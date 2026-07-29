"""ingest_scan end to end: a real HDF5 file into real Postgres.

The unit tier proves the composition with fakes; this tier proves the
whole path with nothing faked below the cross-BC lookups: a synthetic
Data Exchange file on disk, the real DataExchangeScanReader, the real
PosixChecksumAdapter digest, real deciders, and one real
`append_streams` transaction against Postgres. Plus the natural-key
probe against the projection's checksum columns, which only this tier
can exercise (the columns are this branch's own migration).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import replace as dc_replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import h5py
import numpy as np
import pytest

from cora.data.adapters.data_exchange_scan_reader import DataExchangeScanReader
from cora.data.adapters.posix_checksum import PosixChecksumAdapter
from cora.data.aggregates.dataset import DatasetAlreadyIngestedError
from cora.data.features import ingest_scan
from cora.data.ports.checksum_computer import ComputedChecksum
from cora.data.wire import (
    _build_dataset_by_checksum_lookup,  # pyright: ignore[reportPrivateUsage]
)
from cora.infrastructure.adapters.in_memory_asset_lookup import InMemoryAssetLookup
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.supply_lookup import SingleSupplyLookup, SupplyLookupResult
from tests.integration._helpers import build_postgres_deps

pytestmark = pytest.mark.integration

_NOW = datetime(2026, 7, 29, 16, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = uuid4()
_ASSET_ID = uuid4()
_SUPPLY_ID = uuid4()


def _write_scan(path: Path) -> None:
    with h5py.File(path, "w") as f:
        f.create_dataset("exchange/data", data=np.zeros((4, 4, 4), dtype=np.uint16))
        f.create_dataset("exchange/data_white", data=np.zeros((2, 4, 4), dtype=np.uint16))
        f.create_dataset("exchange/data_dark", data=np.zeros((2, 4, 4), dtype=np.uint16))
        f.create_dataset("exchange/theta", data=np.linspace(0.0, 180.0, 4))
        f.create_dataset("process/acquisition/rotation/num_angles", data=4)
        f.create_dataset("process/acquisition/start_date", data="2026-07-29T10:15:30-05:00")


def _deps(pool: asyncpg.Pool) -> Kernel:
    lookup = InMemoryAssetLookup()
    lookup.register(
        asset_id=_ASSET_ID,
        name="Oryx Detector",
        tier="Device",
        lifecycle="Active",
        family_affordances=frozenset({"Capturing"}),
    )
    base = build_postgres_deps(
        pool,
        now=_NOW,
        asset_lookup=lookup,
        # ingest consumes six ids per success (three aggregates, three
        # event envelopes); give the queue slack for both tests.
        ids=[uuid4() for _ in range(12)],
    )
    supply = SupplyLookupResult(
        supply_id=_SUPPLY_ID,
        kind="Storage",
        name="analysis tier",
        status="Available",
        facility_code="aps",
    )
    return dc_replace(base, supply_lookup=SingleSupplyLookup(supply))


def _bind(deps: Kernel, pool: asyncpg.Pool, roots: tuple[str, ...]) -> ingest_scan.Handler:
    return ingest_scan.bind(
        deps,
        scan_reader=DataExchangeScanReader(allowed_roots=roots),
        checksum_computer=PosixChecksumAdapter(allowed_roots=roots),
        dataset_by_checksum_lookup=_build_dataset_by_checksum_lookup(deps),
    )


async def test_ingest_real_file_lands_three_streams_in_postgres(
    db_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    scan = tmp_path / "scan_001.h5"
    _write_scan(scan)
    deps = _deps(db_pool)
    handler = _bind(deps, db_pool, roots=(str(tmp_path),))

    dataset_id = await handler(
        ingest_scan.IngestScan(
            locator=scan.as_uri(),
            producing_asset_id=_ASSET_ID,
            supply_id=_SUPPLY_ID,
            access_protocol="POSIX",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=uuid4(),
    )

    dataset_events, dataset_version = await deps.event_store.load("Dataset", dataset_id)
    assert dataset_version == 1
    assert dataset_events[0].event_type == "DatasetRegistered"
    assert dataset_events[0].payload["name"] == "scan_001.h5"

    row = await db_pool.fetchrow(
        "SELECT COUNT(*) AS n FROM events WHERE correlation_id IS NOT NULL "
        "AND stream_type IN ('Dataset', 'Distribution', 'Acquisition')"
    )
    assert row is not None and row["n"] >= 3


async def test_ingest_known_checksum_row_refuses_via_the_projection_probe(
    db_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    """The natural-key probe reads the migration's new columns for real:
    seed a projection row with the file's actual digest, then watch the
    refusal name that dataset."""
    scan = tmp_path / "scan_002.h5"
    _write_scan(scan)
    deps = _deps(db_pool)
    handler = _bind(deps, db_pool, roots=(str(tmp_path),))

    computed = await PosixChecksumAdapter(allowed_roots=(str(tmp_path),)).compute(
        locator_uri=scan.as_uri(), supply_id=_SUPPLY_ID
    )
    assert isinstance(computed, ComputedChecksum)
    existing_id: UUID = uuid4()
    await db_pool.execute(
        "INSERT INTO proj_data_dataset_summary "
        "(dataset_id, name, uri, status, created_at, checksum_algorithm, checksum_value) "
        "VALUES ($1, $2, $3, 'Registered', $4, $5, $6)",
        existing_id,
        "scan_002.h5",
        scan.as_uri(),
        _NOW,
        computed.algorithm,
        computed.value,
    )

    with pytest.raises(DatasetAlreadyIngestedError) as caught:
        await handler(
            ingest_scan.IngestScan(
                locator=scan.as_uri(),
                producing_asset_id=_ASSET_ID,
                supply_id=_SUPPLY_ID,
                access_protocol="POSIX",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=uuid4(),
        )

    assert caught.value.existing_dataset_id == existing_id
