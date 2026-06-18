"""End-to-end: `list_plans` handler against real Postgres.

Plan binding requires a chain of upstream events: Family, Asset
(with that Family added), Method (needing the Family), and
Practice (referencing the Method). This test seeds the chain via a
helper, then pins that the projection surfaces practice_id +
method_id and that the practice_id filter works.

The Equipment and Recipe projections are co-registered via their
respective register_<bc>_projections helpers; the drain helper's
per-projection subscribed-head semantics (8e-3b) handles the
Equipment-side projection bookmarks not advancing when only Recipe
events are emitted, and vice versa.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import bind as bind_add_family
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe._projections import register_recipe_projections
from cora.recipe.aggregates.method import ExecutionPattern
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_plan import bind as bind_define
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.define_practice import bind as bind_define_practice
from cora.recipe.features.deprecate_plan import DeprecatePlan
from cora.recipe.features.deprecate_plan import bind as bind_deprecate
from cora.recipe.features.list_plans import ListPlans
from cora.recipe.features.list_plans import bind as bind_list
from cora.recipe.features.version_plan import VersionPlan
from cora.recipe.features.version_plan import bind as bind_version
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d3ec")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    """Drain all Recipe + Equipment projections (Plan integration test
    emits events from both BCs)."""
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    register_recipe_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _seed_chain(deps: Kernel, family_name: str = "Tomography") -> tuple[UUID, UUID, UUID]:
    """Seed Family + Asset + Method + Practice. Returns
    (practice_id, method_id, asset_id) for the Plan to bind to.

    The IDs are consumed from deps.id_generator in this exact order
    (define_family, register_asset, add_asset_family,
    define_method, define_practice). Caller pre-allocates them in
    the FixedIdGenerator queue.

    Family stream ids are deterministic (uuid5 over the name), so a
    second seed in the same db with the same family_name would 409;
    callers seeding two chains in one db pass distinct family_name."""
    cap_id = await bind_define_family(deps)(
        DefineFamily(name=family_name, affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await bind_register_asset(deps)(
        RegisterAsset(
            name="EigerDetector", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_family(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    method_id = await bind_define_method(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="Tomography",
            needed_family_ids=frozenset({cap_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await bind_define_practice(deps)(
        DefinePractice(name="APS-2BM-CT", method_id=method_id, site_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return practice_id, method_id, asset_id


def _chain_ids() -> list[UUID]:
    """8 ids consumed by _seed_chain (in order):
      - define_family: event_id only      = 1 (stream id derived from name)
      - register_asset:    asset_id + event_id = 2
      - add_asset_family: event_id only   = 1 (no new aggregate)
      - define_method:     method_id + event_id = 2
      - define_practice:   practice_id + event_id = 2
    Total = 8."""
    return [uuid4() for _ in range(8)]


@pytest.mark.integration
async def test_define_emits_defined_status_with_practice_and_method_ids(
    db_pool: asyncpg.Pool,
) -> None:
    plan_id = uuid4()
    deps = _build_deps(db_pool, [*_chain_ids(), plan_id, uuid4()])
    practice_id, method_id, asset_id = await _seed_chain(deps)
    await bind_define(deps)(
        DefinePlan(
            name="32-ID Plan",
            practice_id=practice_id,
            asset_ids=frozenset({asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT name, practice_id, method_id, status, version_tag "
            "FROM proj_recipe_plan_summary WHERE plan_id = $1",
            plan_id,
        )
    assert row is not None
    assert row["name"] == "32-ID Plan"
    assert row["practice_id"] == practice_id
    assert row["method_id"] == method_id
    assert row["status"] == "Defined"
    assert row["version_tag"] is None


@pytest.mark.integration
async def test_practice_id_filter_narrows_results(db_pool: asyncpg.Pool) -> None:
    """Two Plans binding different Practices; the practice_id filter
    returns only the one matching."""
    # First Plan
    plan_a = uuid4()
    deps_a = _build_deps(db_pool, [*_chain_ids(), plan_a, uuid4()])
    practice_a, _, asset_a = await _seed_chain(deps_a)
    await bind_define(deps_a)(
        DefinePlan(name="ForPracticeA", practice_id=practice_a, asset_ids=frozenset({asset_a})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Second Plan with a different chain
    plan_b = uuid4()
    deps_b = _build_deps(db_pool, [*_chain_ids(), plan_b, uuid4()])
    practice_b, _, asset_b = await _seed_chain(deps_b, family_name="TomographyB")
    await bind_define(deps_b)(
        DefinePlan(name="ForPracticeB", practice_id=practice_b, asset_ids=frozenset({asset_b})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)
    handler = bind_list(deps_a)
    page = await handler(
        ListPlans(practice_id=practice_a, limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].plan_id == plan_a
    assert page.items[0].practice_id == practice_a


@pytest.mark.integration
async def test_lifecycle_deprecate_preserves_practice_and_method(
    db_pool: asyncpg.Pool,
) -> None:
    plan_id = uuid4()
    deps = _build_deps(db_pool, [*_chain_ids(), plan_id, uuid4(), uuid4(), uuid4()])
    practice_id, method_id, asset_id = await _seed_chain(deps)
    await bind_define(deps)(
        DefinePlan(name="ToDeprecate", practice_id=practice_id, asset_ids=frozenset({asset_id})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_version(deps)(
        VersionPlan(plan_id=plan_id, version_tag="v3"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_deprecate(deps)(
        DeprecatePlan(plan_id=plan_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT practice_id, method_id, status, version_tag "
            "FROM proj_recipe_plan_summary WHERE plan_id = $1",
            plan_id,
        )
    assert row is not None
    assert row["status"] == "Deprecated"
    assert row["version_tag"] == "v3"
    assert row["practice_id"] == practice_id
    assert row["method_id"] == method_id


@pytest.mark.integration
async def test_combined_status_and_practice_id_filter(db_pool: asyncpg.Pool) -> None:
    """Pin: combined-filter SQL path narrows on BOTH status and
    practice_id together. Two Plans for Practice A (one Versioned,
    one Defined) plus one Versioned Plan for Practice B. Filter
    status=Versioned + practice_id=A returns only the first."""
    plan_versioned_a = uuid4()
    deps_a = _build_deps(
        db_pool,
        [*_chain_ids(), plan_versioned_a, uuid4(), uuid4()],
    )
    practice_a, _, asset_a = await _seed_chain(deps_a)
    await bind_define(deps_a)(
        DefinePlan(name="VerForA", practice_id=practice_a, asset_ids=frozenset({asset_a})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_version(deps_a)(
        VersionPlan(plan_id=plan_versioned_a, version_tag="v1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    plan_defined_a = uuid4()
    deps_a2 = _build_deps(db_pool, [plan_defined_a, uuid4()])
    await bind_define(deps_a2)(
        DefinePlan(name="DefForA", practice_id=practice_a, asset_ids=frozenset({asset_a})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    plan_versioned_b = uuid4()
    deps_b = _build_deps(
        db_pool,
        [*_chain_ids(), plan_versioned_b, uuid4(), uuid4()],
    )
    practice_b, _, asset_b = await _seed_chain(deps_b, family_name="TomographyB")
    await bind_define(deps_b)(
        DefinePlan(name="VerForB", practice_id=practice_b, asset_ids=frozenset({asset_b})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_version(deps_b)(
        VersionPlan(plan_id=plan_versioned_b, version_tag="v1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)
    handler = bind_list(deps_a)
    page = await handler(
        ListPlans(status="Versioned", practice_id=practice_a, limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].plan_id == plan_versioned_a


@pytest.mark.integration
async def test_empty_table_returns_empty_page(db_pool: asyncpg.Pool) -> None:
    deps = _build_deps(db_pool, [])
    handler = bind_list(deps)
    page = await handler(
        ListPlans(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None
