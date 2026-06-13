"""End-to-end integration test: add_model_family against real Postgres.

Round-trip: define Families, define Model, add a second Family to the
Model's declared_family_ids set, and read the events back from the event
store. Verifies the ModelFamilyAdded payload shape, the cross-BC
`list_family_ids` lookup against the real `proj_equipment_family_summary`
projection (404 path on a missing Family id), and the
strict-not-idempotent guard (re-adding a present family raises).
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.family import (
    FamilyName,
    FamilyNotFoundError,
    family_stream_id,
)
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    ModelFamilyAlreadyPresentError,
    PartNumber,
    fold,
    from_stored,
    model_stream_id,
)
from cora.equipment.features import (
    add_model_family,
    define_family,
    define_model,
    deprecate_family,
)
from cora.equipment.features.add_model_family import AddModelFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.deprecate_family import DeprecateFamily
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _drain_equipment_projections(db_pool: asyncpg.Pool) -> None:
    """Flush FamilyDefined rows into `proj_equipment_family_summary` so
    the Family read repo called by `add_model_family.handler` sees the
    seed."""
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_add_model_family_persists_event_with_payload(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy path: seed two Families, define a Model declaring one,
    add the other via add_model_family. Verify ModelFamilyAdded is
    persisted with the expected payload shape and fold reflects the
    expanded declared_family_ids set."""
    family_a_id = family_stream_id(FamilyName("ContinuousRotationTomography"))
    family_a_event_id = UUID("01900000-0000-7000-8000-00000061d00e")
    family_b_id = family_stream_id(FamilyName("StepScanTomography"))
    family_b_event_id = UUID("01900000-0000-7000-8000-00000061d00f")
    model_fallback_id = UUID("01900000-0000-7000-8000-00000061ca01")
    define_event_id = UUID("01900000-0000-7000-8000-00000061ca0e")
    added_event_id = UUID("01900000-0000-7000-8000-00000061ca1a")
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

    events, version = await deps.event_store.load("Model", model_id)
    assert version == 2
    assert [e.event_type for e in events] == ["ModelDefined", "ModelFamilyAdded"]
    added = events[1]
    assert added.event_id == added_event_id
    assert added.metadata == {"command": "AddModelFamily"}
    assert added.payload == {
        "model_id": str(model_id),
        "family_id": str(family_b_id),
        "occurred_at": _NOW.isoformat(),
    }

    # State round-trip via fold confirms the targeted mutation.
    history = [from_stored(s) for s in events]
    state = fold(history)
    assert state is not None
    assert state.declared_family_ids == frozenset({family_a_id, family_b_id})


@pytest.mark.integration
async def test_add_model_family_rejects_unregistered_family_id(
    db_pool: asyncpg.Pool,
) -> None:
    """Cross-BC family_lookup: adding a Family that has never been
    registered raises `FamilyNotFoundError` before the decider sees the
    command. Real PG lookup against `proj_equipment_family_summary`."""
    family_id = family_stream_id(FamilyName("ContinuousRotationTomography"))
    family_event_id = UUID("01900000-0000-7000-8000-00000061e00e")
    model_fallback_id = UUID("01900000-0000-7000-8000-00000061ca21")
    define_event_id = UUID("01900000-0000-7000-8000-00000061ca2e")
    # The add_model_family call rejects before consuming any id; queue
    # an extra to be safe.
    unused_add_event_id = UUID("01900000-0000-7000-8000-00000061ca3a")
    missing_family_id = UUID("01900000-0000-7000-8000-0000000bad21")
    model_id = model_stream_id(
        Manufacturer(name=ManufacturerName("Aerotech")),
        PartNumber("ANT130-L"),
        new_id=UUID(int=0),
    )

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[family_event_id, model_fallback_id, define_event_id, unused_add_event_id],
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

    with pytest.raises(FamilyNotFoundError) as exc_info:
        await add_model_family.bind(deps)(
            AddModelFamily(model_id=model_id, family_id=missing_family_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.family_id == missing_family_id

    # No new event was written on the rejected command.
    _, version = await deps.event_store.load("Model", model_id)
    assert version == 1


@pytest.mark.integration
async def test_add_model_family_rejects_duplicate_family(
    db_pool: asyncpg.Pool,
) -> None:
    """Strict-not-idempotent: re-adding a family already in
    declared_family_ids raises `ModelFamilyAlreadyPresentError` and writes
    no new event."""
    family_id = family_stream_id(FamilyName("ContinuousRotationTomography"))
    family_event_id = UUID("01900000-0000-7000-8000-00000061f00e")
    model_fallback_id = UUID("01900000-0000-7000-8000-00000061ca41")
    define_event_id = UUID("01900000-0000-7000-8000-00000061ca4e")
    unused_add_event_id = UUID("01900000-0000-7000-8000-00000061ca5a")
    model_id = model_stream_id(
        Manufacturer(name=ManufacturerName("Aerotech")),
        PartNumber("ANT130-L"),
        new_id=UUID(int=0),
    )

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[family_event_id, model_fallback_id, define_event_id, unused_add_event_id],
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

    with pytest.raises(ModelFamilyAlreadyPresentError) as exc_info:
        await add_model_family.bind(deps)(
            AddModelFamily(model_id=model_id, family_id=family_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.model_id == model_id
    assert exc_info.value.family_id == family_id

    _, version = await deps.event_store.load("Model", model_id)
    assert version == 1


@pytest.mark.integration
async def test_add_model_family_succeeds_when_family_is_deprecated(
    db_pool: asyncpg.Pool,
) -> None:
    """Family.deprecation is an authoring signal NOT a runtime gate
    per the Model aggregate's design memo. Seed two Families, deprecate
    the second, define a Model declaring only the first, then add the
    deprecated Family. The handler's cross-BC lookup goes through
    `list_all_family_ids` which INCLUDES Deprecated rows, so the call
    proceeds to event-write without raising `FamilyNotFoundError`."""
    family_a_id = family_stream_id(FamilyName("ContinuousRotationTomography"))
    family_a_event_id = UUID("01900000-0000-7000-8000-00000062d00e")
    family_b_id = family_stream_id(FamilyName("LegacyStepScan"))
    family_b_event_id = UUID("01900000-0000-7000-8000-00000062d00f")
    family_b_deprecate_event_id = UUID("01900000-0000-7000-8000-00000062d01a")
    model_fallback_id = UUID("01900000-0000-7000-8000-00000062ca01")
    define_event_id = UUID("01900000-0000-7000-8000-00000062ca0e")
    added_event_id = UUID("01900000-0000-7000-8000-00000062ca1a")
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
            family_b_deprecate_event_id,
            model_fallback_id,
            define_event_id,
            added_event_id,
        ],
    )
    await define_family.bind(deps)(
        DefineFamily(name="ContinuousRotationTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_family.bind(deps)(
        DefineFamily(name="LegacyStepScan", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await deprecate_family.bind(deps)(
        DeprecateFamily(family_id=family_b_id),
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

    events, version = await deps.event_store.load("Model", model_id)
    assert version == 2
    assert [e.event_type for e in events] == ["ModelDefined", "ModelFamilyAdded"]
    added = events[1]
    assert added.payload == {
        "model_id": str(model_id),
        "family_id": str(family_b_id),
        "occurred_at": _NOW.isoformat(),
    }

    history = [from_stored(s) for s in events]
    state = fold(history)
    assert state is not None
    assert state.declared_family_ids == frozenset({family_a_id, family_b_id})
