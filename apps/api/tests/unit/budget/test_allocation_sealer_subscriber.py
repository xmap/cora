"""Unit tests for AllocationSealerSubscriber (CampaignClosed -> seal).

Drives the subscriber against `InMemoryEventStore` seeds with local
lookup fakes so every path is pinned: the campaign-bound seal (with
the ledger snapshot and the SYSTEM principal), the skip family
(no Active envelope, unbound envelope, campaign mismatch, stale
projection row), and idempotent replay.
"""

# pyright: reportPrivateUsage=false

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4, uuid5

import pytest

from cora.budget.aggregates.allocation import AllocationStatus, load_allocation
from cora.budget.subscribers.allocation_sealer import (
    _ALLOCATION_SEALER_NAMESPACE,
    AllocationSealerSubscriber,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.ports import ConcurrencyError
from cora.infrastructure.ports.allocation_lookup import AllocationLookupResult
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.ports.spend_lookup import TotalSpendResult
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID
from tests.unit.budget._helpers import (
    ACTIVATED_AT,
    activated_event,
    granted_event,
    seed_allocation_events,
)

_CAMPAIGN_ID = uuid4()
_CLOSED_AT = datetime(2026, 7, 13, 18, 30, 0, tzinfo=UTC)


class _FakeAllocationLookup:
    def __init__(self, active: AllocationLookupResult | None) -> None:
        self.active = active

    async def find_active(self) -> AllocationLookupResult | None:
        return self.active


class _FakeTotalSpendLookup:
    """SpendLookup fake covering only the total-spend arm the sealer uses."""

    def __init__(self, *, total_usd_spent: float = 0.0) -> None:
        self.total_usd_spent = total_usd_spent
        self.total_windows: list[tuple[datetime, datetime]] = []

    async def find_total_spend(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> TotalSpendResult:
        self.total_windows.append((window_start, window_end))
        return TotalSpendResult(
            window_start=window_start,
            window_end=window_end,
            usd_spent=self.total_usd_spent,
            call_count=3,
        )


def _campaign_closed(campaign_id: UUID) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Campaign",
        stream_id=campaign_id,
        version=4,
        event_type="CampaignClosed",
        schema_version=1,
        payload={"campaign_id": str(campaign_id), "occurred_at": _CLOSED_AT.isoformat()},
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_CLOSED_AT,
        recorded_at=_CLOSED_AT,
    )


def _active_row(allocation_id: UUID, campaign_id: UUID | None) -> AllocationLookupResult:
    return AllocationLookupResult(
        allocation_id=allocation_id,
        ceiling_usd=25000.0,
        activated_at=ACTIVATED_AT,
        campaign_id=campaign_id,
    )


async def _seed_active_allocation(
    store: InMemoryEventStore,
    allocation_id: UUID,
    *,
    campaign_id: UUID | None,
) -> None:
    await seed_allocation_events(
        store,
        allocation_id,
        granted_event(allocation_id, campaign_id=campaign_id),
        activated_event(allocation_id),
    )


def _sealer(
    store: InMemoryEventStore,
    lookup: _FakeAllocationLookup,
    spend: _FakeTotalSpendLookup | None = None,
) -> tuple[AllocationSealerSubscriber, _FakeTotalSpendLookup]:
    spend = spend or _FakeTotalSpendLookup()
    sub = AllocationSealerSubscriber(
        event_store=store,
        allocation_lookup=lookup,
        spend_lookup=spend,  # type: ignore[arg-type]  # total-spend arm only
    )
    return sub, spend


@pytest.mark.unit
def test_subscriber_metadata() -> None:
    store = InMemoryEventStore()
    sub, _ = _sealer(store, _FakeAllocationLookup(None))
    assert sub.name == "allocation_sealer"
    assert sub.subscribed_event_types == frozenset({"CampaignClosed"})
    assert sub.batch_size == 1


@pytest.mark.unit
async def test_bound_active_allocation_is_sealed_with_ledger_snapshot() -> None:
    """The close-the-books path: the envelope bound to the closed
    campaign folds Sealed, the snapshot is the ledger sum over
    [activated_at, campaign-close), and the seal is attributed to the
    SYSTEM principal (no operator issued a command)."""
    store = InMemoryEventStore()
    allocation_id = uuid4()
    await _seed_active_allocation(store, allocation_id, campaign_id=_CAMPAIGN_ID)
    sub, spend = _sealer(
        store,
        _FakeAllocationLookup(_active_row(allocation_id, _CAMPAIGN_ID)),
        _FakeTotalSpendLookup(total_usd_spent=431.25),
    )
    trigger = _campaign_closed(_CAMPAIGN_ID)

    await sub.apply(trigger, AsyncMock())

    state = await load_allocation(store, allocation_id)
    assert state is not None
    assert state.status is AllocationStatus.SEALED
    assert state.sealed_at == _CLOSED_AT
    assert state.spent_usd_at_seal == 431.25
    assert state.sealed_by == SYSTEM_PRINCIPAL_ID
    assert state.end_reason is not None
    assert str(_CAMPAIGN_ID) in state.end_reason
    assert spend.total_windows == [(ACTIVATED_AT, _CLOSED_AT)]

    stored, _version = await store.load("Allocation", allocation_id)
    seal_envelope = stored[-1]
    assert seal_envelope.event_type == "AllocationSealed"
    assert seal_envelope.correlation_id == trigger.correlation_id
    assert seal_envelope.causation_id == trigger.event_id
    # Deterministic event id: a replay derives the same id, so the store's
    # UNIQUE(event_id) backs the expected-version guard.
    assert seal_envelope.event_id == uuid5(
        _ALLOCATION_SEALER_NAMESPACE, f"seal:{trigger.event_id}:{allocation_id}"
    )


@pytest.mark.unit
async def test_no_active_allocation_skips_without_write() -> None:
    store = InMemoryEventStore()
    sub, spend = _sealer(store, _FakeAllocationLookup(None))

    await sub.apply(_campaign_closed(_CAMPAIGN_ID), AsyncMock())

    assert spend.total_windows == []


@pytest.mark.unit
async def test_allocation_bound_to_another_campaign_is_left_active() -> None:
    store = InMemoryEventStore()
    allocation_id = uuid4()
    other_campaign_id = uuid4()
    await _seed_active_allocation(store, allocation_id, campaign_id=other_campaign_id)
    sub, spend = _sealer(
        store, _FakeAllocationLookup(_active_row(allocation_id, other_campaign_id))
    )

    await sub.apply(_campaign_closed(_CAMPAIGN_ID), AsyncMock())

    state = await load_allocation(store, allocation_id)
    assert state is not None
    assert state.status is AllocationStatus.ACTIVE
    assert spend.total_windows == []


@pytest.mark.unit
async def test_unbound_allocation_is_left_active() -> None:
    """No campaign binding means no automatic seal: binding is what
    opts an envelope into the campaign-close reflex."""
    store = InMemoryEventStore()
    allocation_id = uuid4()
    await _seed_active_allocation(store, allocation_id, campaign_id=None)
    sub, spend = _sealer(store, _FakeAllocationLookup(_active_row(allocation_id, None)))

    await sub.apply(_campaign_closed(_CAMPAIGN_ID), AsyncMock())

    state = await load_allocation(store, allocation_id)
    assert state is not None
    assert state.status is AllocationStatus.ACTIVE
    assert spend.total_windows == []


@pytest.mark.unit
async def test_stale_projection_row_for_granted_allocation_skips() -> None:
    """The lookup says Active but the fold says Granted (projection
    lag): the fold is the truth, so the sealer stands down instead of
    letting the decider raise into the bookmark."""
    store = InMemoryEventStore()
    allocation_id = uuid4()
    await seed_allocation_events(
        store,
        allocation_id,
        granted_event(allocation_id, campaign_id=_CAMPAIGN_ID),
    )
    sub, spend = _sealer(store, _FakeAllocationLookup(_active_row(allocation_id, _CAMPAIGN_ID)))

    await sub.apply(_campaign_closed(_CAMPAIGN_ID), AsyncMock())

    state = await load_allocation(store, allocation_id)
    assert state is not None
    assert state.status is AllocationStatus.GRANTED
    assert spend.total_windows == []


@pytest.mark.unit
async def test_replayed_delivery_after_seal_no_ops() -> None:
    """At-least-once delivery: the second apply() finds the envelope
    already Sealed (via the fold double-check) and leaves the stream
    untouched, so the seal snapshot is never overwritten."""
    store = InMemoryEventStore()
    allocation_id = uuid4()
    await _seed_active_allocation(store, allocation_id, campaign_id=_CAMPAIGN_ID)
    lookup = _FakeAllocationLookup(_active_row(allocation_id, _CAMPAIGN_ID))
    sub, spend = _sealer(store, lookup, _FakeTotalSpendLookup(total_usd_spent=431.25))
    trigger = _campaign_closed(_CAMPAIGN_ID)

    await sub.apply(trigger, AsyncMock())
    _stored_after_first, version_after_first = await store.load("Allocation", allocation_id)

    # The projection row may ALSO still say Active on replay (worker
    # lag); the fold double-check is what makes the replay a no-op.
    sub.allocation_lookup = lookup
    later = StoredEvent(
        position=trigger.position,
        event_id=trigger.event_id,
        stream_type=trigger.stream_type,
        stream_id=trigger.stream_id,
        version=trigger.version,
        event_type=trigger.event_type,
        schema_version=trigger.schema_version,
        payload=trigger.payload,
        correlation_id=trigger.correlation_id,
        causation_id=trigger.causation_id,
        occurred_at=trigger.occurred_at,
        recorded_at=trigger.recorded_at + timedelta(seconds=5),
    )
    await sub.apply(later, AsyncMock())

    _stored_after_second, version_after_second = await store.load("Allocation", allocation_id)
    assert version_after_second == version_after_first
    assert len(spend.total_windows) == 1


@pytest.mark.unit
async def test_non_trigger_event_type_is_ignored(monkeypatch: Any) -> None:
    store = InMemoryEventStore()
    lookup = _FakeAllocationLookup(None)
    sub, _ = _sealer(store, lookup)
    trigger = _campaign_closed(_CAMPAIGN_ID)
    other = StoredEvent(
        position=trigger.position,
        event_id=trigger.event_id,
        stream_type=trigger.stream_type,
        stream_id=trigger.stream_id,
        version=trigger.version,
        event_type="CampaignHeld",
        schema_version=trigger.schema_version,
        payload=trigger.payload,
        correlation_id=trigger.correlation_id,
        causation_id=trigger.causation_id,
        occurred_at=trigger.occurred_at,
        recorded_at=trigger.recorded_at,
    )

    called = False

    async def _boom() -> AllocationLookupResult | None:
        nonlocal called
        called = True
        return None

    monkeypatch.setattr(lookup, "find_active", _boom)
    await sub.apply(other, AsyncMock())

    assert called is False


class _ConflictOnceStore:
    """Wraps a store to raise ConcurrencyError on the FIRST append only,
    simulating a benign concurrent write (an operator update) landing
    between the sealer's load and its append."""

    def __init__(self, delegate: InMemoryEventStore) -> None:
        self._delegate = delegate
        self._append_calls = 0

    async def load(self, stream_type: str, stream_id: UUID) -> Any:
        return await self._delegate.load(stream_type, stream_id)

    async def append(
        self,
        *,
        stream_type: str,
        stream_id: UUID,
        expected_version: int,
        events: Any,
    ) -> Any:
        self._append_calls += 1
        if self._append_calls == 1:
            raise ConcurrencyError(
                stream_type=stream_type,
                stream_id=stream_id,
                expected=expected_version,
                actual=expected_version + 1,
            )
        return await self._delegate.append(
            stream_type=stream_type,
            stream_id=stream_id,
            expected_version=expected_version,
            events=events,
        )


@pytest.mark.unit
async def test_seal_retries_past_a_benign_concurrent_write() -> None:
    """A concurrent update bumps the version between load and append; the
    sealer re-loads and retries rather than forfeiting the automatic
    seal. The envelope ends Sealed after the retry."""
    store = InMemoryEventStore()
    allocation_id = uuid4()
    await _seed_active_allocation(store, allocation_id, campaign_id=_CAMPAIGN_ID)
    conflict_store = _ConflictOnceStore(store)
    sub = AllocationSealerSubscriber(
        event_store=conflict_store,  # type: ignore[arg-type]
        allocation_lookup=_FakeAllocationLookup(_active_row(allocation_id, _CAMPAIGN_ID)),
        spend_lookup=_FakeTotalSpendLookup(total_usd_spent=12.5),  # type: ignore[arg-type]
    )

    await sub.apply(_campaign_closed(_CAMPAIGN_ID), AsyncMock())

    assert conflict_store._append_calls == 2  # one conflict, one success
    state = await load_allocation(store, allocation_id)
    assert state is not None
    assert state.status is AllocationStatus.SEALED
    assert state.spent_usd_at_seal == 12.5
