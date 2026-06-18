"""End-to-end: `list_practices` handler against real Postgres.

Practice carries cross-aggregate refs (method_id + site_id) in
the genesis payload; this test pins both surface in the projection
and that the method_id filter narrows correctly.
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
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.define_practice import bind as bind_define
from cora.recipe.features.deprecate_practice import DeprecatePractice
from cora.recipe.features.deprecate_practice import bind as bind_deprecate
from cora.recipe.features.list_practices import ListPractices
from cora.recipe.features.list_practices import bind as bind_list
from cora.recipe.features.version_practice import VersionPractice
from cora.recipe.features.version_practice import bind as bind_version
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0dec1")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_recipe_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _seed_method(deps: Kernel, name: str = "Tomography") -> UUID:
    """Define a Method (Practice's required upstream) and return its id.
    Practice's decider doesn't verify Method exists (eventual-consistency
    stance), but the integration test still seeds one for realism."""
    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    return await bind_define_method(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH, capability_id=_CAPABILITY_ID, name=name
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_define_emits_defined_status_with_method_and_site_ids(
    db_pool: asyncpg.Pool,
) -> None:
    method_id = uuid4()
    site_id = uuid4()
    practice_id = uuid4()
    deps = _build_deps(db_pool, [method_id, uuid4(), practice_id, uuid4()])
    await _seed_method(deps)
    await bind_define(deps)(
        DefinePractice(name="APS-2BM-CT", method_id=method_id, site_id=site_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT name, method_id, site_id, status, version_tag "
            "FROM proj_recipe_practice_summary WHERE practice_id = $1",
            practice_id,
        )
    assert row is not None
    assert row["name"] == "APS-2BM-CT"
    assert row["method_id"] == method_id
    assert row["site_id"] == site_id
    assert row["status"] == "Defined"
    assert row["version_tag"] is None


@pytest.mark.integration
async def test_method_id_filter_narrows_results(db_pool: asyncpg.Pool) -> None:
    """Two Practices implementing different Methods; the method_id
    filter returns only the one matching."""
    method_a = uuid4()
    method_b = uuid4()
    practice_for_a = uuid4()
    practice_for_b = uuid4()
    site_id = uuid4()
    deps = _build_deps(
        db_pool,
        [
            method_a,
            uuid4(),
            method_b,
            uuid4(),
            practice_for_a,
            uuid4(),
            practice_for_b,
            uuid4(),
        ],
    )
    await _seed_method(deps, name="MethodA")
    await _seed_method(deps, name="MethodB")
    define = bind_define(deps)
    await define(
        DefinePractice(name="ForA", method_id=method_a, site_id=site_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define(
        DefinePractice(name="ForB", method_id=method_b, site_id=site_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)
    handler = bind_list(deps)
    page = await handler(
        ListPractices(method_id=method_a, limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].practice_id == practice_for_a
    assert page.items[0].method_id == method_a


@pytest.mark.integration
async def test_lifecycle_deprecate_preserves_method_and_site(
    db_pool: asyncpg.Pool,
) -> None:
    """Define -> version -> deprecate; method_id, site_id, version_tag
    all preserved through deprecation (audit-trail invariant)."""
    method_id = uuid4()
    site_id = uuid4()
    practice_id = uuid4()
    deps = _build_deps(
        db_pool,
        [method_id, uuid4(), practice_id, uuid4(), uuid4(), uuid4()],
    )
    await _seed_method(deps)
    await bind_define(deps)(
        DefinePractice(name="ToDeprecate", method_id=method_id, site_id=site_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_version(deps)(
        VersionPractice(practice_id=practice_id, version_tag="2026-Q3"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_deprecate(deps)(
        DeprecatePractice(practice_id=practice_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT method_id, site_id, status, version_tag "
            "FROM proj_recipe_practice_summary WHERE practice_id = $1",
            practice_id,
        )
    assert row is not None
    assert row["status"] == "Deprecated"
    assert row["version_tag"] == "2026-Q3"
    assert row["method_id"] == method_id
    assert row["site_id"] == site_id


@pytest.mark.integration
async def test_combined_status_and_method_id_filter(db_pool: asyncpg.Pool) -> None:
    """Pin: the combined-filter SQL path narrows on BOTH status and
    method_id together. Three Practices: Versioned-for-A, Defined-
    for-A, Versioned-for-B. Filter status=Versioned + method_id=A
    returns only the first."""
    method_a = uuid4()
    method_b = uuid4()
    practice_versioned_a = uuid4()
    practice_defined_a = uuid4()
    practice_versioned_b = uuid4()
    site_id = uuid4()
    deps = _build_deps(
        db_pool,
        [
            method_a,
            uuid4(),
            method_b,
            uuid4(),
            practice_versioned_a,
            uuid4(),
            uuid4(),  # version event for practice_versioned_a
            practice_defined_a,
            uuid4(),
            practice_versioned_b,
            uuid4(),
            uuid4(),  # version event for practice_versioned_b
        ],
    )
    await _seed_method(deps, name="MethodA")
    await _seed_method(deps, name="MethodB")
    define = bind_define(deps)
    await define(
        DefinePractice(name="VerForA", method_id=method_a, site_id=site_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_version(deps)(
        VersionPractice(practice_id=practice_versioned_a, version_tag="v1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define(
        DefinePractice(name="DefForA", method_id=method_a, site_id=site_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define(
        DefinePractice(name="VerForB", method_id=method_b, site_id=site_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_version(deps)(
        VersionPractice(practice_id=practice_versioned_b, version_tag="v1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)
    handler = bind_list(deps)
    page = await handler(
        ListPractices(status="Versioned", method_id=method_a, limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].practice_id == practice_versioned_a


@pytest.mark.integration
async def test_empty_table_returns_empty_page(db_pool: asyncpg.Pool) -> None:
    deps = _build_deps(db_pool, [])
    handler = bind_list(deps)
    page = await handler(
        ListPractices(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None
