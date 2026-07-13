"""Application-handler tests for the `seal_allocation` slice.

The slice's load-bearing wiring is the TotalSpendReader seam: the
handler folds the envelope, threads its `activated_at` and the Clock's
`now` into the injected reader, and records the reader's answer as the
seal's spend snapshot. The tests pin the window threading, the
guard-path short-circuit (no ledger read for a window that never
opened), and the stage-A zero-reader posture.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.budget.aggregates.allocation import (
    AllocationCannotSealError,
    AllocationNotFoundError,
)
from cora.budget.errors import UnauthorizedError
from cora.budget.features import seal_allocation
from cora.budget.features.seal_allocation import SealAllocation, zero_total_spend
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.budget._helpers import (
    ACTIVATED_AT,
    activated_event,
    granted_event,
    seed_allocation_events,
)

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
_ALLOCATION_ID = UUID("01900000-0000-7000-8000-00000000f001")
_SEAL_EVENT_ID = UUID("01900000-0000-7000-8000-00000000f002")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


class _RecordingReader:
    """TotalSpendReader stub that records its calls and returns a fixed fold."""

    def __init__(self, total: float) -> None:
        self.total = total
        self.calls: list[tuple[datetime, datetime]] = []

    async def __call__(self, *, window_start: datetime, window_end: datetime) -> float:
        self.calls.append((window_start, window_end))
        return self.total


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_SEAL_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _seed_active(store: InMemoryEventStore) -> None:
    await seed_allocation_events(
        store,
        _ALLOCATION_ID,
        granted_event(_ALLOCATION_ID),
        activated_event(_ALLOCATION_ID),
    )


@pytest.mark.unit
async def test_handler_seals_active_allocation_recording_readers_value() -> None:
    store = InMemoryEventStore()
    await _seed_active(store)
    deps = _build_deps(event_store=store)
    reader = _RecordingReader(total=42.5)
    handler = seal_allocation.bind(deps, total_spend_reader=reader)
    await handler(
        SealAllocation(allocation_id=_ALLOCATION_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Allocation", _ALLOCATION_ID)
    assert version == 3
    assert events[-1].event_type == "AllocationSealed"
    payload = events[-1].payload
    assert payload["spent_usd"] == 42.5
    assert payload["reason"] is None
    assert payload["sealed_by"] == str(_PRINCIPAL_ID)
    assert payload["occurred_at"] == _NOW.isoformat()


@pytest.mark.unit
async def test_handler_threads_activated_at_and_now_into_reader_window() -> None:
    """The envelope's own lifecycle IS the window: window_start is the
    folded activated_at, window_end is the Clock's now."""
    store = InMemoryEventStore()
    await _seed_active(store)
    deps = _build_deps(event_store=store)
    reader = _RecordingReader(total=0.0)
    handler = seal_allocation.bind(deps, total_spend_reader=reader)
    await handler(
        SealAllocation(allocation_id=_ALLOCATION_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert reader.calls == [(ACTIVATED_AT, _NOW)]


@pytest.mark.unit
async def test_handler_carries_seal_reason_to_payload() -> None:
    store = InMemoryEventStore()
    await _seed_active(store)
    deps = _build_deps(event_store=store)
    handler = seal_allocation.bind(deps, total_spend_reader=_RecordingReader(total=0.0))
    await handler(
        SealAllocation(allocation_id=_ALLOCATION_ID, reason="Campaign closed early"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Allocation", _ALLOCATION_ID)
    assert events[-1].payload["reason"] == "Campaign closed early"


@pytest.mark.unit
async def test_handler_with_zero_reader_records_zero_snapshot() -> None:
    """Stage-A posture: the bound zero-reader makes every seal record 0.0
    honestly until stage C wires the ledger-backed fold."""
    store = InMemoryEventStore()
    await _seed_active(store)
    deps = _build_deps(event_store=store)
    handler = seal_allocation.bind(deps, total_spend_reader=zero_total_spend)
    await handler(
        SealAllocation(allocation_id=_ALLOCATION_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Allocation", _ALLOCATION_ID)
    assert events[-1].payload["spent_usd"] == 0.0


@pytest.mark.unit
async def test_handler_raises_not_found_without_calling_reader() -> None:
    deps = _build_deps()
    reader = _RecordingReader(total=99.0)
    handler = seal_allocation.bind(deps, total_spend_reader=reader)
    with pytest.raises(AllocationNotFoundError):
        await handler(
            SealAllocation(allocation_id=_ALLOCATION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert reader.calls == []


@pytest.mark.unit
async def test_handler_raises_cannot_seal_dormant_grant_without_calling_reader() -> None:
    """A Granted envelope has no activated_at: there is no window to
    fold, so the reader must not be consulted before the guard fires."""
    store = InMemoryEventStore()
    await seed_allocation_events(store, _ALLOCATION_ID, granted_event(_ALLOCATION_ID))
    deps = _build_deps(event_store=store)
    reader = _RecordingReader(total=99.0)
    handler = seal_allocation.bind(deps, total_spend_reader=reader)
    with pytest.raises(AllocationCannotSealError):
        await handler(
            SealAllocation(allocation_id=_ALLOCATION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert reader.calls == []


@pytest.mark.unit
async def test_handler_denied_does_not_write_or_read_ledger() -> None:
    """Authorize-denial MUST NOT mutate the stream nor touch the ledger."""
    store = InMemoryEventStore()
    await _seed_active(store)
    deps = _build_deps(event_store=store, deny=True)
    reader = _RecordingReader(total=99.0)
    handler = seal_allocation.bind(deps, total_spend_reader=reader)
    with pytest.raises(UnauthorizedError):
        await handler(
            SealAllocation(allocation_id=_ALLOCATION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Allocation", _ALLOCATION_ID)
    assert version == 2
    assert len(events) == 2
    assert reader.calls == []
