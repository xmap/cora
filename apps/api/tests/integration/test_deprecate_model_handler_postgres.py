"""End-to-end integration test: deprecate_model against real Postgres.

Round-trip: define Family, define Model, deprecate Model, and read the
events back from the event store. Verifies the ModelDeprecated payload
shape (model_id, trimmed reason, occurred_at), the multi-source guard
(ModelNotFoundError on a missing stream), and the strict-not-idempotent
re-deprecate rejection (ModelCannotDeprecateError).
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    ModelCannotDeprecateError,
    ModelNotFoundError,
    ModelStatus,
    fold,
    from_stored,
)
from cora.equipment.features import define_family, define_model, deprecate_model
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.deprecate_model import DeprecateModel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_REASON = "Vendor end-of-life 2026-Q3"


async def _drain_equipment_projections(db_pool: asyncpg.Pool) -> None:
    """Flush FamilyDefined into `proj_equipment_family_summary` so the
    Family read repo called by `define_model.handler` sees the seed."""
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_deprecate_model_persists_event_with_full_payload(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy path: seed Family + define Model + deprecate Model. Verify
    ModelDeprecated is persisted with the trimmed reason payload and the
    state folds to Deprecated."""
    family_id = UUID("01900000-0000-7000-8000-00000061d001")
    family_event_id = UUID("01900000-0000-7000-8000-00000061d00e")
    model_id = UUID("01900000-0000-7000-8000-00000061ca01")
    define_event_id = UUID("01900000-0000-7000-8000-00000061ca0e")
    deprecate_event_id = UUID("01900000-0000-7000-8000-00000061ca1a")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            family_id,
            family_event_id,
            model_id,
            define_event_id,
            deprecate_event_id,
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

    await deprecate_model.bind(deps)(
        DeprecateModel(model_id=model_id, reason=_REASON),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Model", model_id)
    assert version == 2
    assert [e.event_type for e in events] == ["ModelDefined", "ModelDeprecated"]
    deprecated = events[1]
    assert deprecated.event_id == deprecate_event_id
    assert deprecated.metadata == {"command": "DeprecateModel"}
    assert deprecated.payload == {
        "model_id": str(model_id),
        "reason": _REASON,
        "occurred_at": _NOW.isoformat(),
    }

    # State round-trip via fold confirms the Deprecated status.
    history = [from_stored(s) for s in events]
    state = fold(history)
    assert state is not None
    assert state.status is ModelStatus.DEPRECATED


@pytest.mark.integration
async def test_deprecate_model_raises_not_found_for_unknown_id(
    db_pool: asyncpg.Pool,
) -> None:
    """Deprecating a model whose stream has no events raises ModelNotFoundError."""
    missing_id = UUID("01900000-0000-7000-8000-0000000bad12")
    deprecate_event_id = UUID("01900000-0000-7000-8000-0000000bad1e")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[deprecate_event_id])

    with pytest.raises(ModelNotFoundError) as exc_info:
        await deprecate_model.bind(deps)(
            DeprecateModel(model_id=missing_id, reason=_REASON),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.model_id == missing_id

    _, version = await deps.event_store.load("Model", missing_id)
    assert version == 0


@pytest.mark.integration
async def test_deprecate_model_raises_cannot_deprecate_after_first_deprecation(
    db_pool: asyncpg.Pool,
) -> None:
    """Strict-not-idempotent: re-deprecating raises ModelCannotDeprecateError
    and no new event is written."""
    family_id = UUID("01900000-0000-7000-8000-00000061e001")
    family_event_id = UUID("01900000-0000-7000-8000-00000061e00e")
    model_id = UUID("01900000-0000-7000-8000-00000061ca21")
    define_event_id = UUID("01900000-0000-7000-8000-00000061ca2e")
    deprecate_event_id = UUID("01900000-0000-7000-8000-00000061ca2f")
    # The second deprecate_model call lands on the disallowed source and
    # rejects before consuming any id; queue an extra to be safe.
    unused_event_id = UUID("01900000-0000-7000-8000-00000061ca3a")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            family_id,
            family_event_id,
            model_id,
            define_event_id,
            deprecate_event_id,
            unused_event_id,
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

    await deprecate_model.bind(deps)(
        DeprecateModel(model_id=model_id, reason=_REASON),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    with pytest.raises(ModelCannotDeprecateError):
        await deprecate_model.bind(deps)(
            DeprecateModel(model_id=model_id, reason="another reason"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    _, version = await deps.event_store.load("Model", model_id)
    assert version == 2
