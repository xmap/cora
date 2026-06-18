"""Integration test: bind_plan_role + unbind_plan_role handlers against
real Postgres. Exercises the jsonb role_bindings column round-trip
through proj_recipe_plan_summary.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetTier, PortDirection
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import bind as bind_add_asset_family
from cora.equipment.features.add_asset_port import AddAssetPort
from cora.equipment.features.add_asset_port import bind as bind_add_asset_port
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe._projections import register_recipe_projections
from cora.recipe.aggregates.capability import ExecutorShape
from cora.recipe.aggregates.method import (
    ExecutionPattern,
    PortRequirement,
    RoleName,
    RoleRequirement,
)
from cora.recipe.aggregates.plan import PlanCannotMutateRoleBindingsError
from cora.recipe.features import (
    add_method_required_role,
    bind_plan_role,
    define_capability,
    define_method,
    define_plan,
    define_practice,
    unbind_plan_role,
    version_plan,
)
from cora.recipe.features.add_method_required_role import AddMethodRequiredRole
from cora.recipe.features.bind_plan_role import BindPlanRole
from cora.recipe.features.define_capability import DefineCapability
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.unbind_plan_role import UnbindPlanRole
from cora.recipe.features.version_plan import VersionPlan
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_plan_with_required_role(db_pool: asyncpg.Pool) -> tuple[UUID, UUID]:
    """Seed Capability + Family + Asset + Method (with required role) +
    Plan. Returns (plan_id, asset_id)."""
    # Need plenty of UUIDs for the cascade of definitions.
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(60)])

    # Capability
    cap_id = await define_capability.bind(deps)(
        DefineCapability(
            name="Tomo",
            code="cora.capability.tomography",
            executor_shapes=frozenset({ExecutorShape.METHOD}),
            required_affordances=frozenset(),
            parameters_schema=None,
            description=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Family
    family_id = await bind_define_family(deps)(
        DefineFamily(name="Camera", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Asset with the family + matching port
    asset_id = await bind_register_asset(deps)(
        RegisterAsset(
            name="cam",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_asset_family(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_asset_port(deps)(
        AddAssetPort(
            asset_id=asset_id,
            port_name="trigger_in",
            direction=PortDirection.INPUT,
            signal_type="TTL",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Method + required role
    method_id = await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            name="Tomography",
            capability_id=cap_id,
            needed_family_ids=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_method_required_role.bind(deps)(
        AddMethodRequiredRole(
            method_id=method_id,
            requirement=RoleRequirement(
                role_name=RoleName("detector"),
                family_id=family_id,
                required_ports=frozenset(
                    {
                        PortRequirement(
                            port_name="trigger_in",
                            direction=PortDirection.INPUT,
                            signal_type="TTL",
                        ),
                    }
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Practice + Plan
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name="P", method_id=method_id, site_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_id = await define_plan.bind(deps)(
        DefinePlan(name="P1", practice_id=practice_id, asset_ids=frozenset({asset_id})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return plan_id, asset_id


@pytest.mark.integration
async def test_bind_plan_role_writes_jsonb_array(db_pool: asyncpg.Pool) -> None:
    plan_id, asset_id = await _seed_plan_with_required_role(db_pool)
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(10)])
    await bind_plan_role.bind(deps)(
        BindPlanRole(
            plan_id=plan_id,
            role_name=RoleName("detector"),
            asset_id=asset_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    registry = ProjectionRegistry()
    register_recipe_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT role_bindings FROM proj_recipe_plan_summary WHERE plan_id = $1",
            plan_id,
        )
    assert row is not None
    bindings = row["role_bindings"]
    if isinstance(bindings, str):
        import json

        bindings = json.loads(bindings)
    assert len(bindings) == 1
    assert bindings[0]["role_name"] == "detector"
    assert bindings[0]["asset_id"] == str(asset_id)


@pytest.mark.integration
async def test_unbind_plan_role_filters_jsonb_array(db_pool: asyncpg.Pool) -> None:
    plan_id, asset_id = await _seed_plan_with_required_role(db_pool)
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(10)])
    await bind_plan_role.bind(deps)(
        BindPlanRole(
            plan_id=plan_id,
            role_name=RoleName("detector"),
            asset_id=asset_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await unbind_plan_role.bind(deps)(
        UnbindPlanRole(plan_id=plan_id, role_name=RoleName("detector")),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    registry = ProjectionRegistry()
    register_recipe_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT role_bindings FROM proj_recipe_plan_summary WHERE plan_id = $1",
            plan_id,
        )
    assert row is not None
    bindings = row["role_bindings"]
    if isinstance(bindings, str):
        import json

        bindings = json.loads(bindings)
    assert bindings == []


@pytest.mark.integration
async def test_plan_defined_alone_projects_empty_role_bindings(db_pool: asyncpg.Pool) -> None:
    plan_id, _ = await _seed_plan_with_required_role(db_pool)
    registry = ProjectionRegistry()
    register_recipe_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT role_bindings FROM proj_recipe_plan_summary WHERE plan_id = $1",
            plan_id,
        )
    assert row is not None
    bindings = row["role_bindings"]
    if isinstance(bindings, str):
        import json

        bindings = json.loads(bindings)
    assert bindings == []


@pytest.mark.integration
async def test_versioned_plan_rejects_role_binding_mutation(db_pool: asyncpg.Pool) -> None:
    plan_id, asset_id = await _seed_plan_with_required_role(db_pool)
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(10)])
    await version_plan.bind(deps)(
        VersionPlan(plan_id=plan_id, version_tag="v1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(PlanCannotMutateRoleBindingsError):
        await bind_plan_role.bind(deps)(
            BindPlanRole(
                plan_id=plan_id,
                role_name=RoleName("detector"),
                asset_id=asset_id,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    with pytest.raises(PlanCannotMutateRoleBindingsError):
        await unbind_plan_role.bind(deps)(
            UnbindPlanRole(plan_id=plan_id, role_name=RoleName("detector")),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
