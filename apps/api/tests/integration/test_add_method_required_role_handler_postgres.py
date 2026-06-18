"""Integration test: add_method_required_role + remove_method_required_role
handlers against real Postgres. Exercises the jsonb required_roles
column round-trip through proj_recipe_method_summary.

Pins:
  - MethodRequiredRoleAdded writes the role to the jsonb array (sorted
    by role_name)
  - Two adds yield a 2-entry sorted array
  - MethodRequiredRoleRemoved filters out the matching role
  - Decommissioned-equivalent (Versioned/Deprecated) lifecycle guard
    surfaces correctly through the full handler stack (decider raises,
    handler propagates, no event lands)
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.asset import PortDirection
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe._projections import register_recipe_projections
from cora.recipe.aggregates.capability import ExecutorShape
from cora.recipe.aggregates.method import (
    ExecutionPattern,
    PortRequirement,
    RoleName,
    RoleRequirement,
)
from cora.recipe.features import (
    add_method_required_role,
    define_capability,
    define_method,
    remove_method_required_role,
    version_method,
)
from cora.recipe.features.add_method_required_role import AddMethodRequiredRole
from cora.recipe.features.define_capability import DefineCapability
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.remove_method_required_role import RemoveMethodRequiredRole
from cora.recipe.features.version_method import VersionMethod
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_method(db_pool: asyncpg.Pool) -> UUID:
    """Define a Capability + Method via the real handlers; return method_id."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(20)])
    cap_id = await define_capability.bind(deps)(
        DefineCapability(
            name="ContinuousRotationSweep",
            code="cora.capability.continuous_rotation_sweep",
            executor_shapes=frozenset({ExecutorShape.METHOD}),
            required_affordances=frozenset(),
            parameters_schema=None,
            description=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
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
    return method_id


def _requirement(role_name: str = "detector") -> RoleRequirement:
    return RoleRequirement(
        role_name=RoleName(role_name),
        family_id=uuid4(),
        required_ports=frozenset(
            {PortRequirement("trigger_in", PortDirection.INPUT, "TTL")},
        ),
        optional=False,
    )


@pytest.mark.integration
async def test_add_method_required_role_writes_jsonb_array(
    db_pool: asyncpg.Pool,
) -> None:
    """Add one role and verify the proj_recipe_method_summary
    required_roles column carries it after the projection drains."""
    method_id = await _seed_method(db_pool)
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(20)])
    await add_method_required_role.bind(deps)(
        AddMethodRequiredRole(method_id=method_id, requirement=_requirement()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    registry = ProjectionRegistry()
    register_recipe_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT required_roles FROM proj_recipe_method_summary WHERE method_id = $1",
            method_id,
        )
    assert row is not None
    roles = row["required_roles"]
    if isinstance(roles, str):
        import json

        roles = json.loads(roles)
    assert len(roles) == 1
    assert roles[0]["role_name"] == "detector"
    assert roles[0]["optional"] is False
    assert roles[0]["required_ports"] == [
        {"port_name": "trigger_in", "direction": "Input", "signal_type": "TTL"},
    ]


@pytest.mark.integration
async def test_add_two_required_roles_yields_sorted_jsonb_array(
    db_pool: asyncpg.Pool,
) -> None:
    """Add roles in reverse alphabetical order; projection persists
    sorted by role_name."""
    method_id = await _seed_method(db_pool)
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(20)])
    handler = add_method_required_role.bind(deps)
    await handler(
        AddMethodRequiredRole(method_id=method_id, requirement=_requirement("sample_monitor")),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await handler(
        AddMethodRequiredRole(method_id=method_id, requirement=_requirement("detector")),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    registry = ProjectionRegistry()
    register_recipe_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT required_roles FROM proj_recipe_method_summary WHERE method_id = $1",
            method_id,
        )
    assert row is not None
    roles = row["required_roles"]
    if isinstance(roles, str):
        import json

        roles = json.loads(roles)
    assert [r["role_name"] for r in roles] == ["detector", "sample_monitor"]


@pytest.mark.integration
async def test_remove_method_required_role_filters_jsonb_array(
    db_pool: asyncpg.Pool,
) -> None:
    """Add two roles then remove one; the projection drops only the
    matching role_name."""
    method_id = await _seed_method(db_pool)
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(20)])
    add_handler = add_method_required_role.bind(deps)
    await add_handler(
        AddMethodRequiredRole(method_id=method_id, requirement=_requirement("detector")),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_handler(
        AddMethodRequiredRole(method_id=method_id, requirement=_requirement("sample_monitor")),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await remove_method_required_role.bind(deps)(
        RemoveMethodRequiredRole(method_id=method_id, role_name=RoleName("detector")),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    registry = ProjectionRegistry()
    register_recipe_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT required_roles FROM proj_recipe_method_summary WHERE method_id = $1",
            method_id,
        )
    assert row is not None
    roles = row["required_roles"]
    if isinstance(roles, str):
        import json

        roles = json.loads(roles)
    assert [r["role_name"] for r in roles] == ["sample_monitor"]


@pytest.mark.integration
async def test_method_defined_alone_projects_empty_required_roles_array(
    db_pool: asyncpg.Pool,
) -> None:
    """A Method with no role events ever emitted projects required_roles
    as empty array (NOT NULL DEFAULT '[]'::jsonb)."""
    method_id = await _seed_method(db_pool)

    registry = ProjectionRegistry()
    register_recipe_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT required_roles FROM proj_recipe_method_summary WHERE method_id = $1",
            method_id,
        )
    assert row is not None
    roles = row["required_roles"]
    if isinstance(roles, str):
        import json

        roles = json.loads(roles)
    assert roles == []


@pytest.mark.integration
async def test_versioned_method_rejects_required_role_mutation(
    db_pool: asyncpg.Pool,
) -> None:
    """Lifecycle guard end-to-end: after VersionMethod, add and remove
    both surface MethodCannotMutateRequiredRolesError. No event lands."""
    from cora.recipe.aggregates.method import MethodCannotMutateRequiredRolesError

    method_id = await _seed_method(db_pool)
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(20)])
    await version_method.bind(deps)(
        VersionMethod(method_id=method_id, version_tag="v1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(MethodCannotMutateRequiredRolesError):
        await add_method_required_role.bind(deps)(
            AddMethodRequiredRole(method_id=method_id, requirement=_requirement()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    with pytest.raises(MethodCannotMutateRequiredRolesError):
        await remove_method_required_role.bind(deps)(
            RemoveMethodRequiredRole(method_id=method_id, role_name=RoleName("detector")),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
