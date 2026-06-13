"""End-to-end integration test: remove_model_family against real Postgres.

Round-trip: define a Family, define a Model declaring it, add a second
Family to the Model, remove one of them, and read the events back from
the event store. Verifies the ModelFamilyRemoved payload shape and
the strict-not-idempotent guard (removing an absent family raises).

Unlike `add_model_family`, this slice performs NO cross-BC Family
lookup; the only cross-BC seeding still required is via
`define_model` (and `add_model_family`) which DO call
`list_family_ids`. Those calls hit the real
`proj_equipment_family_summary` projection backed by the
`db_pool` fixture.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    ModelFamilyNotPresentError,
    PartNumber,
    fold,
    from_stored,
    model_stream_id,
)
from cora.equipment.features import (
    add_model_family,
    define_family,
    define_model,
    remove_model_family,
)
from cora.equipment.features.add_model_family import AddModelFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.remove_model_family import RemoveModelFamily
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _drain_equipment_projections(db_pool: asyncpg.Pool) -> None:
    """Flush FamilyDefined rows into `proj_equipment_family_summary` so
    the Family read repo called by `define_model.handler` and
    `add_model_family.handler` sees the seed."""
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_remove_model_family_persists_event_with_payload(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy path: seed two Families, define a Model declaring one,
    add the other via add_model_family, then remove the second one via
    remove_model_family. Verify ModelFamilyRemoved is persisted with
    the expected payload shape and fold reflects the contracted
    declared_family_ids set."""
    family_a_id = family_stream_id(FamilyName("ContinuousRotationTomography"))
    family_a_event_id = UUID("01900000-0000-7000-8000-00000062d00e")
    family_b_id = family_stream_id(FamilyName("StepScanTomography"))
    family_b_event_id = UUID("01900000-0000-7000-8000-00000062d00f")
    model_fallback_id = UUID("01900000-0000-7000-8000-00000062ca01")
    define_event_id = UUID("01900000-0000-7000-8000-00000062ca0e")
    added_event_id = UUID("01900000-0000-7000-8000-00000062ca1a")
    removed_event_id = UUID("01900000-0000-7000-8000-00000062ca2a")
    model_id = model_stream_id(
        Manufacturer(name=ManufacturerName("Aerotech")),
        PartNumber("ANT130-L"),
        new_id=UUID(int=0),
    )

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            family_a_event_id,
            family_b_event_id,
            model_fallback_id,
            define_event_id,
            added_event_id,
            removed_event_id,
        ],
    )
    await define_family.bind(deps)(
        DefineFamily(name="ContinuousRotationTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_family.bind(deps)(
        DefineFamily(name="StepScanTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_equipment_projections(db_pool)

    await define_model.bind(deps)(
        DefineModel(
            name="Aerotech ANT130-L",
            manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
            part_number="ANT130-L",
            declared_family_ids=frozenset({family_a_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await add_model_family.bind(deps)(
        AddModelFamily(model_id=model_id, family_id=family_b_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await remove_model_family.bind(deps)(
        RemoveModelFamily(model_id=model_id, family_id=family_b_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Model", model_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "ModelDefined",
        "ModelFamilyAdded",
        "ModelFamilyRemoved",
    ]
    removed = events[2]
    assert removed.event_id == removed_event_id
    assert removed.metadata == {"command": "RemoveModelFamily"}
    assert removed.payload == {
        "model_id": str(model_id),
        "family_id": str(family_b_id),
        "occurred_at": _NOW.isoformat(),
    }

    # State round-trip via fold confirms the targeted mutation.
    history = [from_stored(s) for s in events]
    state = fold(history)
    assert state is not None
    assert state.declared_family_ids == frozenset({family_a_id})


@pytest.mark.integration
async def test_remove_model_family_rejects_absent_family(
    db_pool: asyncpg.Pool,
) -> None:
    """Strict-not-idempotent: removing a family not in declared_family_ids
    raises `ModelFamilyNotPresentError` and writes no new event. No
    cross-BC Family lookup is performed by the slice; the absent
    family_id is rejected purely by the decider against the folded
    state."""
    family_id = family_stream_id(FamilyName("ContinuousRotationTomography"))
    family_event_id = UUID("01900000-0000-7000-8000-00000062f00e")
    model_fallback_id = UUID("01900000-0000-7000-8000-00000062ca41")
    define_event_id = UUID("01900000-0000-7000-8000-00000062ca4e")
    unused_remove_event_id = UUID("01900000-0000-7000-8000-00000062ca5a")
    absent_family_id = UUID("01900000-0000-7000-8000-0000000bad42")
    model_id = model_stream_id(
        Manufacturer(name=ManufacturerName("Aerotech")),
        PartNumber("ANT130-L"),
        new_id=UUID(int=0),
    )

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[family_event_id, model_fallback_id, define_event_id, unused_remove_event_id],
    )
    await define_family.bind(deps)(
        DefineFamily(name="ContinuousRotationTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_equipment_projections(db_pool)

    await define_model.bind(deps)(
        DefineModel(
            name="Aerotech ANT130-L",
            manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
            part_number="ANT130-L",
            declared_family_ids=frozenset({family_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    with pytest.raises(ModelFamilyNotPresentError) as exc_info:
        await remove_model_family.bind(deps)(
            RemoveModelFamily(model_id=model_id, family_id=absent_family_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.model_id == model_id
    assert exc_info.value.family_id == absent_family_id

    _, version = await deps.event_store.load("Model", model_id)
    assert version == 1
