"""End-to-end integration test: Edition Registered-state lifecycle against real Postgres.

Exercises the Slice B surface of the Edition aggregate:

  - register an Edition with one member Dataset (genesis)
  - add a second Dataset to the Edition
  - remove the first Dataset from the Edition

After each step the test drains the Data projection worker and asserts
the proj_data_edition_summary.dataset_ids array reflects the change.

Pins Slice A+B end-to-end without touching seal/publish/withdraw.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.data._projections import register_data_projections
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from cora.data.features import (
    add_dataset_to_edition,
    register_dataset,
    register_edition,
    remove_dataset_from_edition,
)
from cora.data.features.add_dataset_to_edition import AddDatasetToEdition
from cora.data.features.register_dataset import RegisterDataset
from cora.data.features.register_edition import CreatorEntry, RegisterEdition
from cora.data.features.remove_dataset_from_edition import RemoveDatasetFromEdition
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _drain_data(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_data_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


async def _register_dataset(
    db_pool: asyncpg.Pool,
    dataset_id: UUID,
    *,
    name: str = "ds",
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[dataset_id, uuid4()])
    await register_dataset.bind(deps)(
        RegisterDataset(
            name=name,
            uri=f"s3://bucket/{name}",
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA256,
            byte_size=1024,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_edition_dataset_ids_array_updates_through_register_add_remove(
    db_pool: asyncpg.Pool,
) -> None:
    first_dataset = uuid4()
    second_dataset = uuid4()
    edition_id = uuid4()
    event_id = uuid4()

    # Seed two Datasets in Data BC.
    await _register_dataset(db_pool, first_dataset, name="first")
    await _register_dataset(db_pool, second_dataset, name="second")

    # Genesis: register the Edition with first_dataset only.
    register_deps = build_postgres_deps(db_pool, now=_NOW, ids=[edition_id, event_id])
    returned_id = await register_edition.bind(register_deps)(
        RegisterEdition(
            kind="ROCrate",
            title="Lifecycle Test Edition",
            dataset_ids=frozenset({first_dataset}),
            creators=(CreatorEntry(actor_id=uuid4(), affiliation="ANL"),),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == edition_id

    await _drain_data(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT dataset_ids, status FROM proj_data_edition_summary WHERE edition_id = $1",
            edition_id,
        )
    assert row is not None
    assert row["status"] == "Registered"
    assert list(row["dataset_ids"]) == [first_dataset]

    # Add second_dataset.
    add_deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    await add_dataset_to_edition.bind(add_deps)(
        AddDatasetToEdition(edition_id=edition_id, dataset_id=second_dataset),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain_data(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT dataset_ids FROM proj_data_edition_summary WHERE edition_id = $1",
            edition_id,
        )
    assert row is not None
    assert set(row["dataset_ids"]) == {first_dataset, second_dataset}

    # Remove first_dataset, leaving second_dataset.
    remove_deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    await remove_dataset_from_edition.bind(remove_deps)(
        RemoveDatasetFromEdition(edition_id=edition_id, dataset_id=first_dataset),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain_data(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT dataset_ids, status FROM proj_data_edition_summary WHERE edition_id = $1",
            edition_id,
        )
    assert row is not None
    assert row["status"] == "Registered"
    assert list(row["dataset_ids"]) == [second_dataset]

    # Final event-store sanity: 3 events on the Edition stream.
    events, version = await remove_deps.event_store.load("Edition", edition_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "EditionRegistered",
        "EditionDatasetAdded",
        "EditionDatasetRemoved",
    ]
