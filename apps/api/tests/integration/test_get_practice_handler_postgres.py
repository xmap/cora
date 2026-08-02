"""Integration test: get_practice handler against real Postgres.

Path C: handler returns PracticeView
bundling aggregate state + projection-sourced lifecycle timestamps.
Mirrors test_get_method_handler_postgres + test_get_plan_handler_postgres
shape; exercises both pre-drain (timestamps None) and post-drain
(timestamps populated) paths.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe._projections import register_recipe_projections
from cora.recipe.aggregates.practice import PracticeName, PracticeStatus
from cora.recipe.features import define_practice, get_practice
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.get_practice import GetPractice
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_get_practice_loads_state_from_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    practice_id = UUID("01900000-0000-7000-8000-00000059ee01")
    event_id = UUID("01900000-0000-7000-8000-00000059ee0e")
    method_id = UUID("01900000-0000-7000-8000-000000000333")
    site_id = UUID("01900000-0000-7000-8000-000000000444")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[practice_id, event_id])

    await define_practice.bind(deps)(
        DefinePractice(
            name="APS Standard Tomography",
            method_id=method_id,
            site_id=site_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    view = await get_practice.bind(deps)(
        GetPractice(practice_id=practice_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.practice.id == practice_id
    assert view.practice.name == PracticeName("APS Standard Tomography")
    assert view.practice.method_id == method_id
    assert view.practice.site_id == site_id
    assert view.practice.status is PracticeStatus.DEFINED
    assert view.practice.version is None
    # Pre-drain: projection hasn't folded PracticeDefined yet -> no row.
    assert view.timestamps is None

    # Post-drain: projection catches up, lifecycle-timestamps surface.
    registry = ProjectionRegistry()
    register_recipe_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())

    view = await get_practice.bind(deps)(
        GetPractice(practice_id=practice_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is not None
    assert view.timestamps is not None
    assert view.timestamps.created_at == _NOW
    assert view.timestamps.versioned_at is None
    assert view.timestamps.deprecated_at is None
