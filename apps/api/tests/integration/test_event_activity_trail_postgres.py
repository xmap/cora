"""Integration: PostgresEventActivityTrail against real Postgres.

Seeds rows through the real `PostgresEventStore` (so `transaction_id` and
`position` are real DB round-trips, exercising the same
`events_advance_idx (transaction_id, position)` index the projection
worker's own advance query rides), then reads them back through the
trail. The `events` table is never empty at test start (migrations seed
bootstrap Policy/Actor events), so every test establishes its own
baseline via `head()` first, mirroring `test_decision_tail_starts_empty_
even_with_existing_decisions`'s pattern rather than assuming a clean table.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.adapters.postgres_event_activity_trail import (
    PostgresEventActivityTrail,
)
from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.ports.event_store import NewEvent

_NOW = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)


async def _write_event(
    store: PostgresEventStore,
    *,
    stream_type: str = "Run",
    stream_id: UUID | None = None,
    event_type: str = "RunStarted",
    event_id: UUID | None = None,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
    occurred_at: datetime = _NOW,
) -> UUID:
    stream_id = stream_id or uuid4()
    await store.append(
        stream_type,
        stream_id,
        0,
        [
            NewEvent(
                event_id=event_id or uuid4(),
                event_type=event_type,
                schema_version=1,
                payload={"irrelevant": "never read back by this trail"},
                occurred_at=occurred_at,
                correlation_id=correlation_id or uuid4(),
                causation_id=causation_id,
                principal_id=None,
            )
        ],
    )
    return stream_id


@pytest.mark.integration
async def test_head_then_read_since_sees_only_rows_written_after_head(
    db_pool: asyncpg.Pool,
) -> None:
    store = PostgresEventStore(db_pool)
    trail = PostgresEventActivityTrail(db_pool)

    baseline = await trail.head()
    stream_id = await _write_event(store)

    rows, _next = await trail.read_since(cursor=baseline, limit=10)

    assert [r.stream_id for r in rows] == [stream_id]


@pytest.mark.integration
async def test_read_since_returns_the_same_cursor_when_nothing_is_new(
    db_pool: asyncpg.Pool,
) -> None:
    trail = PostgresEventActivityTrail(db_pool)
    baseline = await trail.head()

    rows, next_cursor = await trail.read_since(cursor=baseline, limit=10)

    assert rows == []
    assert next_cursor == baseline


@pytest.mark.integration
async def test_read_since_never_returns_the_payload(db_pool: asyncpg.Pool) -> None:
    store = PostgresEventStore(db_pool)
    trail = PostgresEventActivityTrail(db_pool)
    baseline = await trail.head()

    await _write_event(store)
    rows, _next = await trail.read_since(cursor=baseline, limit=10)

    assert len(rows) == 1
    assert not hasattr(rows[0], "payload")


@pytest.mark.integration
async def test_read_since_round_trips_stream_type_and_event_type(db_pool: asyncpg.Pool) -> None:
    store = PostgresEventStore(db_pool)
    trail = PostgresEventActivityTrail(db_pool)
    baseline = await trail.head()

    await _write_event(store, stream_type="Decision", event_type="DecisionMade")
    rows, _next = await trail.read_since(cursor=baseline, limit=10)

    assert len(rows) == 1
    assert rows[0].stream_type == "Decision"
    assert rows[0].event_type == "DecisionMade"


@pytest.mark.integration
async def test_read_since_advances_the_cursor_so_a_second_call_sees_nothing_new(
    db_pool: asyncpg.Pool,
) -> None:
    store = PostgresEventStore(db_pool)
    trail = PostgresEventActivityTrail(db_pool)
    cursor = await trail.head()

    await _write_event(store)
    first_rows, cursor = await trail.read_since(cursor=cursor, limit=10)
    second_rows, _cursor = await trail.read_since(cursor=cursor, limit=10)

    assert len(first_rows) == 1
    assert second_rows == []


@pytest.mark.integration
async def test_read_since_carries_correlation_and_a_null_cause_for_an_operator_command(
    db_pool: asyncpg.Pool,
) -> None:
    """A command arriving over REST has no `causation_id`. That is the common
    case, not an anomaly, so the LEFT JOIN must return the row rather than
    filter it out the way an INNER join would."""
    store = PostgresEventStore(db_pool)
    trail = PostgresEventActivityTrail(db_pool)
    cursor = await trail.head()
    correlation_id = uuid4()

    await _write_event(store, correlation_id=correlation_id, causation_id=None)
    rows, _cursor = await trail.read_since(cursor=cursor, limit=10)

    assert len(rows) == 1
    assert rows[0].correlation_id == correlation_id
    assert rows[0].causation_id is None
    assert rows[0].cause_occurred_at is None


@pytest.mark.integration
async def test_read_since_resolves_the_cause_s_time_even_when_the_cause_is_not_in_the_page(
    db_pool: asyncpg.Pool,
) -> None:
    """The join resolves against the whole table, not the page being returned.
    A cause is almost always older than the effect that cites it, so a lookup
    limited to the current page would report nearly every cause unresolvable
    and hand the browser a window it cannot distinguish from "uncaused"."""
    store = PostgresEventStore(db_pool)
    trail = PostgresEventActivityTrail(db_pool)

    cause_event_id = uuid4()
    cause_at = datetime(2026, 6, 21, 11, 20, 0, tzinfo=UTC)
    await _write_event(store, event_id=cause_event_id, occurred_at=cause_at)

    # Baseline AFTER the cause, so the cause is deliberately outside the page.
    cursor = await trail.head()
    await _write_event(
        store,
        stream_type="Caution",
        event_type="CautionRegistered",
        causation_id=cause_event_id,
    )

    rows, _cursor = await trail.read_since(cursor=cursor, limit=10)

    assert len(rows) == 1
    assert rows[0].event_type == "CautionRegistered"
    assert rows[0].causation_id == cause_event_id
    assert rows[0].cause_occurred_at == cause_at


@pytest.mark.integration
async def test_read_since_limit_truncates_and_the_cursor_still_advances(
    db_pool: asyncpg.Pool,
) -> None:
    store = PostgresEventStore(db_pool)
    trail = PostgresEventActivityTrail(db_pool)
    cursor = await trail.head()

    ids = [await _write_event(store) for _ in range(5)]

    first_page, cursor = await trail.read_since(cursor=cursor, limit=3)
    second_page, _cursor = await trail.read_since(cursor=cursor, limit=3)

    assert [r.stream_id for r in first_page] == ids[:3]
    assert [r.stream_id for r in second_page] == ids[3:]
