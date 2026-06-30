"""Integration tests for `PostgresDatasetDistributionLookup` against real Postgres.

Pins the cross-stream query contract the Run BC's `start_run` input gate
depends on: seeds Datasets + Distributions via `register_dataset` +
`register_distribution`, flips one Distribution to Verified via the
`record_attestation` projection path, drains the Data projection worker,
then queries through the adapter and verifies `find_by_datasets` returns the
non-Discarded set per Dataset with the correct status strings and EXCLUDES
the Discarded row. This is the drift guard for the "Verified" wire literal,
the `proj_data_distribution_summary` column names, and the
`status != 'Discarded'` filter.

Mirrors `tests/integration/test_postgres_supply_lookup.py` (and the
attestation-flip seeding of
`tests/integration/test_distribution_status_flip_via_attestation.py`).

The Discarded row is seeded via a direct projection UPDATE: no
Distribution-discard handler ships in this spike (the
`DistributionDiscarded` transition is named-but-unbuilt and the summary
projection does not yet subscribe to it), so a direct UPDATE to
status='Discarded' is the honest way to pin the query-layer filter, the
same shape `test_postgres_supply_lookup` relies on `deregister_supply` for.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.data._projections import register_data_projections
from cora.data.adapters import PostgresDatasetDistributionLookup
from cora.data.features import (
    record_attestation,
    register_dataset,
    register_distribution,
)
from cora.data.features.record_attestation import RecordAttestation
from cora.data.features.register_dataset import RegisterDataset
from cora.data.features.register_distribution import RegisterDistribution
from cora.data.ports.checksum_verifier import AlwaysMatchingChecksumVerifier
from cora.infrastructure.deps import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.supply._projections import register_supply_projections
from cora.supply.adapters import PostgresSupplyLookup
from cora.supply.features import register_supply
from cora.supply.features.register_supply import RegisterSupply
from tests.integration._helpers import build_postgres_deps

_GOOD_SHA = "a" * 64
_NOW = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _drain_supply(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_supply_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _drain_data(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_data_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _register_storage_supply(db_pool: asyncpg.Pool) -> UUID:
    supply_id = uuid4()
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[supply_id, uuid4()])
    await register_supply.bind(deps)(
        RegisterSupply(kind="Storage", name=f"store-{uuid4()}", facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_supply(db_pool)
    return supply_id


async def _register_dataset(db_pool: asyncpg.Pool) -> UUID:
    dataset_id = uuid4()
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[dataset_id, uuid4()])
    await register_dataset.bind(deps)(
        RegisterDataset(
            name=f"d-{uuid4()}",
            uri=f"s3://aps/runs/{uuid4()}.h5",
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA,
            byte_size=1024,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return dataset_id


async def _register_distribution(
    db_pool: asyncpg.Pool,
    *,
    dataset_id: UUID,
    supply_id: UUID,
    uri: str,
) -> UUID:
    distribution_id = uuid4()
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[distribution_id, uuid4()])
    deps = _with_postgres_supply_lookup(deps, db_pool)
    await register_distribution.bind(deps)(
        RegisterDistribution(
            dataset_id=dataset_id,
            supply_id=supply_id,
            uri=uri,
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA,
            byte_size=1024,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
            access_protocol="HTTPS",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return distribution_id


def _with_postgres_supply_lookup(deps: Kernel, pool: asyncpg.Pool) -> Kernel:
    return replace(deps, supply_lookup=PostgresSupplyLookup(pool))


async def _flip_to_verified(
    db_pool: asyncpg.Pool,
    *,
    dataset_id: UUID,
    distribution_id: UUID,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    object.__setattr__(
        deps,
        "data",
        SimpleNamespace(checksum_verifiers={"https": AlwaysMatchingChecksumVerifier()}),
    )
    await record_attestation.bind(deps)(
        RecordAttestation(
            dataset_id=dataset_id,
            distribution_id=distribution_id,
            kind="ChecksumVerified",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _discard_distribution_row(db_pool: asyncpg.Pool, distribution_id: UUID) -> None:
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE proj_data_distribution_summary SET status = 'Discarded' "
            "WHERE distribution_id = $1",
            distribution_id,
        )


@pytest.mark.integration
async def test_find_by_datasets_returns_non_discarded_rows_with_statuses(
    db_pool: asyncpg.Pool,
) -> None:
    """One Dataset with a Verified and a Registered Distribution; the adapter
    returns both with their correct status strings."""
    supply_id = await _register_storage_supply(db_pool)
    dataset_id = await _register_dataset(db_pool)
    verified_dist = await _register_distribution(
        db_pool, dataset_id=dataset_id, supply_id=supply_id, uri=f"https://store/{uuid4()}.h5"
    )
    registered_dist = await _register_distribution(
        db_pool, dataset_id=dataset_id, supply_id=supply_id, uri=f"https://store/{uuid4()}.h5"
    )
    await _drain_data(db_pool)
    await _flip_to_verified(db_pool, dataset_id=dataset_id, distribution_id=verified_dist)
    await _drain_data(db_pool)

    lookup = PostgresDatasetDistributionLookup(db_pool)
    result = await lookup.find_by_datasets(frozenset({dataset_id}))

    assert set(result.keys()) == {dataset_id}
    by_id = {r.distribution_id: r for r in result[dataset_id]}
    assert set(by_id) == {verified_dist, registered_dist}
    assert by_id[verified_dist].status == "Verified"
    assert by_id[registered_dist].status == "Registered"
    assert by_id[verified_dist].dataset_id == dataset_id
    assert by_id[verified_dist].supply_id == supply_id


@pytest.mark.integration
async def test_find_by_datasets_excludes_discarded_rows(
    db_pool: asyncpg.Pool,
) -> None:
    """A Discarded Distribution row is excluded at the query layer; the
    remaining Registered peer is still returned.

    Pins the `status != 'Discarded'` clause directly: the row is physically
    present (UPDATEd to status='Discarded', not deleted), and the query must
    still exclude it.
    """
    supply_id = await _register_storage_supply(db_pool)
    dataset_id = await _register_dataset(db_pool)
    kept_dist = await _register_distribution(
        db_pool, dataset_id=dataset_id, supply_id=supply_id, uri=f"https://store/{uuid4()}.h5"
    )
    discarded_dist = await _register_distribution(
        db_pool, dataset_id=dataset_id, supply_id=supply_id, uri=f"https://store/{uuid4()}.h5"
    )
    await _drain_data(db_pool)
    await _discard_distribution_row(db_pool, discarded_dist)

    lookup = PostgresDatasetDistributionLookup(db_pool)
    result = await lookup.find_by_datasets(frozenset({dataset_id}))

    returned_ids = {r.distribution_id for r in result[dataset_id]}
    assert returned_ids == {kept_dist}
    assert discarded_dist not in returned_ids


@pytest.mark.integration
async def test_find_by_datasets_buckets_by_dataset_and_omits_absent_ids(
    db_pool: asyncpg.Pool,
) -> None:
    """A grouped request over two Datasets buckets rows by dataset_id; a
    Dataset with no Distribution is absent from the mapping."""
    supply_id = await _register_storage_supply(db_pool)
    dataset_with_dist = await _register_dataset(db_pool)
    dataset_without_dist = await _register_dataset(db_pool)
    dist = await _register_distribution(
        db_pool,
        dataset_id=dataset_with_dist,
        supply_id=supply_id,
        uri=f"https://store/{uuid4()}.h5",
    )
    await _drain_data(db_pool)

    lookup = PostgresDatasetDistributionLookup(db_pool)
    result = await lookup.find_by_datasets(frozenset({dataset_with_dist, dataset_without_dist}))

    assert set(result.keys()) == {dataset_with_dist}
    assert [r.distribution_id for r in result[dataset_with_dist]] == [dist]


@pytest.mark.integration
async def test_find_by_datasets_empty_input_short_circuits(
    db_pool: asyncpg.Pool,
) -> None:
    """Empty dataset_ids set returns an empty mapping without hitting PG."""
    lookup = PostgresDatasetDistributionLookup(db_pool)
    result = await lookup.find_by_datasets(frozenset())
    assert result == {}
