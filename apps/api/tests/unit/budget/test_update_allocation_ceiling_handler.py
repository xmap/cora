"""Application-handler tests for the `update_allocation_ceiling` slice."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.budget.aggregates.allocation import (
    AllocationCannotUpdateCeilingError,
    AllocationNotFoundError,
    AllocationVoided,
)
from cora.budget.errors import UnauthorizedError
from cora.budget.features import update_allocation_ceiling
from cora.budget.features.update_allocation_ceiling import UpdateAllocationCeiling
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.budget._helpers import (
    ACTIVATED_AT,
    granted_event,
    seed_allocation_events,
)

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
_ALLOCATION_ID = UUID("01900000-0000-7000-8000-00000000e001")
_UPDATE_EVENT_ID = UUID("01900000-0000-7000-8000-00000000e002")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_UPDATE_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


@pytest.mark.unit
async def test_handler_updates_ceiling_of_a_granted_allocation() -> None:
    store = InMemoryEventStore()
    await seed_allocation_events(store, _ALLOCATION_ID, granted_event(_ALLOCATION_ID))
    deps = _build_deps(event_store=store)
    handler = update_allocation_ceiling.bind(deps)
    await handler(
        UpdateAllocationCeiling(allocation_id=_ALLOCATION_ID, ceiling_usd=18000.0),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Allocation", _ALLOCATION_ID)
    assert version == 2
    assert events[-1].event_type == "AllocationCeilingUpdated"
    assert events[-1].payload["ceiling_usd"] == 18000.0


@pytest.mark.unit
async def test_handler_same_ceiling_appends_nothing() -> None:
    """The idempotent PUT no-op flows through the handler as a zero-event
    append: the stream version stays put."""
    store = InMemoryEventStore()
    await seed_allocation_events(store, _ALLOCATION_ID, granted_event(_ALLOCATION_ID))
    deps = _build_deps(event_store=store)
    handler = update_allocation_ceiling.bind(deps)
    await handler(
        UpdateAllocationCeiling(allocation_id=_ALLOCATION_ID, ceiling_usd=25000.0),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Allocation", _ALLOCATION_ID)
    assert version == 1
    assert len(events) == 1


@pytest.mark.unit
async def test_handler_raises_not_found_for_unknown_allocation() -> None:
    deps = _build_deps()
    handler = update_allocation_ceiling.bind(deps)
    with pytest.raises(AllocationNotFoundError):
        await handler(
            UpdateAllocationCeiling(allocation_id=_ALLOCATION_ID, ceiling_usd=100.0),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_update_after_void() -> None:
    store = InMemoryEventStore()
    await seed_allocation_events(
        store,
        _ALLOCATION_ID,
        granted_event(_ALLOCATION_ID),
        AllocationVoided(
            allocation_id=_ALLOCATION_ID,
            reason="Granted against the wrong cycle",
            occurred_at=ACTIVATED_AT,
        ),
    )
    deps = _build_deps(event_store=store)
    handler = update_allocation_ceiling.bind(deps)
    with pytest.raises(AllocationCannotUpdateCeilingError):
        await handler(
            UpdateAllocationCeiling(allocation_id=_ALLOCATION_ID, ceiling_usd=100.0),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denied_does_not_write_to_stream() -> None:
    """Authorize-denial MUST NOT mutate the Allocation stream."""
    store = InMemoryEventStore()
    await seed_allocation_events(store, _ALLOCATION_ID, granted_event(_ALLOCATION_ID))
    deps = _build_deps(event_store=store, deny=True)
    handler = update_allocation_ceiling.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            UpdateAllocationCeiling(allocation_id=_ALLOCATION_ID, ceiling_usd=18000.0),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Allocation", _ALLOCATION_ID)
    assert version == 1
    assert len(events) == 1
    assert events[0].event_type == "AllocationGranted"
