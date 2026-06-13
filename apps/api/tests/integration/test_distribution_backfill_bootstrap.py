"""Integration tests for the Slice 2 Distribution backfill bootstrap.

Per [[project-data-distribution-design]] L23 + L23a + L24 + L24b: two
lifespan-Python startup steps pin the legacy `Dataset.uri` rows to a
storage-kind Supply by synthesizing one `proj_data_distribution_summary`
row per Dataset, with deterministic ids derived from
`uuid5(_DATA_DISTRIBUTION_BACKFILL_NAMESPACE, str(dataset_id))`.

The fail-loud `DefaultStorageSupplyBootstrapError` class (with a
`DefaultStorageSupplyBootstrapFailure` discriminator) closes the
remediable misconfiguration branches; an unmapped URI scheme raises
`UnmappedDistributionUriSchemeError` and aborts the backfill mid-loop.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4, uuid5

import asyncpg
import pytest

from cora.data._bootstrap import (
    bootstrap_default_storage_supply,
    bootstrap_distribution_backfill,
)
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from cora.data.aggregates.distribution import (
    DefaultStorageSupplyBootstrapError,
    DefaultStorageSupplyBootstrapFailure,
    UnmappedDistributionUriSchemeError,
)
from cora.data.aggregates.distribution._namespaces import (
    _DATA_DISTRIBUTION_BACKFILL_NAMESPACE,  # pyright: ignore[reportPrivateUsage]
)
from cora.data.features import register_dataset
from cora.data.features.register_dataset import RegisterDataset
from cora.data.projections.summary import DatasetSummaryProjection
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.supply._projections import register_supply_projections
from cora.supply.adapters import PostgresSupplyLookup
from cora.supply.features import deregister_supply, register_supply
from cora.supply.features.deregister_supply import DeregisterSupply
from cora.supply.features.register_supply import RegisterSupply
from tests.integration._helpers import build_postgres_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")

_STORAGE_SUPPLY_NAME = "primary-store"


async def _drain_supply(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_supply_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _drain_dataset(db_pool: asyncpg.Pool) -> None:
    """Drain ONLY the Dataset summary projection (not Distribution).

    The backfill bootstrap reads `proj_data_dataset_summary`; the
    Distribution summary projection writer is irrelevant to these
    tests (and would race the backfill if started before it). Mirrors
    the production lifespan ordering: backfill runs before any
    projection worker registers.
    """
    registry = ProjectionRegistry()
    registry.register(DatasetSummaryProjection())
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


def _bootstrap_deps(deps: Kernel, supply_code: str | None) -> Kernel:
    """Deps for a `bootstrap_default_storage_supply` call.

    Sets the default-storage-supply env code and wires the real
    `PostgresSupplyLookup` so the bootstrap resolves against the actual
    `proj_supply_summary` projection. The `build_postgres_deps` default
    `supply_lookup` (the `AllSatisfiedSupplyLookup` stub) does not back
    the by-name resolution path the bootstrap now uses.
    """
    assert deps.pool is not None
    return replace(
        deps,
        settings=deps.settings.model_copy(
            update={"self_facility_default_storage_supply_code": supply_code}
        ),
        supply_lookup=PostgresSupplyLookup(deps.pool),
    )


async def _register_storage_supply(
    db_pool: asyncpg.Pool,
    supply_id: UUID,
    *,
    name: str = _STORAGE_SUPPLY_NAME,
    kind: str = "Storage",
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[supply_id, uuid4()])
    await register_supply.bind(deps)(
        RegisterSupply(kind=kind, name=name, facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_supply(db_pool)


async def _mark_supply_available(db_pool: asyncpg.Pool, supply_id: UUID) -> None:
    """Walk a freshly-registered Supply (status='Unknown') to 'Available'.

    The Supply BC's `register_supply` ships a row at status='Unknown';
    only `mark_supply_available` (or a transition trigger) flips it to
    'Available'. The backfill bootstrap requires status='Available'.
    """
    from cora.supply.features import mark_supply_available
    from cora.supply.features.mark_supply_available import MarkSupplyAvailable

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    await mark_supply_available.bind(deps)(
        MarkSupplyAvailable(
            supply_id=supply_id,
            reason="initial bootstrap",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_supply(db_pool)


async def _register_dataset(
    db_pool: asyncpg.Pool,
    dataset_id: UUID,
    *,
    uri: str = "s3://aps-32id/runs/abc/recon.h5",
    byte_size: int = 1024,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[dataset_id, uuid4()])
    await register_dataset.bind(deps)(
        RegisterDataset(
            name=f"dataset-{dataset_id.hex[:8]}",
            uri=uri,
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA256,
            byte_size=byte_size,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


# ---------- bootstrap_default_storage_supply branches ----------


@pytest.mark.integration
async def test_env_var_unset_with_no_legacy_datasets_succeeds_no_op(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW)
    deps = _bootstrap_deps(deps, None)

    supply_id = await bootstrap_default_storage_supply(deps)
    assert supply_id is None

    count = await bootstrap_distribution_backfill(deps, supply_id)
    assert count == 0


@pytest.mark.integration
async def test_env_var_unset_with_legacy_datasets_raises_unset_error(
    db_pool: asyncpg.Pool,
) -> None:
    await _register_dataset(db_pool, uuid4())
    await _drain_dataset(db_pool)

    deps = build_postgres_deps(db_pool, now=_NOW)
    deps = _bootstrap_deps(deps, None)

    with pytest.raises(DefaultStorageSupplyBootstrapError) as exc_info:
        await bootstrap_default_storage_supply(deps)
    assert exc_info.value.kind is DefaultStorageSupplyBootstrapFailure.CODE_UNSET
    assert exc_info.value.legacy_dataset_count == 1


@pytest.mark.integration
async def test_env_var_set_but_supply_missing_raises_not_found(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW)
    deps = _bootstrap_deps(deps, "NONEXISTENT")

    with pytest.raises(DefaultStorageSupplyBootstrapError) as exc_info:
        await bootstrap_default_storage_supply(deps)
    assert exc_info.value.kind is DefaultStorageSupplyBootstrapFailure.NOT_FOUND
    assert exc_info.value.supply_code == "NONEXISTENT"


@pytest.mark.integration
async def test_env_var_set_supply_wrong_kind_raises_not_found(
    db_pool: asyncpg.Pool,
) -> None:
    """Wrong-kind Supply does not match the facility+kind=Storage query.

    Per the C2 fix, the lookup query filters by `kind='Storage'` in
    SQL; a Consumable-kind Supply with the same name simply does not
    match, surfacing as NOT_FOUND. The previous separate
    `KIND_MISMATCH` discriminator is now redundant.
    """
    supply_id = uuid4()
    await _register_storage_supply(db_pool, supply_id, name="wrong-kind-store", kind="Consumable")
    await _mark_supply_available(db_pool, supply_id)

    deps = build_postgres_deps(db_pool, now=_NOW)
    deps = _bootstrap_deps(deps, "wrong-kind-store")

    with pytest.raises(DefaultStorageSupplyBootstrapError) as exc_info:
        await bootstrap_default_storage_supply(deps)
    assert exc_info.value.kind is DefaultStorageSupplyBootstrapFailure.NOT_FOUND
    assert exc_info.value.supply_code == "wrong-kind-store"


@pytest.mark.integration
async def test_env_var_set_supply_not_available_raises_not_available(
    db_pool: asyncpg.Pool,
) -> None:
    supply_id = uuid4()
    await _register_storage_supply(db_pool, supply_id, name="unknown-store")
    # Skip mark_supply_available: the row stays at status='Unknown'.

    deps = build_postgres_deps(db_pool, now=_NOW)
    deps = _bootstrap_deps(deps, "unknown-store")

    with pytest.raises(DefaultStorageSupplyBootstrapError) as exc_info:
        await bootstrap_default_storage_supply(deps)
    assert exc_info.value.kind is DefaultStorageSupplyBootstrapFailure.NOT_AVAILABLE
    assert exc_info.value.supply_code == "unknown-store"
    assert exc_info.value.actual_status == "Unknown"


# ---------- bootstrap_distribution_backfill happy path + idempotency ----------


@pytest.mark.integration
async def test_happy_path_backfills_three_datasets(db_pool: asyncpg.Pool) -> None:
    supply_id = uuid4()
    await _register_storage_supply(db_pool, supply_id)
    await _mark_supply_available(db_pool, supply_id)

    dataset_ids = sorted([uuid4() for _ in range(3)])
    for did in dataset_ids:
        await _register_dataset(db_pool, did)
    await _drain_dataset(db_pool)

    deps = build_postgres_deps(db_pool, now=_NOW)
    deps = _bootstrap_deps(deps, _STORAGE_SUPPLY_NAME)

    resolved = await bootstrap_default_storage_supply(deps)
    assert resolved == supply_id

    count = await bootstrap_distribution_backfill(deps, resolved)
    assert count == 3

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT distribution_id, dataset_id, supply_id, access_protocol, "
            "       status, backfilled, registered_by "
            "FROM proj_data_distribution_summary "
            "ORDER BY dataset_id"
        )
    assert len(rows) == 3
    for row, did in zip(rows, dataset_ids, strict=True):
        expected_id = uuid5(_DATA_DISTRIBUTION_BACKFILL_NAMESPACE, str(did))
        assert row["distribution_id"] == expected_id
        assert row["dataset_id"] == did
        assert row["supply_id"] == supply_id
        assert row["access_protocol"] == "S3"
        assert row["status"] == "Registered"
        assert row["backfilled"] is True
        assert row["registered_by"] == _PRINCIPAL_ID


@pytest.mark.integration
async def test_backfill_unmapped_uri_scheme_raises(db_pool: asyncpg.Pool) -> None:
    supply_id = uuid4()
    await _register_storage_supply(db_pool, supply_id)
    await _mark_supply_available(db_pool, supply_id)

    dataset_id = uuid4()
    await _register_dataset(db_pool, dataset_id, uri="ftp://legacy/data.h5")
    await _drain_dataset(db_pool)

    deps = build_postgres_deps(db_pool, now=_NOW)
    deps = _bootstrap_deps(deps, _STORAGE_SUPPLY_NAME)

    resolved = await bootstrap_default_storage_supply(deps)
    assert resolved == supply_id

    with pytest.raises(UnmappedDistributionUriSchemeError) as exc_info:
        await bootstrap_distribution_backfill(deps, resolved)
    assert exc_info.value.scheme == "ftp"
    assert exc_info.value.uri == "ftp://legacy/data.h5"


@pytest.mark.integration
async def test_backfill_is_idempotent_on_rerun(db_pool: asyncpg.Pool) -> None:
    supply_id = uuid4()
    await _register_storage_supply(db_pool, supply_id)
    await _mark_supply_available(db_pool, supply_id)

    for _ in range(2):
        await _register_dataset(db_pool, uuid4())
    await _drain_dataset(db_pool)

    deps = build_postgres_deps(db_pool, now=_NOW)
    deps = _bootstrap_deps(deps, _STORAGE_SUPPLY_NAME)

    resolved = await bootstrap_default_storage_supply(deps)
    first = await bootstrap_distribution_backfill(deps, resolved)
    assert first == 2

    # Re-running on the same db must not duplicate rows.
    second = await bootstrap_distribution_backfill(deps, resolved)
    assert second == 0

    async with db_pool.acquire() as conn:
        n = await conn.fetchval(
            "SELECT COUNT(*) FROM proj_data_distribution_summary WHERE backfilled = TRUE"
        )
    assert n == 2


@pytest.mark.integration
async def test_backfill_skips_decommissioned_path_when_supply_unset(
    db_pool: asyncpg.Pool,
) -> None:
    """Backfill is a no-op when supply_id is None (clean install)."""
    deps = build_postgres_deps(db_pool, now=_NOW)
    count = await bootstrap_distribution_backfill(deps, None)
    assert count == 0


# ---------- bind a Supply that gets decommissioned mid-test ----------


@pytest.mark.integration
async def test_decommissioned_supply_fails_status_check(
    db_pool: asyncpg.Pool,
) -> None:
    """Decommissioned Supplies are excluded at the query layer by
    `find_supplies_by_name`'s `status != 'Decommissioned'` filter (the
    deregister_supply slice UPDATEs the projection row to
    status='Decommissioned'; it does not delete it), so the bootstrap
    fails-loud deterministically with NOT_FOUND."""
    supply_id = uuid4()
    await _register_storage_supply(db_pool, supply_id, name="ephemeral-store")
    await _mark_supply_available(db_pool, supply_id)

    dereg_deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    await deregister_supply.bind(dereg_deps)(
        DeregisterSupply(supply_id=supply_id, reason="end-of-life"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_supply(db_pool)

    deps = build_postgres_deps(db_pool, now=_NOW)
    deps = _bootstrap_deps(deps, "ephemeral-store")

    with pytest.raises(DefaultStorageSupplyBootstrapError) as exc_info:
        await bootstrap_default_storage_supply(deps)
    assert exc_info.value.kind is DefaultStorageSupplyBootstrapFailure.NOT_FOUND


def test_settings_default_storage_supply_code_defaults_to_none() -> None:
    """The `self_facility_default_storage_supply_code` Settings field
    defaults to None so clean-install deployments boot without setting
    the env var; tests use the in-memory Settings constructor directly."""
    s = Settings(app_env="test")  # type: ignore[call-arg]
    assert s.self_facility_default_storage_supply_code is None
