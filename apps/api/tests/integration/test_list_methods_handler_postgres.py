"""End-to-end: `list_methods` handler against real Postgres
projection table. Same shape as `list_families` (3 lifecycle
events, 3 statuses, version_tag preserved through deprecation).

Drains all three Recipe projections (Method + Practice + Plan are
co-registered via register_recipe_projections), so this test also
exercises the multi-projection-per-BC drain semantics under the
"only one projection has subscribed events" path.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe._projections import register_recipe_projections
from cora.recipe.aggregates.method import ExecutionPattern
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define
from cora.recipe.features.deprecate_method import DeprecateMethod
from cora.recipe.features.deprecate_method import bind as bind_deprecate
from cora.recipe.features.list_methods import ListMethods
from cora.recipe.features.list_methods import bind as bind_list
from cora.recipe.features.version_method import VersionMethod
from cora.recipe.features.version_method import bind as bind_version
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000000c1de")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _build_seeded_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    """Every define_method needs a real Capability stream. Seed once
    per test via this helper to avoid repeating the boilerplate."""
    deps = _build_deps(db_pool, ids)
    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    return deps


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_recipe_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_define_emits_defined_status_with_null_version_tag(
    db_pool: asyncpg.Pool,
) -> None:
    method_id = uuid4()
    deps = await _build_seeded_deps(db_pool, [method_id, uuid4()])
    await bind_define(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="Continuous Rotation Tomography",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT name, status, version_tag FROM proj_recipe_method_summary WHERE method_id = $1",
            method_id,
        )
    assert row is not None
    assert row["name"] == "Continuous Rotation Tomography"
    assert row["status"] == "Defined"
    assert row["version_tag"] is None


@pytest.mark.integration
async def test_full_lifecycle_define_version_deprecate(db_pool: asyncpg.Pool) -> None:
    """Define -> version -> deprecate; status flips through and
    version_tag is preserved on deprecate."""
    method_id = uuid4()
    deps = _build_deps(db_pool, [method_id, uuid4(), uuid4(), uuid4()])
    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    await bind_define(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="Powder Diffraction",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_version(deps)(
        VersionMethod(method_id=method_id, version_tag="v2.1.0"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_deprecate(deps)(
        DeprecateMethod(method_id=method_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, version_tag FROM proj_recipe_method_summary WHERE method_id = $1",
            method_id,
        )
    assert row is not None
    assert row["status"] == "Deprecated"
    assert row["version_tag"] == "v2.1.0"


@pytest.mark.integration
async def test_status_filter_returns_only_matching_rows(db_pool: asyncpg.Pool) -> None:
    defined_id = uuid4()
    versioned_id = uuid4()
    deps = _build_deps(
        db_pool,
        [defined_id, uuid4(), versioned_id, uuid4(), uuid4()],
    )
    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    define = bind_define(deps)
    await define(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="DefinedOnly",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="ToBeVersioned",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_version(deps)(
        VersionMethod(method_id=versioned_id, version_tag="v1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)
    handler = bind_list(deps)
    page = await handler(
        ListMethods(status="Versioned", limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].method_id == versioned_id


@pytest.mark.integration
async def test_cursor_walks_pages(db_pool: asyncpg.Pool) -> None:
    method_ids: list[UUID] = []
    fixed_ids: list[UUID] = []
    for _ in range(5):
        m = uuid4()
        method_ids.append(m)
        fixed_ids.extend([m, uuid4()])
    deps = _build_deps(db_pool, fixed_ids)
    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    define = bind_define(deps)
    for i in range(5):
        await define(
            DefineMethod(
                execution_pattern=ExecutionPattern.BATCH,
                capability_id=_CAPABILITY_ID,
                name=f"Method{i:02d}",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    await _drain(db_pool)
    handler = bind_list(deps)
    page1 = await handler(
        ListMethods(limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    page2 = await handler(
        ListMethods(cursor=page1.next_cursor, limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    page3 = await handler(
        ListMethods(cursor=page2.next_cursor, limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page1.items) == 2 and page1.next_cursor is not None
    assert len(page2.items) == 2 and page2.next_cursor is not None
    assert len(page3.items) == 1 and page3.next_cursor is None
    seen = {item.method_id for p in (page1, page2, page3) for item in p.items}
    assert seen == set(method_ids)


@pytest.mark.integration
async def test_empty_table_returns_empty_page(db_pool: asyncpg.Pool) -> None:
    deps = _build_deps(db_pool, [])
    handler = bind_list(deps)
    page = await handler(
        ListMethods(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None
