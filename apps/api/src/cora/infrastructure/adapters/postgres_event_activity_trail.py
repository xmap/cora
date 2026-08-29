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
SELECT stream_type, stream_id, event_type, occurred_at, recorded_at,
       transaction_id::text AS transaction_id_text, position
FROM events
WHERE (transaction_id, position) > ($1::xid8, $2)
  AND transaction_id < pg_snapshot_xmin(pg_current_snapshot())
ORDER BY transaction_id ASC, position ASC
LIMIT $3
"""

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
            )
            for row in rows
        ]
        last = rows[-1]
        next_cursor = EventActivityCursor(
            transaction_id=last["transaction_id_text"], position=last["position"]
        )
        return activity, next_cursor
