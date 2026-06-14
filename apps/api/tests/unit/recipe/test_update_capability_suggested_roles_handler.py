"""Unit tests for the `update_capability_suggested_roles` handler (Layer 3 3E).

Pins the handler-side RoleLookup precondition (every supplied
role_id must resolve via Kernel.role_lookup; first miss raises
RoleNotFoundError) + the wholesale-replace event-emission shape.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment.aggregates.role import RoleNotFoundError
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.recipe.features import define_capability, update_capability_suggested_roles
from cora.recipe.features.define_capability import DefineCapability
from cora.recipe.features.update_capability_suggested_roles import (
    UpdateCapabilitySuggestedRoles,
)
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000005a01")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-000000005a02")
_UPDATE_EVENT_ID = UUID("01900000-0000-7000-8000-000000005a03")
_ROLE_A = UUID("01900000-0000-7000-8000-000000005a11")
_ROLE_B = UUID("01900000-0000-7000-8000-000000005a12")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_3e_deps(store: InMemoryEventStore) -> Kernel:
    return build_deps(
        ids=[_CAPABILITY_ID, _DEFINED_EVENT_ID, _UPDATE_EVENT_ID],
        now=_NOW,
        event_store=store,
    )


def _seed_role(deps: Kernel, role_id: UUID, *, name: str = "Detector") -> None:
    lookup = deps.role_lookup
    assert hasattr(lookup, "register"), "deps.role_lookup must be in-memory"
    lookup.register(  # type: ignore[union-attr]
        role_id=role_id,
        name=name,
        required_affordances=frozenset({"Imageable"}),
    )


async def _define_capability(deps: Kernel) -> UUID:
    from cora.recipe.aggregates.capability.executor_shape import ExecutorShape

    return await define_capability.bind(deps)(
        DefineCapability(
            code="cora.capability.acquire",
            name="Acquire",
            required_affordances=frozenset(),
            executor_shapes=frozenset({ExecutorShape.METHOD}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_appends_capability_suggested_roles_updated_event() -> None:
    store = InMemoryEventStore()
    deps = _build_3e_deps(store)
    cid = await _define_capability(deps)
    _seed_role(deps, _ROLE_A)
    _seed_role(deps, _ROLE_B, name="Detector")

    await update_capability_suggested_roles.bind(deps)(
        UpdateCapabilitySuggestedRoles(
            capability_id=cid, suggested_role_ids=frozenset({_ROLE_A, _ROLE_B})
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _version = await store.load("Capability", cid)
    update_event = events[-1]
    assert update_event.event_type == "CapabilitySuggestedRolesUpdated"
    assert set(update_event.payload["suggested_role_ids"]) == {
        str(_ROLE_A),
        str(_ROLE_B),
    }
    assert update_event.metadata == {"command": "UpdateCapabilitySuggestedRoles"}


@pytest.mark.unit
async def test_handler_raises_role_not_found_when_any_role_unregistered() -> None:
    """First missing role short-circuits with RoleNotFoundError."""
    store = InMemoryEventStore()
    deps = _build_3e_deps(store)
    cid = await _define_capability(deps)
    _seed_role(deps, _ROLE_A)
    # _ROLE_B is intentionally NOT seeded.

    with pytest.raises(RoleNotFoundError):
        await update_capability_suggested_roles.bind(deps)(
            UpdateCapabilitySuggestedRoles(
                capability_id=cid, suggested_role_ids=frozenset({_ROLE_A, _ROLE_B})
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_accepts_empty_set_without_consulting_role_lookup() -> None:
    """Empty suggested_roles is a valid wholesale-replace clear; no
    Role seeding required (the asyncio.gather over the empty set
    short-circuits)."""
    store = InMemoryEventStore()
    deps = _build_3e_deps(store)
    cid = await _define_capability(deps)
    # No role seeded at all -- empty set still succeeds.

    await update_capability_suggested_roles.bind(deps)(
        UpdateCapabilitySuggestedRoles(capability_id=cid, suggested_role_ids=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Capability", cid)
    update_event = events[-1]
    assert update_event.event_type == "CapabilitySuggestedRolesUpdated"
    assert update_event.payload["suggested_role_ids"] == []
