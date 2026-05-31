"""In-memory `EventStore` for unit tests and the `test` app environment.

Mirrors the Postgres adapter's contract: same optimistic-concurrency
semantics, same global ordering by an in-memory monotonic position counter,
same per-stream version invariants, AND the same `event_id` UNIQUE
constraint (a duplicate `event_id` in any append raises ValueError so
test failures match what production would surface as a Postgres
UniqueViolationError). A `threading.Lock` guards the dict and the position
counter so the same instance can be safely shared across concurrent
tasks (we hold the lock only across pure in-memory work, never across
awaits).
"""

from collections.abc import Sequence
from copy import deepcopy
from datetime import UTC, datetime
from itertools import count
from threading import Lock
from uuid import UUID

from cora.infrastructure.ports.event_store import (
    ConcurrencyError,
    NewEvent,
    StoredEvent,
    StreamAppend,
)


class InMemoryEventStore:
    """Thread-safe in-memory implementation of the EventStore port."""

    def __init__(self) -> None:
        self._streams: dict[tuple[str, UUID], list[StoredEvent]] = {}
        self._event_ids: set[UUID] = set()
        self._position = count(start=1)
        # Fake xid8: monotonic per append() call. All events in the same
        # batch share a transaction_id (mirrors Postgres semantics where
        # one transaction can emit N events). Starts at a non-zero value
        # so the bookmark sentinel ('0'::xid8 in production, 0 here)
        # compares strictly less than any real value.
        self._transaction_id = count(start=1)
        self._lock = Lock()

    async def load(
        self,
        stream_type: str,
        stream_id: UUID,
    ) -> tuple[list[StoredEvent], int]:
        with self._lock:
            events = list(self._streams.get((stream_type, stream_id), []))
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
        # `conn` parameter on the EventStore port lets forget_actor
        # bundle a profile_store.scrub_and_delete + this append in one
        # Postgres transaction. In-memory has no transaction concept;
        # the contract is preserved at the type level.
        _ = conn
        non_empty = [s for s in streams if s.events]
        if not non_empty:
            return {s.stream_id: s.expected_version for s in streams}

        with self._lock:
            # Pre-validate ALL streams' expected_version + event_id
            # uniqueness BEFORE mutating any state. All-or-nothing.
            for stream in non_empty:
                key = (stream.stream_type, stream.stream_id)
                existing = self._streams.get(key)
                actual = existing[-1].version if existing else 0
                if actual != stream.expected_version:
                    raise ConcurrencyError(
                        stream_type=stream.stream_type,
                        stream_id=stream.stream_id,
                        expected=stream.expected_version,
                        actual=actual,
                    )

            # event_id uniqueness across the entire multi-stream batch +
            # against already-stored ids.
            all_new_ids: list[UUID] = [
                event.event_id for stream in non_empty for event in stream.events
            ]
            if len(set(all_new_ids)) != len(all_new_ids):
                msg = "Duplicate event_id within a single append_streams batch"
                raise ValueError(msg)
            collisions = self._event_ids.intersection(all_new_ids)
            if collisions:
                msg = f"event_id already exists: {sorted(str(i) for i in collisions)}"
                raise ValueError(msg)

            # Mutate state. All streams share the same fake xid8 to
            # mirror Postgres's "one transaction = one xid8" semantic.
            now = datetime.now(tz=UTC)
            tx_id = next(self._transaction_id)
            new_versions: dict[UUID, int] = {
                s.stream_id: s.expected_version for s in streams if not s.events
            }
            for stream in non_empty:
                key = (stream.stream_type, stream.stream_id)
                existing = self._streams.get(key)
                if existing is None:
                    existing = []
                    self._streams[key] = existing
                next_version = stream.expected_version
                for event in stream.events:
                    next_version += 1
                    stored = StoredEvent(
                        position=next(self._position),
                        event_id=event.event_id,
                        stream_type=stream.stream_type,
                        stream_id=stream.stream_id,
                        version=next_version,
                        event_type=event.event_type,
                        schema_version=event.schema_version,
                        payload=deepcopy(event.payload),
                        metadata=deepcopy(event.metadata),
                        correlation_id=event.correlation_id,
                        causation_id=event.causation_id,
                        occurred_at=event.occurred_at,
                        recorded_at=now,
                        transaction_id=tx_id,
                        principal_id=event.principal_id,
                        signature=event.signature,
                        signature_kid=event.signature_kid,
                        signature_version=event.signature_version,
                    )
                    existing.append(stored)
                    self._event_ids.add(event.event_id)
                new_versions[stream.stream_id] = next_version
            return new_versions
