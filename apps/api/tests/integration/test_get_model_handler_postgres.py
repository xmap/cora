"""Integration test: get_model handler against real Postgres.

End-to-end: seed a Family + define a Model declaring it + version the
Model + add a second Family via add_model_family + GET back. Verifies
the handler folds the full event-stream history (Defined + Versioned
+ FamilyAdded) and returns the post-mutation Model state.

Projection-row contents are NOT verified here (that's the projection
unit test's job). The GET endpoint loads via the event-store fold,
not the projection; this test pins that fold path against real
Postgres.
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
    ModelName,
    ModelStatus,
    PartNumber,
    model_stream_id,
)
from cora.equipment.features import (
    add_model_family,
    define_family,
    define_model,
    get_model,
    version_model,
)
from cora.equipment.features.add_model_family import AddModelFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.get_model import GetModel
from cora.equipment.features.version_model import VersionModel
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
async def test_get_model_loads_full_history_from_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed Family A + Family B, define Model declaring A, version
    Model (wholesale identity replace), then add Family B via the
    targeted-mutation slice. GET returns the post-mutation state: the
    Versioned identity block plus the appended family."""
    family_a_id = family_stream_id(FamilyName("ContinuousRotationTomography"))
    family_a_event_id = UUID("01900000-0000-7000-8000-00000063d00e")
    family_b_id = family_stream_id(FamilyName("StepScanTomography"))
    family_b_event_id = UUID("01900000-0000-7000-8000-00000063d00f")
    model_fallback_id = UUID("01900000-0000-7000-8000-00000063ca01")
    define_event_id = UUID("01900000-0000-7000-8000-00000063ca0e")
    versioned_event_id = UUID("01900000-0000-7000-8000-00000063ca1a")
    added_event_id = UUID("01900000-0000-7000-8000-00000063ca2b")
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
            versioned_event_id,
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

    await version_model.bind(deps)(
        VersionModel(
            model_id=model_id,
            name="Aerotech ANT130-LZS",
            manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
            part_number="ANT130-LZS",
            declared_family_ids=frozenset({family_a_id}),
            version_tag="v2",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await add_model_family.bind(deps)(
        AddModelFamily(model_id=model_id, family_id=family_b_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    model = await get_model.bind(deps)(
        GetModel(model_id=model_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert model is not None
    assert model.id == model_id
    # Versioned identity block (replaced wholesale on version_model).
    assert model.name == ModelName("Aerotech ANT130-LZS")
    assert model.part_number == PartNumber("ANT130-LZS")
    assert model.status is ModelStatus.VERSIONED
    assert model.version == "v2"
    # Family B was appended via add_model_family after the version.
    assert model.declared_family_ids == frozenset({family_a_id, family_b_id})


@pytest.mark.integration
async def test_get_model_returns_none_for_unknown_id_against_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Missing stream against real PG event store folds to None."""
    missing_model_id = UUID("01900000-0000-7000-8000-00000063bad9")
    deps = build_postgres_deps(db_pool, now=_NOW)

    model = await get_model.bind(deps)(
        GetModel(model_id=missing_model_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert model is None
