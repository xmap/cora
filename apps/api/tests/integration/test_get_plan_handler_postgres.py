"""Integration test: get_plan handler against real Postgres.

Exercises (1) the fold-on-read state path, and (2) the Path C
projection-sourced lifecycle-timestamps path
. Pre-drain assertion confirms timestamps
are None when the projection hasn't caught up; post-drain assertion
confirms `created_at` populates after `PlanSummaryProjection` folds
`PlanDefined`. Mirrors `test_get_method_handler_postgres.py`.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe._projections import register_recipe_projections
from cora.recipe.aggregates.plan import PlanStatus
from cora.recipe.features import get_plan
from cora.recipe.features.get_plan import GetPlan
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps, seed_run_upstream_chain_postgres

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_get_plan_loads_state_and_timestamps_from_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    plan_id, _subject_id = await seed_run_upstream_chain_postgres(db_pool, now=_NOW)

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[])
    view = await get_plan.bind(deps)(
        GetPlan(plan_id=plan_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.plan.id == plan_id
    assert view.plan.status is PlanStatus.DEFINED
    # Pre-drain: projection hasn't folded PlanDefined yet -> no row.
    assert view.timestamps is None

    # Post-drain: projection catches up, lifecycle-timestamps surface.
    registry = ProjectionRegistry()
    register_recipe_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())

    view = await get_plan.bind(deps)(
        GetPlan(plan_id=plan_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is not None
    assert view.timestamps is not None
    assert view.timestamps.created_at == _NOW
    assert view.timestamps.versioned_at is None
    assert view.timestamps.deprecated_at is None
