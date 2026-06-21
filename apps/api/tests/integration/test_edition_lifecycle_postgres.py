"""End-to-end integration test: full Edition lifecycle against real Postgres.

Walks one Edition through every transition slice:

  register_edition -> seal_edition -> publish_edition -> withdraw_edition

with the cross-aggregate precondition chain seal requires:

  - a Storage Supply
  - a Production-intent Dataset (registered then promoted)
  - a canonical Distribution for that Dataset (so the seal-time
    canonical-distribution lookup succeeds)

After each transition the test drains the Data projection worker and
asserts proj_data_edition_summary reflects the new state:

  Registered -> content_hash set at Seal -> external_pid +
  published_content_hash set at Publish -> withdrawal_reason set at
  Withdraw, status walking Registered -> Sealed -> Published ->
  Withdrawn.

The Edition slices read `deps.data.{distribution_lookup,
edition_serializers, persistent_identifier_minter}`; `build_postgres_deps` does not wire
that BC-local namespace, so the test attaches it (PostgresDistribution
Lookup + RoCrate12Adapter + StubPersistentIdentifierMinter) per deps build, mirroring
`wire_data`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.data._projections import register_data_projections
from cora.data.adapters.postgres_distribution_lookup import PostgresDistributionLookup
from cora.data.adapters.rocrate12_serializer import RoCrate12Adapter
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from cora.data.aggregates.edition import EditionKind
from cora.data.features import (
    promote_dataset,
    publish_edition,
    register_dataset,
    register_distribution,
    register_edition,
    seal_edition,
    withdraw_edition,
)
from cora.data.features.promote_dataset import PromoteDataset
from cora.data.features.publish_edition.command import PublishEdition
from cora.data.features.register_dataset import RegisterDataset
from cora.data.features.register_distribution import RegisterDistribution
from cora.data.features.register_edition import CreatorEntry, RegisterEdition
from cora.data.features.seal_edition.command import SealEdition
from cora.data.features.withdraw_edition.command import WithdrawEdition
from cora.infrastructure.adapters.stub_persistent_identifier_minter import (
    StubPersistentIdentifierMinter,
)
from cora.infrastructure.deps import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.supply._projections import register_supply_projections
from cora.supply.adapters import PostgresSupplyLookup
from cora.supply.features import register_supply
from cora.supply.features.register_supply import RegisterSupply
from tests.integration._helpers import build_postgres_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_URI = "s3://aps-2bm/runs/abc/recon.h5"


def _attach_data_namespace(deps: Kernel, pool: asyncpg.Pool) -> Kernel:
    """Wire the BC-local `deps.data` namespace the Edition slices read.

    Mirrors `wire_data`: PostgresDistributionLookup (pool-backed),
    the RoCrate serializer map, and the StubPersistentIdentifierMinter.
    """
    object.__setattr__(
        deps,
        "data",
        SimpleNamespace(
            distribution_lookup=PostgresDistributionLookup(pool),
            edition_serializers={EditionKind.ROCRATE: RoCrate12Adapter()},
            persistent_identifier_minter=StubPersistentIdentifierMinter(),
        ),
    )
    return deps


async def _drain_supply(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_supply_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _drain_data(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_data_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _register_storage_supply(db_pool: asyncpg.Pool, supply_id: UUID) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[supply_id, uuid4()])
    await register_supply.bind(deps)(
        RegisterSupply(kind="Storage", name="primary-store", facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_supply(db_pool)


async def _register_production_dataset(db_pool: asyncpg.Pool, dataset_id: UUID) -> None:
    reg_deps = build_postgres_deps(db_pool, now=_NOW, ids=[dataset_id, uuid4()])
    await register_dataset.bind(reg_deps)(
        RegisterDataset(
            name="recon",
            uri=_URI,
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA256,
            byte_size=1024,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    promote_deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    await promote_dataset.bind(promote_deps)(
        PromoteDataset(dataset_id=dataset_id, reason="for publication"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _register_distribution(
    db_pool: asyncpg.Pool,
    *,
    dataset_id: UUID,
    supply_id: UUID,
    distribution_id: UUID,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[distribution_id, uuid4()])
    deps = replace(deps, supply_lookup=PostgresSupplyLookup(db_pool))
    await register_distribution.bind(deps)(
        RegisterDistribution(
            dataset_id=dataset_id,
            supply_id=supply_id,
            uri=_URI,
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA256,
            byte_size=1024,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
            access_protocol="S3",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_data(db_pool)


@pytest.mark.integration
async def test_edition_walks_register_seal_publish_withdraw(
    db_pool: asyncpg.Pool,
) -> None:
    supply_id = uuid4()
    dataset_id = uuid4()
    distribution_id = uuid4()
    edition_id = uuid4()

    await _register_storage_supply(db_pool, supply_id)
    await _register_production_dataset(db_pool, dataset_id)
    await _register_distribution(
        db_pool,
        dataset_id=dataset_id,
        supply_id=supply_id,
        distribution_id=distribution_id,
    )

    # Register the Edition.
    reg_deps = build_postgres_deps(db_pool, now=_NOW, ids=[edition_id, uuid4()])
    returned_id = await register_edition.bind(reg_deps)(
        RegisterEdition(
            kind="ROCrate",
            title="Lifecycle Edition",
            dataset_ids=frozenset({dataset_id}),
            creators=(CreatorEntry(actor_id=uuid4(), affiliation="ANL"),),
            publisher_facility_code="cora",
            license="CC-BY-4.0",
            publication_year=2026,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == edition_id

    await _drain_data(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, content_hash FROM proj_data_edition_summary WHERE edition_id = $1",
            edition_id,
        )
    assert row is not None
    assert row["status"] == "Registered"
    assert row["content_hash"] is None

    # Seal the Edition.
    seal_deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    seal_deps = _attach_data_namespace(seal_deps, db_pool)
    await seal_edition.bind(seal_deps)(
        SealEdition(edition_id=edition_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain_data(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, content_hash, publisher_facility_code, publication_year "
            "FROM proj_data_edition_summary WHERE edition_id = $1",
            edition_id,
        )
    assert row is not None
    assert row["status"] == "Sealed"
    assert row["content_hash"] is not None
    assert len(row["content_hash"]) == 64
    assert row["publisher_facility_code"] == "cora"
    assert row["publication_year"] == 2026
    sealed_content_hash = row["content_hash"]

    # Publish the Edition.
    publish_deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    publish_deps = _attach_data_namespace(publish_deps, db_pool)
    await publish_edition.bind(publish_deps)(
        PublishEdition(edition_id=edition_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain_data(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, content_hash, external_pid_scheme, external_pid_value, "
            "published_content_hash FROM proj_data_edition_summary "
            "WHERE edition_id = $1",
            edition_id,
        )
    assert row is not None
    assert row["status"] == "Published"
    # Sealed content_hash is immutable across Publish.
    assert row["content_hash"] == sealed_content_hash
    assert row["external_pid_scheme"] == "DOI"
    assert row["external_pid_value"].startswith("10.0000/cora-stub/")
    assert str(edition_id) in row["external_pid_value"]
    assert row["published_content_hash"] is not None
    assert len(row["published_content_hash"]) == 64

    # Withdraw the Edition.
    withdraw_deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    withdraw_deps = _attach_data_namespace(withdraw_deps, db_pool)
    await withdraw_edition.bind(withdraw_deps)(
        WithdrawEdition(edition_id=edition_id, withdrawal_reason="superseded by v2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain_data(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, withdrawal_reason FROM proj_data_edition_summary WHERE edition_id = $1",
            edition_id,
        )
    assert row is not None
    assert row["status"] == "Withdrawn"
    assert row["withdrawal_reason"] == "superseded by v2"

    # Final event-store sanity: 4 events on the Edition stream.
    events, version = await withdraw_deps.event_store.load("Edition", edition_id)
    assert version == 4
    assert [e.event_type for e in events] == [
        "EditionRegistered",
        "EditionSealed",
        "EditionPublished",
        "EditionWithdrawn",
    ]
