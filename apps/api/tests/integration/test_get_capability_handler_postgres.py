"""Integration test: get_capability handler against real Postgres.

Path C: handler returns
CapabilityView bundling aggregate state + projection-sourced lifecycle
timestamps. Exercises both pre-drain (timestamps None) and post-drain
(timestamps populated) paths.

Mirrors test_get_method/plan/practice/family_handler_postgres.py shape.
Separate from test_capability_end_to_end_postgres.py, which exercises the
full Capability/Family/Asset/Method/Plan/Procedure pipeline but does
not isolate the projection-lag behavior of get_capability.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe._projections import register_recipe_projections
from cora.recipe.aggregates.capability import (
    CapabilityCode,
    CapabilityName,
    CapabilityStatus,
    ExecutorShape,
)
from cora.recipe.features import define_capability, get_capability
from cora.recipe.features.define_capability import DefineCapability
from cora.recipe.features.get_capability import GetCapability
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_get_capability_loads_state_from_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    capability_id = UUID("01900000-0000-7000-8000-00000060bc01")
    event_id = UUID("01900000-0000-7000-8000-00000060bc0e")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[capability_id, event_id])

    await define_capability.bind(deps)(
        DefineCapability(
            code="cora.capability.iter_b_4_test",
            name="IterB4Test",
            required_affordances=frozenset(),
            executor_shapes=frozenset({ExecutorShape.METHOD}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    view = await get_capability.bind(deps)(
        GetCapability(capability_id=capability_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.capability.id == capability_id
    assert view.capability.code == CapabilityCode("cora.capability.iter_b_4_test")
    assert view.capability.name == CapabilityName("IterB4Test")
    assert view.capability.status is CapabilityStatus.DEFINED
    # Pre-drain: projection hasn't folded CapabilityDefined yet -> no row.
    assert view.timestamps is None

    # Post-drain: projection catches up, lifecycle-timestamps surface.
    registry = ProjectionRegistry()
    register_recipe_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())

    view = await get_capability.bind(deps)(
        GetCapability(capability_id=capability_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is not None
    assert view.timestamps is not None
    assert view.timestamps.created_at == _NOW
    assert view.timestamps.versioned_at is None
    assert view.timestamps.deprecated_at is None
