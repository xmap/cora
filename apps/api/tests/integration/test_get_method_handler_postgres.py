"""Integration test: get_method handler against real Postgres.

Exercises (1) the fold-on-read state path, and (2) the Path C
projection-sourced lifecycle-timestamps path
. Pre-drain assertion confirms timestamps
are None when the projection hasn't caught up; post-drain assertion
confirms `created_at` populates after `MethodSummaryProjection`
folds `MethodDefined`.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe._projections import register_recipe_projections
from cora.recipe.aggregates.method import ExecutionPattern, MethodName, MethodStatus
from cora.recipe.features import define_method, get_method
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.get_method import GetMethod
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000056ef0c")


@pytest.mark.integration
async def test_get_method_loads_state_from_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    method_id = UUID("01900000-0000-7000-8000-00000056ef01")
    event_id = UUID("01900000-0000-7000-8000-00000056ef0e")
    cap1 = UUID("01900000-0000-7000-8000-000000000111")
    cap2 = UUID("01900000-0000-7000-8000-000000000222")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[method_id, event_id])
    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)

    await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            name="XRF Fly Mapping",
            capability_id=_CAPABILITY_ID,
            needed_family_ids=frozenset({cap1, cap2}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    view = await get_method.bind(deps)(
        GetMethod(method_id=method_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.method.id == method_id
    assert view.method.name == MethodName("XRF Fly Mapping")
    assert view.method.needed_family_ids == frozenset({cap1, cap2})
    assert view.method.status is MethodStatus.DEFINED
    # Pre-drain: projection hasn't folded MethodDefined yet -> no row.
    assert view.timestamps is None

    # Post-drain: projection catches up, lifecycle-timestamps surface.
    registry = ProjectionRegistry()
    register_recipe_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    view = await get_method.bind(deps)(
        GetMethod(method_id=method_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is not None
    assert view.timestamps is not None
    assert view.timestamps.created_at == _NOW
    assert view.timestamps.versioned_at is None
    assert view.timestamps.deprecated_at is None
