"""The pilot seed ceremony, end to end against real Postgres.

Three claims, one flow: a fresh database seeds (exit 2), a re-run
changes nothing (exit 0), and `ingest_scan` then records a real file
through the REAL `PostgresAssetLookup` and `PostgresSupplyLookup`,
which retires the in-memory fake as the only Capturing-bearing asset
in the test suite. This is the proof the seeder design's gate review
demanded: the seeded camera must surface the Capturing affordance
through the projection join, or the ceremony is decoration.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import replace as dc_replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import asyncpg
import h5py
import numpy as np
import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer

from cora.api.pilot_seed import asset_seed_id, seed_pilot_beamline
from cora.data.adapters.data_exchange_scan_reader import DataExchangeScanReader
from cora.data.adapters.posix_checksum import PosixChecksumAdapter
from cora.data.features import ingest_scan
from cora.data.wire import (
    _build_dataset_by_checksum_lookup,  # pyright: ignore[reportPrivateUsage]
)
from cora.equipment.adapters.postgres_asset_lookup import PostgresAssetLookup
from cora.infrastructure.postgres.pool import create_pool
from cora.supply.adapters.postgres_supply_lookup import PostgresSupplyLookup
from tests._postgres import normalize_async_url
from tests.integration._helpers import build_postgres_deps

pytestmark = pytest.mark.integration

SeedDatabase = tuple[asyncpg.Pool, str]

_NOW = datetime(2026, 7, 29, 16, 0, 0, tzinfo=UTC)
_FACILITY = "cora"
_BEAMLINE = "2-bm"
_CAMERA = "Camera"


@pytest_asyncio.fixture
async def seed_database(
    postgres_container: PostgresContainer,
    template_database: str,
):
    """A per-test database plus its URL, because the ceremony builds its
    own pool from a URL rather than borrowing the fixture's."""
    test_db = f"seed_{uuid4().hex[:12]}"
    admin_url = normalize_async_url(postgres_container.get_connection_url(), database="postgres")
    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f'CREATE DATABASE "{test_db}" TEMPLATE "{template_database}"')
    finally:
        await admin.close()

    test_url = normalize_async_url(postgres_container.get_connection_url(), database=test_db)
    pool = await create_pool(test_url, min_size=1, max_size=4)
    try:
        yield pool, test_url
    finally:
        await pool.close()
        admin = await asyncpg.connect(admin_url)
        try:
            await admin.execute(f'DROP DATABASE "{test_db}"')
        finally:
            await admin.close()


async def _run_ceremony(url: str, *, dry_run: bool = False) -> int:
    return await seed_pilot_beamline(
        facility_code=_FACILITY,
        beamline=_BEAMLINE,
        root_name="2-BM",
        camera_name=_CAMERA,
        camera_family_name="Camera",
        supply_name="analysis-tier",
        dry_run=dry_run,
        database_url=url,
    )


def _write_scan(path: Path) -> None:
    with h5py.File(path, "w") as f:
        f.create_dataset("exchange/data", data=np.zeros((4, 4, 4), dtype=np.uint16))
        f.create_dataset("exchange/theta", data=np.linspace(0.0, 180.0, 4))
        f.create_dataset("process/acquisition/rotation/num_angles", data=4)
        f.create_dataset("process/acquisition/start_date", data="2026-07-29T10:15:30-05:00")


async def test_ceremony_seeds_then_rerun_changes_nothing(seed_database: SeedDatabase) -> None:
    pool, url = seed_database

    first = await _run_ceremony(url)
    assert first == 2, "first run must report seeded"

    events_after_first = await pool.fetchval("SELECT COUNT(*) FROM events")

    second = await _run_ceremony(url)
    assert second == 0, "second run must report all-exists"

    events_after_second = await pool.fetchval("SELECT COUNT(*) FROM events")
    assert events_after_second == events_after_first, "a re-run must append zero events"


async def test_dry_run_writes_nothing_beyond_bootstrap(seed_database: SeedDatabase) -> None:
    pool, url = seed_database

    exit_code = await _run_ceremony(url, dry_run=True)
    assert exit_code == 2, "dry run against a fresh database reports would-seed"

    camera_streams = await pool.fetchval(
        "SELECT COUNT(*) FROM events WHERE stream_id = $1",
        asset_seed_id(_FACILITY, _BEAMLINE, _CAMERA),
    )
    assert camera_streams == 0, "dry run must not write the camera asset"


async def test_seeded_camera_carries_capturing_through_the_real_lookup(
    seed_database: SeedDatabase,
) -> None:
    pool, url = seed_database
    assert await _run_ceremony(url) == 2

    asset = await PostgresAssetLookup(pool).lookup(asset_seed_id(_FACILITY, _BEAMLINE, _CAMERA))
    assert asset is not None
    assert "Capturing" in asset.family_affordances


async def test_ingest_against_the_seeded_beamline_records_the_dataset(
    seed_database: SeedDatabase, tmp_path: Path
) -> None:
    """The whole pipeline with zero fakes: ceremony, then a real HDF5
    file through the real reader, digest, deciders, projections."""
    pool, url = seed_database
    assert await _run_ceremony(url) == 2

    supplies = await PostgresSupplyLookup(pool).find_supplies_by_kind(kinds=frozenset({"Storage"}))
    assert "Storage" in supplies, "the ceremony must have registered a Storage supply"
    supply_id = supplies["Storage"][0].supply_id

    scan = tmp_path / "scan_001.h5"
    _write_scan(scan)

    deps = dc_replace(
        build_postgres_deps(
            pool,
            now=_NOW,
            ids=[uuid4() for _ in range(12)],
            asset_lookup=PostgresAssetLookup(pool),
        ),
        supply_lookup=PostgresSupplyLookup(pool),
    )
    handler = ingest_scan.bind(
        deps,
        scan_reader=DataExchangeScanReader(allowed_roots=(str(tmp_path),)),
        checksum_computer=PosixChecksumAdapter(allowed_roots=(str(tmp_path),)),
        dataset_by_checksum_lookup=_build_dataset_by_checksum_lookup(deps),
    )

    dataset_id = await handler(
        ingest_scan.IngestScan(
            locator=scan.as_uri(),
            producing_asset_id=asset_seed_id(_FACILITY, _BEAMLINE, _CAMERA),
            supply_id=supply_id,
            access_protocol="POSIX",
        ),
        principal_id=uuid4(),
        correlation_id=uuid4(),
    )

    events, version = await deps.event_store.load("Dataset", dataset_id)
    assert version == 1
    assert events[0].event_type == "DatasetRegistered"
    assert events[0].payload["name"] == "scan_001.h5"


async def test_unknown_facility_code_reports_error_and_exit_one(
    seed_database: SeedDatabase,
) -> None:
    """The facility guard is the loud alternative to registering under
    the wrong facility; nothing else runs after it."""
    _, url = seed_database

    exit_code = await seed_pilot_beamline(
        facility_code="nosuchfacility",
        beamline=_BEAMLINE,
        root_name="2-BM",
        camera_name=_CAMERA,
        camera_family_name="Camera",
        supply_name="analysis-tier",
        dry_run=False,
        database_url=url,
    )

    assert exit_code == 1


async def test_unknown_family_name_reports_error_and_exit_one(seed_database: SeedDatabase) -> None:
    _, url = seed_database

    exit_code = await seed_pilot_beamline(
        facility_code=_FACILITY,
        beamline=_BEAMLINE,
        root_name="2-BM",
        camera_name=_CAMERA,
        camera_family_name="NoSuchFamily",
        supply_name="analysis-tier",
        dry_run=False,
        database_url=url,
    )

    assert exit_code == 1


async def test_mid_ceremony_exception_reports_error_and_exit_one(
    seed_database: SeedDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CLI catch: any unexpected failure becomes a named report line
    and exit 1, never a traceback swallowed into a zero."""
    _, url = seed_database

    async def explode(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("synthetic mid-ceremony failure")

    monkeypatch.setattr("cora.api.pilot_seed.verify_schema_version", explode)

    exit_code = await seed_pilot_beamline(
        facility_code=_FACILITY,
        beamline=_BEAMLINE,
        root_name="2-BM",
        camera_name=_CAMERA,
        camera_family_name="Camera",
        supply_name="analysis-tier",
        dry_run=False,
        database_url=url,
    )

    assert exit_code == 1
