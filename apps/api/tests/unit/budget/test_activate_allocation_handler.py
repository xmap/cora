"""Application-handler tests for the `activate_allocation` slice.

Actor-stamping factory path: the handler threads the envelope's
`principal_id` into the decider as `activated_by`, so the payload
carries the fold-symmetric attribution half.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.budget.aggregates.allocation import (
    AllocationAlreadyActiveError,
    AllocationCannotActivateError,
    AllocationNotFoundError,
)
from cora.budget.errors import UnauthorizedError
from cora.budget.features import activate_allocation
from cora.budget.features.activate_allocation import ActivateAllocation
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.allocation_lookup import AllocationLookupResult
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.agent._helpers import FakeAllocationLookup
from tests.unit.budget._helpers import (
    activated_event,
    granted_event,
    seed_allocation_events,
)

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
_ALLOCATION_ID = UUID("01900000-0000-7000-8000-00000000d001")
_ACTIVATE_EVENT_ID = UUID("01900000-0000-7000-8000-00000000d002")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_ACTIVATE_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


@pytest.mark.unit
async def test_handler_activates_a_granted_allocation() -> None:
    store = InMemoryEventStore()
    await seed_allocation_events(store, _ALLOCATION_ID, granted_event(_ALLOCATION_ID))
    deps = _build_deps(event_store=store)
    handler = activate_allocation.bind(deps)
    await handler(
        ActivateAllocation(allocation_id=_ALLOCATION_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Allocation", _ALLOCATION_ID)
    assert version == 2
    assert events[-1].event_type == "AllocationActivated"
    assert events[-1].payload["allocation_id"] == str(_ALLOCATION_ID)


@pytest.mark.unit
async def test_handler_stamps_principal_as_activated_by() -> None:
    """The actor-stamping factory passes the envelope's principal into
    the decider, so the payload attribution matches the envelope."""
    store = InMemoryEventStore()
    await seed_allocation_events(store, _ALLOCATION_ID, granted_event(_ALLOCATION_ID))
    deps = _build_deps(event_store=store)
    handler = activate_allocation.bind(deps)
    await handler(
        ActivateAllocation(allocation_id=_ALLOCATION_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Allocation", _ALLOCATION_ID)
    assert events[-1].payload["activated_by"] == str(_PRINCIPAL_ID)
    assert events[-1].principal_id == _PRINCIPAL_ID


@pytest.mark.unit
async def test_handler_raises_not_found_for_unknown_allocation() -> None:
    deps = _build_deps()
    handler = activate_allocation.bind(deps)
    with pytest.raises(AllocationNotFoundError):
        await handler(
            ActivateAllocation(allocation_id=_ALLOCATION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_activate_when_already_active() -> None:
    store = InMemoryEventStore()
    await seed_allocation_events(
        store,
        _ALLOCATION_ID,
        granted_event(_ALLOCATION_ID),
        activated_event(_ALLOCATION_ID),
    )
    deps = _build_deps(event_store=store)
    handler = activate_allocation.bind(deps)
    with pytest.raises(AllocationCannotActivateError):
        await handler(
            ActivateAllocation(allocation_id=_ALLOCATION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denies_via_authorize_port() -> None:
    deps = _build_deps(deny=True)
    handler = activate_allocation.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            ActivateAllocation(allocation_id=_ALLOCATION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denied_does_not_write_to_stream() -> None:
    """Authorize-denial MUST NOT mutate the Allocation stream."""
    store = InMemoryEventStore()
    await seed_allocation_events(store, _ALLOCATION_ID, granted_event(_ALLOCATION_ID))
    deps = _build_deps(event_store=store, deny=True)
    handler = activate_allocation.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            ActivateAllocation(allocation_id=_ALLOCATION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Allocation", _ALLOCATION_ID)
    assert version == 1
    assert len(events) == 1
    assert events[0].event_type == "AllocationGranted"


_OTHER_ACTIVE_ID = UUID("01900000-0000-7000-8000-00000000d0ff")


def _active_result(allocation_id: UUID) -> AllocationLookupResult:
    return AllocationLookupResult(
        allocation_id=allocation_id,
        ceiling_usd=100.0,
        activated_at=_NOW,
        campaign_id=None,
    )


@pytest.mark.unit
async def test_handler_refuses_when_a_different_envelope_is_already_active() -> None:
    """Single-Active guard: a second activation while another envelope is
    Active must be refused, so the gates and the sealer can rely on one
    Active allocation. The stream is not mutated."""
    store = InMemoryEventStore()
    await seed_allocation_events(store, _ALLOCATION_ID, granted_event(_ALLOCATION_ID))
    lookup = FakeAllocationLookup(active=_active_result(_OTHER_ACTIVE_ID))
    deps = _build_deps_shared(
        ids=[_ACTIVATE_EVENT_ID], now=_NOW, event_store=store, allocation_lookup=lookup
    )
    handler = activate_allocation.bind(deps)

    with pytest.raises(AllocationAlreadyActiveError) as exc:
        await handler(
            ActivateAllocation(allocation_id=_ALLOCATION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    assert exc.value.active_allocation_id == _OTHER_ACTIVE_ID
    assert lookup.find_active_calls == 1
    _events, version = await store.load("Allocation", _ALLOCATION_ID)
    assert version == 1  # unchanged: only the seeded Granted event


@pytest.mark.unit
async def test_handler_activates_when_no_other_envelope_is_active() -> None:
    """A sealed or voided prior envelope leaves nothing Active, so the
    lookup returns None and activation proceeds."""
    store = InMemoryEventStore()
    await seed_allocation_events(store, _ALLOCATION_ID, granted_event(_ALLOCATION_ID))
    lookup = FakeAllocationLookup(active=None)
    deps = _build_deps_shared(
        ids=[_ACTIVATE_EVENT_ID], now=_NOW, event_store=store, allocation_lookup=lookup
    )
    handler = activate_allocation.bind(deps)

    await handler(
        ActivateAllocation(allocation_id=_ALLOCATION_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert lookup.find_active_calls == 1
    events, version = await store.load("Allocation", _ALLOCATION_ID)
    assert version == 2
    assert events[-1].event_type == "AllocationActivated"


@pytest.mark.unit
async def test_handler_permits_reactivating_the_same_active_envelope_to_the_decider() -> None:
    """When find_active returns THIS allocation (not a different one), the
    guard does not fire; the decider's own Granted-only source set is
    what rejects a re-activation."""
    store = InMemoryEventStore()
    await seed_allocation_events(
        store,
        _ALLOCATION_ID,
        granted_event(_ALLOCATION_ID),
        activated_event(_ALLOCATION_ID),
    )
    lookup = FakeAllocationLookup(active=_active_result(_ALLOCATION_ID))
    deps = _build_deps_shared(
        ids=[_ACTIVATE_EVENT_ID], now=_NOW, event_store=store, allocation_lookup=lookup
    )
    handler = activate_allocation.bind(deps)

    with pytest.raises(AllocationCannotActivateError):
        await handler(
            ActivateAllocation(allocation_id=_ALLOCATION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
