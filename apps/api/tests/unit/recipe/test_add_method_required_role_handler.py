"""Unit tests for the `add_method_required_role` application handler.

Mirrors `test_update_method_parameters_schema_handler.py` shape.
The handler is wired via `make_method_update_handler`; this suite
exercises the load + decide + append round-trip end-to-end against
the in-memory event store.
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
    MethodRoleNameAlreadyDeclaredError,
    PortRequirement,
    RoleName,
    RoleRequirement,
)
from cora.recipe.features import add_method_required_role, define_method, version_method
from cora.recipe.features.add_method_required_role import AddMethodRequiredRole
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.version_method import VersionMethod
from tests.unit._helpers import build_deps, seed_capability

_NOW = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)
_METHOD_ID = UUID("01900000-0000-7000-8000-000000000c01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000000c0c")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-000000000c02")
_ADD_EVENT_ID = UUID("01900000-0000-7000-8000-000000000c03")
_ADD_EVENT_ID_2 = UUID("01900000-0000-7000-8000-000000000c04")
_VERSION_EVENT_ID = UUID("01900000-0000-7000-8000-000000000c05")
_FAMILY_ID = UUID("01900000-0000-7000-8000-000000000cf1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _requirement(role_name: str = "detector") -> RoleRequirement:
    return RoleRequirement(
        role_name=RoleName(role_name),
        family_id=_FAMILY_ID,
        required_ports=frozenset(
            {PortRequirement("trigger_in", PortDirection.INPUT, "TTL")},
        ),
        optional=False,
    )


async def _define_method_helper(deps: Kernel) -> UUID:
    """Seed bound Capability + invoke define_method."""
    await seed_capability(deps.event_store, _CAPABILITY_ID)
    return await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            name="Tomography",
            capability_id=_CAPABILITY_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_appends_method_required_role_added_event() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _ADD_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)

    await add_method_required_role.bind(deps)(
        AddMethodRequiredRole(method_id=method_id, requirement=_requirement()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Method", method_id)
    assert version == 2
    assert [e.event_type for e in events] == ["MethodDefined", "MethodRequiredRoleAdded"]
    add_event = events[1]
    assert add_event.event_id == _ADD_EVENT_ID
    assert add_event.metadata == {"command": "AddMethodRequiredRole"}
    assert add_event.payload["role_name"] == "detector"
    assert add_event.payload["family_id"] == str(_FAMILY_ID)
    assert add_event.payload["optional"] is False
    assert add_event.payload["required_ports"] == [
        {"port_name": "trigger_in", "direction": "Input", "signal_type": "TTL"},
    ]


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _ADD_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)
    result = await add_method_required_role.bind(deps)(
        AddMethodRequiredRole(method_id=method_id, requirement=_requirement()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_rejects_unknown_method_id() -> None:
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _ADD_EVENT_ID],
        now=_NOW,
    )
    with pytest.raises(MethodNotFoundError):
        await add_method_required_role.bind(deps)(
            AddMethodRequiredRole(method_id=_METHOD_ID, requirement=_requirement()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_rejects_duplicate_role_name() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _ADD_EVENT_ID, _ADD_EVENT_ID_2],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)
    handler = add_method_required_role.bind(deps)
    await handler(
        AddMethodRequiredRole(method_id=method_id, requirement=_requirement()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(MethodRoleNameAlreadyDeclaredError):
        await handler(
            AddMethodRequiredRole(method_id=method_id, requirement=_requirement()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_rejects_when_method_versioned() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _VERSION_EVENT_ID, _ADD_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)
    # Move to Versioned status.
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


@pytest.mark.unit
async def test_handler_wired_into_recipe_handlers_bundle() -> None:
    """Pin that wire_recipe exposes add_method_required_role on the bundle.
    Catches a future refactor that forgets to register the slice."""
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _ADD_EVENT_ID],
        now=_NOW,
    )
    handlers = wire_recipe(deps)
    assert handlers.add_method_required_role is not None
    assert callable(handlers.add_method_required_role)
