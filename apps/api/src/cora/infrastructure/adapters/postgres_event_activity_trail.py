"""asyncpg-backed `EventActivityTrail` over the global `events` table.

The advance query is the canonical Khyst+Dudycz shape already proven by
`cora.infrastructure.projection.worker._ADVANCE_SQL`, minus the
`event_type = ANY(...)` allowlist (this trail wants every stream type, not
one projection's declared subscription) and minus every payload-bearing
column (see the port module docstring for why). Both queries ride the same
`events_advance_idx (transaction_id, position)` index added in migration
`20260512240000_add_transaction_id_to_events.sql`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress at module level for the adapter.

import asyncpg

from cora.infrastructure.ports.event_activity_trail import EventActivityCursor, EventActivityRow

_HEAD_SQL = """
SELECT transaction_id::text AS transaction_id_text, position
FROM events
ORDER BY transaction_id DESC, position DESC
LIMIT 1
"""

_READ_SINCE_SQL = """
SELECT e.stream_type, e.stream_id, e.event_type, e.occurred_at, e.recorded_at,
       e.correlation_id, e.causation_id, cause.occurred_at AS cause_occurred_at,
       e.transaction_id::text AS transaction_id_text, e.position
FROM events e
LEFT JOIN events cause ON cause.event_id = e.causation_id
WHERE (e.transaction_id, e.position) > ($1::xid8, $2)
  AND e.transaction_id < pg_snapshot_xmin(pg_current_snapshot())
ORDER BY e.transaction_id ASC, e.position ASC
LIMIT $3
"""
"""The LEFT JOIN rides `events_event_id_unique`, so resolving a cause is one
index lookup per row and at most `limit` of them. It is LEFT rather than
INNER because a null `causation_id` is the common case, not an anomaly: every
operator-originated command arrives over REST with no cause, and an INNER
join would silently drop exactly those rows."""

# xid8 0 is Postgres's own invalid-transaction-id sentinel: never assigned
# to a real transaction, so it compares strictly less than any row that
# will ever exist. Used only when `events` is empty at `head()` time.
_SENTINEL_CURSOR = EventActivityCursor(transaction_id="0", position=0)


class PostgresEventActivityTrail:
    """Production `EventActivityTrail`; reads `events` directly, no BC import."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def head(self) -> EventActivityCursor:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_HEAD_SQL)
        if row is None:
            return _SENTINEL_CURSOR
        return EventActivityCursor(
            transaction_id=row["transaction_id_text"], position=row["position"]
        )

    async def read_since(
        self, *, cursor: EventActivityCursor, limit: int
    ) -> tuple[list[EventActivityRow], EventActivityCursor]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _READ_SINCE_SQL, int(cursor.transaction_id), cursor.position, limit
            )
        if not rows:
            return [], cursor
        activity = [
            EventActivityRow(
                stream_type=row["stream_type"],
                stream_id=row["stream_id"],
                event_type=row["event_type"],
                occurred_at=row["occurred_at"],
                recorded_at=row["recorded_at"],
                correlation_id=row["correlation_id"],
                causation_id=row["causation_id"],
                cause_occurred_at=row["cause_occurred_at"],
            )
            for row in rows
        ]
        last = rows[-1]
        next_cursor = EventActivityCursor(
            transaction_id=last["transaction_id_text"], position=last["position"]
        )
        return activity, next_cursor
