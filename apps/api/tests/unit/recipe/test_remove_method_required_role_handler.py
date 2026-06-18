"""Unit tests for the `remove_method_required_role` application handler.

Mirror of `test_add_method_required_role_handler.py`. Exercises
load + decide + append round-trip end-to-end against the in-memory
event store; verifies wire_recipe exposes the slice on the bundle.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment.aggregates.asset import PortDirection
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.recipe import wire_recipe
from cora.recipe.aggregates.method import (
    ExecutionPattern,
    MethodCannotMutateRequiredRolesError,
    MethodNotFoundError,
    MethodRoleNameNotFoundError,
    PortRequirement,
    RoleName,
    RoleRequirement,
)
from cora.recipe.features import (
    add_method_required_role,
    define_method,
    remove_method_required_role,
    version_method,
)
from cora.recipe.features.add_method_required_role import AddMethodRequiredRole
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.remove_method_required_role import RemoveMethodRequiredRole
from cora.recipe.features.version_method import VersionMethod
from tests.unit._helpers import build_deps, seed_capability

_NOW = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)
_METHOD_ID = UUID("01900000-0000-7000-8000-000000000d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000000d0c")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-000000000d02")
_ADD_EVENT_ID = UUID("01900000-0000-7000-8000-000000000d03")
_REMOVE_EVENT_ID = UUID("01900000-0000-7000-8000-000000000d04")
_REMOVE_EVENT_ID_2 = UUID("01900000-0000-7000-8000-000000000d05")
_VERSION_EVENT_ID = UUID("01900000-0000-7000-8000-000000000d06")
_FAMILY_ID = UUID("01900000-0000-7000-8000-000000000df1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _requirement(role_name: str = "detector") -> RoleRequirement:
    return RoleRequirement(
        role_name=RoleName(role_name),
        family_id=_FAMILY_ID,
        required_ports=frozenset(
            {PortRequirement("trigger_in", PortDirection.INPUT, "TTL")},
        ),
    )


async def _define_and_add(deps: Kernel) -> UUID:
    await seed_capability(deps.event_store, _CAPABILITY_ID)
    method_id = await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            name="Tomography",
            capability_id=_CAPABILITY_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_method_required_role.bind(deps)(
        AddMethodRequiredRole(method_id=method_id, requirement=_requirement()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return method_id


@pytest.mark.unit
async def test_handler_appends_method_required_role_removed_event() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _ADD_EVENT_ID, _REMOVE_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_and_add(deps)

    await remove_method_required_role.bind(deps)(
        RemoveMethodRequiredRole(method_id=method_id, role_name=RoleName("detector")),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Method", method_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "MethodDefined",
        "MethodRequiredRoleAdded",
        "MethodRequiredRoleRemoved",
    ]
    remove_event = events[2]
    assert remove_event.event_id == _REMOVE_EVENT_ID
    assert remove_event.metadata == {"command": "RemoveMethodRequiredRole"}
    assert remove_event.payload["role_name"] == "detector"


@pytest.mark.unit
async def test_handler_rejects_unknown_method_id() -> None:
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _REMOVE_EVENT_ID],
        now=_NOW,
    )
    with pytest.raises(MethodNotFoundError):
        await remove_method_required_role.bind(deps)(
            RemoveMethodRequiredRole(method_id=_METHOD_ID, role_name=RoleName("detector")),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_rejects_unknown_role_name() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _ADD_EVENT_ID, _REMOVE_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_and_add(deps)
    with pytest.raises(MethodRoleNameNotFoundError):
        await remove_method_required_role.bind(deps)(
            RemoveMethodRequiredRole(
                method_id=method_id,
                role_name=RoleName("sample_monitor"),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_double_remove_is_strict_not_idempotent() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[
            _METHOD_ID,
            _DEFINED_EVENT_ID,
            _ADD_EVENT_ID,
            _REMOVE_EVENT_ID,
            _REMOVE_EVENT_ID_2,
        ],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_and_add(deps)
    handler = remove_method_required_role.bind(deps)
    await handler(
        RemoveMethodRequiredRole(method_id=method_id, role_name=RoleName("detector")),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(MethodRoleNameNotFoundError):
        await handler(
            RemoveMethodRequiredRole(method_id=method_id, role_name=RoleName("detector")),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_rejects_when_method_versioned() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[
            _METHOD_ID,
            _DEFINED_EVENT_ID,
            _ADD_EVENT_ID,
            _VERSION_EVENT_ID,
            _REMOVE_EVENT_ID,
        ],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_and_add(deps)
    await version_method.bind(deps)(
        VersionMethod(method_id=method_id, version_tag="v1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(MethodCannotMutateRequiredRolesError):
        await remove_method_required_role.bind(deps)(
            RemoveMethodRequiredRole(method_id=method_id, role_name=RoleName("detector")),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_wired_into_recipe_handlers_bundle() -> None:
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _ADD_EVENT_ID, _REMOVE_EVENT_ID],
        now=_NOW,
    )
    handlers = wire_recipe(deps)
    assert handlers.remove_method_required_role is not None
    assert callable(handlers.remove_method_required_role)
