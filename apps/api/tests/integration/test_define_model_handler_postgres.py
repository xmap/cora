"""End-to-end integration test: define_model handler against real Postgres.

Pinned:
- Happy path: ModelDefined round-trips through jsonb with the
  manufacturer sub-dict, sorted declared_families UUID list, and the
  optional version_tag dropped when None.
- Cross-BC family_lookup: define_model loads the Family read repo
  (`list_family_ids`) against the real `proj_equipment_family_summary`
  projection before invoking the decider, so an unregistered family id
  surfaces `FamilyNotFoundError` (404), and a registered family id
  proceeds to event-write.
- Idempotency: the wired `IdempotentHandler` (`define_model` slice in
  `wire_equipment`) round-trips the Brandur envelope at the storage
  tier: same Idempotency-Key plus same command body returns the same
  model_id without writing a second Model stream.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.family import FamilyNotFoundError
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerIdentifier,
    ManufacturerIdentifierType,
    ManufacturerName,
)
from cora.equipment.features import define_family, define_model
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_model import DefineModel
from cora.equipment.wire import wire_equipment
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _drain_equipment_projections(db_pool: asyncpg.Pool) -> None:
    """Pump the Equipment-owned projections to flush `FamilyDefined`
    rows into `proj_equipment_family_summary`. The Family read repo
    (`list_family_ids`) called by `define_model.handler` queries this
    projection, so an upstream `define_family` write is only visible
    to the next `define_model` after a drain.
    """
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_define_model_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy path: register a Family, define a Model declaring it,
    read the events back from the event store, and verify ModelDefined
    is persisted with the expected payload shape (sorted
    declared_families, no version_tag key when None)."""
    family_id = UUID("01900000-0000-7000-8000-000000054c01")
    family_event_id = UUID("01900000-0000-7000-8000-000000054c0e")
    model_id = UUID("01900000-0000-7000-8000-00000054ca01")
    model_event_id = UUID("01900000-0000-7000-8000-00000054ca0e")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[family_id, family_event_id, model_id, model_event_id],
    )
    await define_family.bind(deps)(
        DefineFamily(name="ContinuousRotationTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_equipment_projections(db_pool)

    returned_id = await define_model.bind(deps)(
        DefineModel(
            name="Aerotech ANT130-L",
            manufacturer=Manufacturer(
                name=ManufacturerName("Aerotech"),
                identifier=ManufacturerIdentifier("https://ror.org/02jbv0t02"),
                identifier_type=ManufacturerIdentifierType.ROR,
            ),
            part_number="ANT130-L",
            declared_families=frozenset({family_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == model_id

    events, version = await deps.event_store.load("Model", model_id)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "ModelDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "model_id": str(model_id),
        "name": "Aerotech ANT130-L",
        "manufacturer": {
            "name": "Aerotech",
            "identifier": "https://ror.org/02jbv0t02",
            "identifier_type": "ROR",
        },
        "part_number": "ANT130-L",
        # Sorted by UUID string form (deterministic). Pinned by
        # tests/unit/equipment/test_model_events.py.
        "declared_families": [str(family_id)],
        # version_tag is omitted from payload when None (per to_payload).
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == model_event_id
    assert stored.metadata == {"command": "DefineModel"}
    assert stored.occurred_at == _NOW


@pytest.mark.integration
async def test_define_model_rejects_unregistered_family_id(
    db_pool: asyncpg.Pool,
) -> None:
    """Cross-BC family_lookup: defining a Model with a Family id that
    has never been registered raises `FamilyNotFoundError`. Real PG
    lookup against `proj_equipment_family_summary`; no Family seeded."""
    model_id = UUID("01900000-0000-7000-8000-00000054ca02")
    model_event_id = UUID("01900000-0000-7000-8000-00000054ca0f")
    missing_family_id = UUID("01900000-0000-7000-8000-0000000bad01")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[model_id, model_event_id])

    with pytest.raises(FamilyNotFoundError) as exc_info:
        await define_model.bind(deps)(
            DefineModel(
                name="Aerotech ANT130-L",
                manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
                part_number="ANT130-L",
                declared_families=frozenset({missing_family_id}),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.family_id == missing_family_id

    # No Model stream was written on the rejected command.
    _, version = await deps.event_store.load("Model", model_id)
    assert version == 0


@pytest.mark.integration
async def test_define_model_proceeds_when_family_is_registered(
    db_pool: asyncpg.Pool,
) -> None:
    """Cross-BC family_lookup success: a Family seeded via
    `define_family` plus a projection drain resolves through
    `list_family_ids`, and `define_model` proceeds to event-write."""
    family_id = UUID("01900000-0000-7000-8000-000000054d01")
    family_event_id = UUID("01900000-0000-7000-8000-000000054d0e")
    model_id = UUID("01900000-0000-7000-8000-00000054ca03")
    model_event_id = UUID("01900000-0000-7000-8000-00000054ca1a")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[family_id, family_event_id, model_id, model_event_id],
    )
    await define_family.bind(deps)(
        DefineFamily(name="ContinuousRotationTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_equipment_projections(db_pool)

    returned_id = await define_model.bind(deps)(
        DefineModel(
            name="Aerotech ANT130-L",
            manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
            part_number="ANT130-L",
            declared_families=frozenset({family_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == model_id

    events, version = await deps.event_store.load("Model", model_id)
    assert version == 1
    assert events[0].event_type == "ModelDefined"
    assert events[0].payload["declared_families"] == [str(family_id)]


@pytest.mark.integration
async def test_define_model_idempotency_key_replay_returns_same_model_id(
    db_pool: asyncpg.Pool,
) -> None:
    """Same Idempotency-Key plus same command body returns the same
    model_id without writing a second Model stream. Storage-cardinality
    pin against the Brandur cache-miss regression class."""
    family_id = UUID("01900000-0000-7000-8000-000000054e01")
    family_event_id = UUID("01900000-0000-7000-8000-000000054e0e")
    first_model_id = UUID("01900000-0000-7000-8000-00000054ca21")
    first_event_id = UUID("01900000-0000-7000-8000-00000054ca2e")
    # The second model_id is queued but never consumed: the Brandur
    # cache hit short-circuits before `id_generator.new_id()` runs on
    # the replay. The id sits unclaimed at the end of the test.
    unused_replay_model_id = UUID("01900000-0000-7000-8000-00000054ca31")
    unused_replay_event_id = UUID("01900000-0000-7000-8000-00000054ca3e")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            family_id,
            family_event_id,
            first_model_id,
            first_event_id,
            unused_replay_model_id,
            unused_replay_event_id,
        ],
    )
    await define_family.bind(deps)(
        DefineFamily(name="ContinuousRotationTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_equipment_projections(db_pool)

    handler = wire_equipment(deps).define_model
    idempotency_key = f"ck-define-model-{uuid4().hex[:8]}"
    cmd = DefineModel(
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_families=frozenset({family_id}),
    )

    first_id = await handler(
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key=idempotency_key,
    )
    second_id = await handler(
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key=idempotency_key,
    )

    # Same model_id replayed via Brandur cache.
    assert first_id == second_id
    assert first_id == first_model_id

    # Exactly one Model stream exists, with exactly one ModelDefined event.
    _, version = await deps.event_store.load("Model", first_model_id)
    assert version == 1
    # The "second" queued model_id was never written.
    _, second_version = await deps.event_store.load("Model", unused_replay_model_id)
    assert second_version == 0
