"""Integration test: get_family handler against real Postgres.

Path C: handler returns FamilyView
bundling aggregate state + projection-sourced lifecycle timestamps.
Exercises both pre-drain (timestamps None) and post-drain (timestamps
populated) paths.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.family import FamilyName, FamilyStatus, family_stream_id
from cora.equipment.features import define_family, get_family
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.get_family import GetFamily
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_CAPABILITY_ID = family_stream_id(FamilyName("X-ray Fluorescence Mapping"))
_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cb0e")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_get_family_loads_state_from_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_EVENT_ID])

    await define_family.bind(deps)(
        DefineFamily(name="X-ray Fluorescence Mapping", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    view = await get_family.bind(deps)(
        GetFamily(family_id=_CAPABILITY_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.family.id == _CAPABILITY_ID
    assert view.family.name == FamilyName("X-ray Fluorescence Mapping")
    assert view.family.status is FamilyStatus.DEFINED
    # Pre-drain: projection hasn't folded FamilyDefined yet -> no row.
    assert view.timestamps is None

    # Post-drain: projection catches up, lifecycle-timestamps surface.
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    view = await get_family.bind(deps)(
        GetFamily(family_id=_CAPABILITY_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is not None
    assert view.timestamps is not None
    assert view.timestamps.created_at == _NOW
    assert view.timestamps.versioned_at is None
    assert view.timestamps.deprecated_at is None
