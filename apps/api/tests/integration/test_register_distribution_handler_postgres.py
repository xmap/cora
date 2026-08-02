"""End-to-end integration test: register_distribution handler against real Postgres.

Pins the Distribution genesis cross-BC contract end-to-end:

  - Happy: register a Storage Supply -> register a Dataset -> register
    a Distribution; verify the DistributionRegistered event lands with
    canonical payload + version=1 in the Postgres event store, and the
    proj_data_distribution_summary projection row exists after drain.
  - kind!=Storage: register a Consumable Supply; register_distribution
    raises DistributionCannotRegisterOnNonStorageSupplyError.
  - Dataset Discarded: register + discard a Dataset; register_distribution
    raises DistributionCannotRegisterOnDiscardedDatasetError.
  - Checksum mismatch: byte-identical-copy invariant per L10.
  - byte_size mismatch: byte-identical-copy invariant per L11.
  - Decommissioned Supply still binds: per L28 status-agnostic bind.

The PostgresSupplyLookup adapter reads the proj_supply_summary
projection, so each Supply registration is followed by a drain of the
Supply BC projection worker before the dependent register_distribution
call sees the row.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.data._projections import register_data_projections
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from cora.data.aggregates.distribution import (
    DistributionByteSizeMismatchError,
    DistributionCannotRegisterOnDiscardedDatasetError,
    DistributionCannotRegisterOnNonStorageSupplyError,
    DistributionChecksumMismatchError,
)
from cora.data.features import discard_dataset, register_dataset, register_distribution
from cora.data.features.discard_dataset import DiscardDataset
from cora.data.features.register_dataset import RegisterDataset
from cora.data.features.register_distribution import RegisterDistribution
from cora.infrastructure.deps import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.supply._projections import register_supply_projections
from cora.supply.adapters import PostgresSupplyLookup
from cora.supply.features import deregister_supply, register_supply
from cora.supply.features.deregister_supply import DeregisterSupply
from cora.supply.features.register_supply import RegisterSupply
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_OTHER_SHA256 = "b" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _drain_supply(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_supply_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


async def _drain_data(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_data_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


def _with_postgres_supply_lookup(deps: Kernel, pool: asyncpg.Pool) -> Kernel:
    return replace(deps, supply_lookup=PostgresSupplyLookup(pool))


async def _register_storage_supply(
    db_pool: asyncpg.Pool,
    supply_id: UUID,
    *,
    name: str = "primary-store",
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[supply_id, uuid4()])
    await register_supply.bind(deps)(
        RegisterSupply(kind="Storage", name=name, facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_supply(db_pool)


async def _register_non_storage_supply(
    db_pool: asyncpg.Pool,
    supply_id: UUID,
    *,
    kind: str = "Consumable",
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[supply_id, uuid4()])
    await register_supply.bind(deps)(
        RegisterSupply(kind=kind, name=f"{kind}-stub", facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_supply(db_pool)


async def _register_dataset(
    db_pool: asyncpg.Pool,
    dataset_id: UUID,
    *,
    checksum: str = _GOOD_SHA256,
    byte_size: int = 1024,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[dataset_id, uuid4()])
    await register_dataset.bind(deps)(
        RegisterDataset(
            name="parent-dataset",
            uri="s3://aps-32id/runs/abc/recon.h5",
            checksum_algorithm="sha256",
            checksum_value=checksum,
            byte_size=byte_size,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


def _good_command(
    *,
    dataset_id: UUID,
    supply_id: UUID,
    **overrides: object,
) -> RegisterDistribution:
    base: dict[str, object] = {
        "dataset_id": dataset_id,
        "supply_id": supply_id,
        "uri": "s3://aps-32id/runs/abc/recon.h5",
        "checksum_algorithm": "sha256",
        "checksum_value": _GOOD_SHA256,
        "byte_size": 1024,
        "media_type": "application/x-hdf5",
        "conforms_to": frozenset[str](),
        "access_protocol": "S3",
    }
    base.update(overrides)
    return RegisterDistribution(**base)  # type: ignore[arg-type]


# ---------- Happy path + projection ----------


@pytest.mark.integration
async def test_register_distribution_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    dataset_id = uuid4()
    supply_id = uuid4()
    distribution_id = uuid4()
    event_id = uuid4()

    await _register_dataset(db_pool, dataset_id)
    await _register_storage_supply(db_pool, supply_id)

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[distribution_id, event_id])
    deps = _with_postgres_supply_lookup(deps, db_pool)

    returned_id = await register_distribution.bind(deps)(
        _good_command(dataset_id=dataset_id, supply_id=supply_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == distribution_id

    events, version = await deps.event_store.load("Distribution", distribution_id)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "DistributionRegistered"
    payload = stored.payload
    assert payload["distribution_id"] == str(distribution_id)
    assert payload["dataset_id"] == str(dataset_id)
    assert payload["supply_id"] == str(supply_id)
    assert payload["uri"] == "s3://aps-32id/runs/abc/recon.h5"
    assert payload["checksum"] == {"algorithm": "sha256", "value": _GOOD_SHA256}
    assert payload["byte_size"] == 1024
    assert payload["access_protocol"] == "S3"
    assert payload["registered_by"] == str(_PRINCIPAL_ID)

    # Projection writer round-trip.
    await _drain_data(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT distribution_id, dataset_id, supply_id, uri, byte_size, "
            "access_protocol, status, registered_by, checksum, encoding "
            "FROM proj_data_distribution_summary WHERE distribution_id = $1",
            distribution_id,
        )
    assert row is not None
    assert row["distribution_id"] == distribution_id
    assert row["dataset_id"] == dataset_id
    assert row["supply_id"] == supply_id
    assert row["uri"] == "s3://aps-32id/runs/abc/recon.h5"
    assert row["byte_size"] == 1024
    assert row["access_protocol"] == "S3"
    assert row["status"] == "Registered"
    assert row["registered_by"] == _PRINCIPAL_ID
    assert json.loads(row["checksum"]) == {"algorithm": "sha256", "value": _GOOD_SHA256}
    assert json.loads(row["encoding"]) == {
        "media_type": "application/x-hdf5",
        "conforms_to": [],
    }


# ---------- Rejection branches ----------


@pytest.mark.integration
async def test_register_distribution_rejects_non_storage_supply(
    db_pool: asyncpg.Pool,
) -> None:
    dataset_id = uuid4()
    supply_id = uuid4()
    distribution_id = uuid4()
    event_id = uuid4()

    await _register_dataset(db_pool, dataset_id)
    await _register_non_storage_supply(db_pool, supply_id, kind="Consumable")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[distribution_id, event_id])
    deps = _with_postgres_supply_lookup(deps, db_pool)

    with pytest.raises(DistributionCannotRegisterOnNonStorageSupplyError):
        await register_distribution.bind(deps)(
            _good_command(dataset_id=dataset_id, supply_id=supply_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
async def test_register_distribution_rejects_discarded_dataset(
    db_pool: asyncpg.Pool,
) -> None:
    dataset_id = uuid4()
    supply_id = uuid4()
    distribution_id = uuid4()
    event_id = uuid4()

    await _register_dataset(db_pool, dataset_id)
    # Discard the parent Dataset.
    discard_deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    await discard_dataset.bind(discard_deps)(
        DiscardDataset(dataset_id=dataset_id, reason="bytes-deleted-out-of-band"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _register_storage_supply(db_pool, supply_id)

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[distribution_id, event_id])
    deps = _with_postgres_supply_lookup(deps, db_pool)

    with pytest.raises(DistributionCannotRegisterOnDiscardedDatasetError):
        await register_distribution.bind(deps)(
            _good_command(dataset_id=dataset_id, supply_id=supply_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
async def test_register_distribution_rejects_checksum_mismatch(
    db_pool: asyncpg.Pool,
) -> None:
    dataset_id = uuid4()
    supply_id = uuid4()
    distribution_id = uuid4()
    event_id = uuid4()

    await _register_dataset(db_pool, dataset_id, checksum=_GOOD_SHA256)
    await _register_storage_supply(db_pool, supply_id)

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[distribution_id, event_id])
    deps = _with_postgres_supply_lookup(deps, db_pool)

    with pytest.raises(DistributionChecksumMismatchError):
        await register_distribution.bind(deps)(
            _good_command(dataset_id=dataset_id, supply_id=supply_id, checksum_value=_OTHER_SHA256),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
async def test_register_distribution_rejects_byte_size_mismatch(
    db_pool: asyncpg.Pool,
) -> None:
    dataset_id = uuid4()
    supply_id = uuid4()
    distribution_id = uuid4()
    event_id = uuid4()

    await _register_dataset(db_pool, dataset_id, byte_size=1024)
    await _register_storage_supply(db_pool, supply_id)

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[distribution_id, event_id])
    deps = _with_postgres_supply_lookup(deps, db_pool)

    with pytest.raises(DistributionByteSizeMismatchError):
        await register_distribution.bind(deps)(
            _good_command(dataset_id=dataset_id, supply_id=supply_id, byte_size=2048),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
async def test_register_distribution_binds_against_decommissioned_supply(
    db_pool: asyncpg.Pool,
) -> None:
    """Per L28: status-agnostic bind. A Decommissioned-storage Supply
    still surfaces via PostgresSupplyLookup.lookup, and the decider
    only gates on kind."""
    dataset_id = uuid4()
    supply_id = uuid4()
    distribution_id = uuid4()
    event_id = uuid4()

    await _register_dataset(db_pool, dataset_id)
    await _register_storage_supply(db_pool, supply_id)
    # Walk the Supply to Decommissioned (deregister accepts any
    # non-Decommissioned source state per deregister_supply decider).
    dereg_deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    await deregister_supply.bind(dereg_deps)(
        DeregisterSupply(supply_id=supply_id, reason="end-of-life"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_supply(db_pool)

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[distribution_id, event_id])
    deps = _with_postgres_supply_lookup(deps, db_pool)

    returned_id = await register_distribution.bind(deps)(
        _good_command(dataset_id=dataset_id, supply_id=supply_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == distribution_id

    events, _ = await deps.event_store.load("Distribution", distribution_id)
    assert len(events) == 1
    assert events[0].event_type == "DistributionRegistered"
