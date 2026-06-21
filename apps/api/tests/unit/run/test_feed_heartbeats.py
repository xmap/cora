"""Unit tests for the feed-heartbeat store + read_feed_health stub.

The heartbeat is the dead-feeder seam: the InMemory store dedups on
event_id, and InMemoryRunChannelLookup.read_feed_health returns the
newest heartbeat recorded_at (None when no feeder has ever pinged), the
raw signal the decider turns into liveness.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cora.run.aggregates.run import FeedHeartbeat, InMemoryFeedHeartbeatStore
from cora.run.ports import InMemoryRunChannelLookup

_T0 = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)


def _at(seconds: int) -> datetime:
    return _T0 + timedelta(seconds=seconds)


@pytest.mark.unit
async def test_heartbeat_store_dedups_on_event_id() -> None:
    store = InMemoryFeedHeartbeatStore()
    event_id = uuid4()
    run_id = uuid4()
    first = FeedHeartbeat(event_id=event_id, run_id=run_id, source_id="epics", heartbeat_at=_at(0))
    second = FeedHeartbeat(event_id=event_id, run_id=run_id, source_id="epics", heartbeat_at=_at(9))
    await store.append([first])
    await store.append([second])
    assert store.all() == [first]


@pytest.mark.unit
async def test_read_feed_health_returns_none_when_never_pinged() -> None:
    """No feeder heartbeat -> None; the decider reads this as cannot-tell
    and defers the stall rule (never flags a dead feeder as a stall)."""
    lookup = InMemoryRunChannelLookup()
    health = await lookup.read_feed_health(run_id=uuid4())
    assert health.latest_heartbeat_recorded_at is None


@pytest.mark.unit
async def test_read_feed_health_returns_newest_heartbeat() -> None:
    lookup = InMemoryRunChannelLookup()
    run_id = uuid4()
    lookup.register_heartbeat(run_id=run_id, recorded_at=_at(10))
    lookup.register_heartbeat(run_id=run_id, recorded_at=_at(40))
    lookup.register_heartbeat(run_id=run_id, recorded_at=_at(25))
    health = await lookup.read_feed_health(run_id=run_id)
    assert health.latest_heartbeat_recorded_at == _at(40)
