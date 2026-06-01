"""End-to-end integration test: version_model against real Postgres.

Round-trip: define Family, define Model, version Model, and read the
events back from the event store. Verifies the ModelVersioned payload
shape (sorted declared_families, manufacturer sub-dict, version_tag),
the multi-source guard (ModelNotFoundError on a missing stream), and
the Deprecated rejection (ModelCannotVersionError after appending a
ModelDeprecated event onto the same stream).
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    ModelCannotVersionError,
    ModelDeprecated,
    ModelNotFoundError,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.features import define_family, define_model, version_model
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.version_model import VersionModel
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _drain_equipment_projections(db_pool: asyncpg.Pool) -> None:
    """Flush FamilyDefined into `proj_equipment_family_summary` so the
    Family read repo called by `define_model.handler` sees the seed."""
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_version_model_persists_event_with_full_payload(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy path: seed Family + define Model + version Model. Verify
    ModelVersioned is persisted with the wholesale-replacement payload
    (sorted declared_families, manufacturer sub-dict, version_tag)."""
    family_id = UUID("01900000-0000-7000-8000-00000060d001")
    family_event_id = UUID("01900000-0000-7000-8000-00000060d00e")
    other_family_id = UUID("01900000-0000-7000-8000-00000060d002")
    other_family_event_id = UUID("01900000-0000-7000-8000-00000060d00f")
    model_id = UUID("01900000-0000-7000-8000-00000060ca01")
    define_event_id = UUID("01900000-0000-7000-8000-00000060ca0e")
    version_event_id = UUID("01900000-0000-7000-8000-00000060ca1a")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            family_id,
            family_event_id,
            other_family_id,
            other_family_event_id,
            model_id,
            define_event_id,
            version_event_id,
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
            declared_families=frozenset({family_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await version_model.bind(deps)(
        VersionModel(
            model_id=model_id,
            name="Aerotech ANT130-L rev-B",
            manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
            part_number="ANT130-L-B",
            declared_families=frozenset({family_id, other_family_id}),
            version_tag="2026-Q3",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Model", model_id)
    assert version == 2
    assert [e.event_type for e in events] == ["ModelDefined", "ModelVersioned"]
    versioned = events[1]
    assert versioned.event_id == version_event_id
    assert versioned.metadata == {"command": "VersionModel"}
    assert versioned.payload == {
        "model_id": str(model_id),
        "name": "Aerotech ANT130-L rev-B",
        "manufacturer": {"name": "Aerotech"},
        "part_number": "ANT130-L-B",
        "declared_families": sorted([str(family_id), str(other_family_id)]),
        "version_tag": "2026-Q3",
        "occurred_at": _NOW.isoformat(),
    }

    # State round-trip via fold confirms the wholesale replacement.
    history = [from_stored(s) for s in events]
    state = fold(history)
    assert state is not None
    assert state.name.value == "Aerotech ANT130-L rev-B"
    assert state.part_number.value == "ANT130-L-B"
    assert state.declared_families == frozenset({family_id, other_family_id})
    assert state.version == "2026-Q3"


@pytest.mark.integration
async def test_version_model_raises_not_found_for_unknown_id(
    db_pool: asyncpg.Pool,
) -> None:
    """Versioning a model whose stream has no events raises ModelNotFoundError."""
    missing_id = UUID("01900000-0000-7000-8000-0000000bad02")
    family_id = UUID("01900000-0000-7000-8000-0000000bad03")
    version_event_id = UUID("01900000-0000-7000-8000-0000000bad0e")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[version_event_id])

    with pytest.raises(ModelNotFoundError) as exc_info:
        await version_model.bind(deps)(
            VersionModel(
                model_id=missing_id,
                name="Aerotech ANT130-L",
                manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
                part_number="ANT130-L",
                declared_families=frozenset({family_id}),
                version_tag="v2",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.model_id == missing_id

    _, version = await deps.event_store.load("Model", missing_id)
    assert version == 0


@pytest.mark.integration
async def test_version_model_raises_cannot_version_after_deprecation(
    db_pool: asyncpg.Pool,
) -> None:
    """After appending a ModelDeprecated event, version_model raises
    ModelCannotVersionError and no new event is written."""
    family_id = UUID("01900000-0000-7000-8000-00000060e001")
    family_event_id = UUID("01900000-0000-7000-8000-00000060e00e")
    model_id = UUID("01900000-0000-7000-8000-00000060ca21")
    define_event_id = UUID("01900000-0000-7000-8000-00000060ca2e")
    deprecate_event_id = UUID("01900000-0000-7000-8000-00000060ca2f")
    # The version_model call lands on the disallowed source and rejects
    # before consuming any id; queue an extra to be safe.
    unused_version_event_id = UUID("01900000-0000-7000-8000-00000060ca3a")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            family_id,
            family_event_id,
            model_id,
            define_event_id,
            unused_version_event_id,
        ],
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
            declared_families=frozenset({family_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    deprecated = ModelDeprecated(
        model_id=model_id,
        reason="superseded by next-gen part",
        occurred_at=_NOW,
    )
    await deps.event_store.append(
        stream_type="Model",
        stream_id=model_id,
        expected_version=1,
        events=[
            to_new_event(
                event_type=event_type_name(deprecated),
                payload=to_payload(deprecated),
                occurred_at=deprecated.occurred_at,
                event_id=deprecate_event_id,
                command_name="DeprecateModel",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )

    with pytest.raises(ModelCannotVersionError):
        await version_model.bind(deps)(
            VersionModel(
                model_id=model_id,
                name="Aerotech ANT130-L rev-B",
                manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
                part_number="ANT130-L-B",
                declared_families=frozenset({family_id}),
                version_tag="v2",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    _, version = await deps.event_store.load("Model", model_id)
    assert version == 2
