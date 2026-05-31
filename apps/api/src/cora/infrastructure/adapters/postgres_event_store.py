"""Postgres-backed `EventStore` adapter.

Optimistic concurrency is enforced by the `events_stream_version_unique`
UNIQUE constraint on `(stream_type, stream_id, version)`. On conflict the
adapter reads the current version and raises `ConcurrencyError` so the
caller can retry with a fresh load.

The `events_event_id_unique` UNIQUE INDEX on `event_id` is a separate
constraint that producers should never violate (UUIDv7 collisions are
astronomically unlikely; a violation indicates a wrapper that's reusing
an id from a cached generator). The adapter inspects the violated
constraint name and re-raises the original `UniqueViolationError`
unchanged for that case so the bug surfaces loudly rather than being
mis-mapped to ConcurrencyError.

Append is wrapped in a single transaction so partial writes never appear
to readers. The AFTER INSERT trigger fires `pg_notify` per row (see
migration `20260509120000_init_events.sql`); listeners use that as a
wake-up signal and always poll from a persisted watermark to recover any
missed notifications.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress only at module level for the
# adapter file. The port + StoredEvent fields keep typing strict for
# every caller above the boundary.

from collections.abc import Sequence
from typing import Any
from uuid import UUID

import asyncpg

from cora.infrastructure.ports.event_store import (
    ConcurrencyError,
    NewEvent,
    StoredEvent,
    StreamAppend,
)

_LOAD_SQL = """
SELECT position, event_id, stream_type, stream_id, version, event_type,
       schema_version, payload, metadata, correlation_id, causation_id,
       principal_id, occurred_at, recorded_at,
       signature, signature_kid, signature_version,
       transaction_id::text AS transaction_id_text
FROM events
WHERE stream_type = $1 AND stream_id = $2
ORDER BY version
"""
# asyncpg 0.31 + PG18 has no built-in OUTPUT codec for xid8, so we
# cast to text in the SELECT and parse to Python int in `_row_to_event`.
# (Empirically verified by `tests/integration/test_event_store_xid8_postgres.py`.)
# On the INPUT side asyncpg accepts a Python int for an `$1::xid8`
# parameter — the projection-bookmark UPDATE (when 8e-1 lands) will
# pass int directly without the text round-trip.

_APPEND_SQL = """
INSERT INTO events (
    event_id, stream_type, stream_id, version, event_type, schema_version,
    payload, metadata, correlation_id, causation_id, occurred_at,
    principal_id, signature, signature_kid, signature_version
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
"""

_CURRENT_VERSION_SQL = """
SELECT COALESCE(MAX(version), 0) FROM events
WHERE stream_type = $1 AND stream_id = $2
"""

_STREAM_VERSION_CONSTRAINT = "events_stream_version_unique"


class PostgresEventStore:
    """asyncpg-backed `EventStore` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def load(
        self,
        stream_type: str,
        stream_id: UUID,
    ) -> tuple[list[StoredEvent], int]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_LOAD_SQL, stream_type, stream_id)
        events = [_row_to_event(row) for row in rows]
        version = events[-1].version if events else 0
        return events, version

    async def append(
        self,
        stream_type: str,
        stream_id: UUID,
        expected_version: int,
        events: Sequence[NewEvent],
    ) -> int:
        if not events:
            return expected_version
        result = await self.append_streams(
            [
                StreamAppend(
                    stream_type=stream_type,
                    stream_id=stream_id,
                    expected_version=expected_version,
                    events=events,
                )
            ]
        )
        return result[stream_id]

    async def append_streams(
        self,
        streams: Sequence[StreamAppend],
        *,
        conn: object | None = None,
    ) -> dict[UUID, int]:
        # Filter out empty-events StreamAppend entries (no-op rows still
        # report their expected_version so callers get a complete dict).
        non_empty = [s for s in streams if s.events]
        if not non_empty:
            return {s.stream_id: s.expected_version for s in streams}

        new_versions: dict[UUID, int] = {
            s.stream_id: s.expected_version for s in streams if not s.events
        }
        # Caller-supplied conn (forget_actor): run inside their
        # transaction; do NOT open a nested one. None: acquire from
        # pool + open the adapter's own transaction (every other
        # caller's path). Both branches share the same INSERT body +
        # ConcurrencyError mapping below.
        if conn is not None:
            # Caller owns the transaction; if their outer block aborts
            # for any reason after this call returns, the appends roll
            # back too.
            return await self._append_in_conn(
                conn,  # type: ignore[arg-type]
                non_empty,
                new_versions,
            )
        try:
            async with self._pool.acquire() as conn, conn.transaction():
                for stream in non_empty:
                    next_version = stream.expected_version
                    for event in stream.events:
                        next_version += 1
                        await conn.execute(
                            _APPEND_SQL,
                            event.event_id,
                            stream.stream_type,
                            stream.stream_id,
                            next_version,
                            event.event_type,
                            event.schema_version,
                            event.payload,
                            event.metadata,
                            event.correlation_id,
                            event.causation_id,
                            event.occurred_at,
                            event.principal_id,
                            event.signature,
                            event.signature_kid,
                            event.signature_version,
                        )
                    new_versions[stream.stream_id] = next_version
                return new_versions
        except asyncpg.UniqueViolationError as exc:
            # Stream-version constraint -> retry-able ConcurrencyError.
            # Any other constraint (today: events_event_id_unique) is a
            # producer bug; re-raise unchanged. Whole batch rolled back.
            if getattr(exc, "constraint_name", None) != _STREAM_VERSION_CONSTRAINT:
                raise
            # The exception's detail string carries the conflicting row;
            # we re-query each stream's current version to find the
            # offender. asyncpg exposes the original key via `exc.detail`
            # but parsing is fragile; do a per-stream lookup instead.
            async with self._pool.acquire() as fresh:
                for stream in non_empty:
                    actual = await fresh.fetchval(
                        _CURRENT_VERSION_SQL, stream.stream_type, stream.stream_id
                    )
                    actual_int = int(actual or 0)
                    if actual_int != stream.expected_version:
                        raise ConcurrencyError(
                            stream_type=stream.stream_type,
                            stream_id=stream.stream_id,
                            expected=stream.expected_version,
                            actual=actual_int,
                        ) from exc
            # Defensive: a stream-version UniqueViolation must map to a
            # mismatch somewhere; re-raise if we somehow can't pin it.
            raise

    async def _append_in_conn(
        self,
        conn: asyncpg.Connection,
        non_empty: Sequence[StreamAppend],
        new_versions: dict[UUID, int],
    ) -> dict[UUID, int]:
        # Same INSERT body as `append_streams` but runs against the
        # caller's connection without opening a nested transaction.
        # The caller (forget_actor) wraps the call in its own
        # `conn.transaction()` so the scrub+delete+append commit
        # atomically. ConcurrencyError mapping is identical (the
        # UniqueViolationError still names `_STREAM_VERSION_CONSTRAINT`);
        # the lookup uses a SEPARATE pool connection because the
        # caller's transaction is aborted by the exception and can't
        # be reused.
        try:
            for stream in non_empty:
                next_version = stream.expected_version
                for event in stream.events:
                    next_version += 1
                    await conn.execute(
                        _APPEND_SQL,
                        event.event_id,
                        stream.stream_type,
                        stream.stream_id,
                        next_version,
                        event.event_type,
                        event.schema_version,
                        event.payload,
                        event.metadata,
                        event.correlation_id,
                        event.causation_id,
                        event.occurred_at,
                        event.principal_id,
                        event.signature,
                        event.signature_kid,
                        event.signature_version,
                    )
                new_versions[stream.stream_id] = next_version
            return new_versions
        except asyncpg.UniqueViolationError as exc:
            if getattr(exc, "constraint_name", None) != _STREAM_VERSION_CONSTRAINT:
                raise
            async with self._pool.acquire() as fresh:
                for stream in non_empty:
                    actual = await fresh.fetchval(
                        _CURRENT_VERSION_SQL, stream.stream_type, stream.stream_id
                    )
                    actual_int = int(actual or 0)
                    if actual_int != stream.expected_version:
                        raise ConcurrencyError(
                            stream_type=stream.stream_type,
                            stream_id=stream.stream_id,
                            expected=stream.expected_version,
                            actual=actual_int,
                        ) from exc
            raise


def _row_to_event(row: Any) -> StoredEvent:
    payload: dict[str, Any] = row["payload"]
    metadata: dict[str, Any] = row["metadata"]
    return StoredEvent(
        position=int(row["position"]),
        event_id=row["event_id"],
        stream_type=str(row["stream_type"]),
        stream_id=row["stream_id"],
        version=int(row["version"]),
        event_type=str(row["event_type"]),
        schema_version=int(row["schema_version"]),
        payload=payload,
        metadata=metadata,
        correlation_id=row["correlation_id"],
        causation_id=row["causation_id"],
        occurred_at=row["occurred_at"],
        recorded_at=row["recorded_at"],
        transaction_id=int(row["transaction_id_text"]),
        principal_id=row["principal_id"],
        signature=row["signature"],
        signature_kid=row["signature_kid"],
        signature_version=row["signature_version"],
    )
