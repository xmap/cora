"""Layer 3 sub-slice 3D: handler tests for the role_kind path."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment.aggregates.role import RoleNotFoundError
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.recipe.aggregates.method import (
    ExecutionPattern,
    RoleName,
    RoleRequirement,
)
from cora.recipe.features import add_method_required_role, define_method
from cora.recipe.features.add_method_required_role import AddMethodRequiredRole
from cora.recipe.features.define_method import DefineMethod
from tests.unit._helpers import build_deps, seed_capability

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_METHOD_ID = UUID("01900000-0000-7000-8000-000000003a01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000003a02")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-000000003a03")
_ADD_EVENT_ID = UUID("01900000-0000-7000-8000-000000003a04")
_ROLE_ID = UUID("01900000-0000-7000-8000-000000003a05")
_FAMILY_ID = UUID("01900000-0000-7000-8000-000000003a06")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_3d_deps(store: InMemoryEventStore) -> Kernel:
    return build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _ADD_EVENT_ID],
        now=_NOW,
        event_store=store,
    )


async def _define_helper(deps: Kernel) -> UUID:
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


def _seed_role(deps: Kernel) -> None:
    lookup = deps.role_lookup
    assert hasattr(lookup, "register"), "deps.role_lookup must be in-memory"
    lookup.register(  # type: ignore[union-attr]
        role_id=_ROLE_ID,
        name="Detector",
        required_affordances=frozenset({"Imageable"}),
    )


@pytest.mark.unit
async def test_handler_succeeds_for_role_kind_requirement_when_role_seeded() -> None:
    store = InMemoryEventStore()
    deps = _build_3d_deps(store)
    method_id = await _define_helper(deps)
    _seed_role(deps)

    requirement = RoleRequirement(role_name=RoleName("detector"), role_kind=_ROLE_ID)
    await add_method_required_role.bind(deps)(
        AddMethodRequiredRole(method_id=method_id, requirement=requirement),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Method", method_id)
    add_event = events[-1]
    assert add_event.event_type == "MethodRequiredRoleAdded"
    assert add_event.payload["role_kind"] == str(_ROLE_ID)
    assert add_event.payload.get("family_id") is None


@pytest.mark.unit
async def test_handler_raises_role_not_found_when_role_lookup_misses() -> None:
    """RoleLookup precondition fires; missing -> 404."""
    store = InMemoryEventStore()
    deps = _build_3d_deps(store)
    method_id = await _define_helper(deps)
    # NOTE: skip _seed_role so the lookup returns None.

    requirement = RoleRequirement(role_name=RoleName("detector"), role_kind=_ROLE_ID)
    with pytest.raises(RoleNotFoundError) as exc:
        await add_method_required_role.bind(deps)(
            AddMethodRequiredRole(method_id=method_id, requirement=requirement),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.role_id == _ROLE_ID


@pytest.mark.unit
async def test_handler_skips_role_lookup_for_family_id_requirement() -> None:
    """Slice-1 path: family_id-only requirements do NOT consult RoleLookup.

    No Role seeded; the handler still succeeds because the
    family_id path skips the RoleLookup precondition entirely.
    """
    store = InMemoryEventStore()
    deps = _build_3d_deps(store)
    method_id = await _define_helper(deps)
    # NO _seed_role -- RoleLookup is empty.

    requirement = RoleRequirement(role_name=RoleName("detector"), family_id=_FAMILY_ID)
    await add_method_required_role.bind(deps)(
        AddMethodRequiredRole(method_id=method_id, requirement=requirement),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Method", method_id)
    add_event = events[-1]
    assert add_event.payload["family_id"] == str(_FAMILY_ID)
    assert "role_kind" not in add_event.payload  # legacy byte-stable shape
