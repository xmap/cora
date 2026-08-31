"""In-memory `EventActivityTrail` for tests and `app_env=test`.

Wraps an `InMemoryEventStore` instance directly (constructor takes the
concrete class, not the `EventStore` Protocol) because it needs
`all_events()`, which is not on the port every other consumer sees --
mirrors `InMemoryRunObservationTrail` wrapping the concrete
`InMemoryObservationStore` for the same reason.
"""

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.ports.event_activity_trail import EventActivityCursor, EventActivityRow

_SENTINEL_CURSOR = EventActivityCursor(transaction_id="0", position=0)


def _cursor_key(cursor: EventActivityCursor) -> tuple[int, int]:
    return int(cursor.transaction_id), cursor.position


class InMemoryEventActivityTrail:
    def __init__(self, store: InMemoryEventStore) -> None:
        self._store = store

    async def head(self) -> EventActivityCursor:
        events = self._store.all_events()
        if not events:
            return _SENTINEL_CURSOR
        last = max(events, key=lambda e: (e.transaction_id, e.position))
        return EventActivityCursor(transaction_id=str(last.transaction_id), position=last.position)

    async def read_since(
        self, *, cursor: EventActivityCursor, limit: int
    ) -> tuple[list[EventActivityRow], EventActivityCursor]:
        cursor_key = _cursor_key(cursor)
        all_events = self._store.all_events()
        newer = sorted(
            (e for e in all_events if (e.transaction_id, e.position) > cursor_key),
            key=lambda e: (e.transaction_id, e.position),
        )[:limit]
        if not newer:
            return [], cursor
        # Stands in for the Postgres adapter's LEFT JOIN on `event_id`. Built
        # over every event in the store, not just the page being returned: a
        # cause is usually older than the page that carries its effect, so
        # resolving against `newer` alone would report almost every cause as
        # unresolvable and the two adapters would disagree.
        occurred_by_event_id = {e.event_id: e.occurred_at for e in all_events}
        rows = [
            EventActivityRow(
                event_id=event.event_id,
                stream_type=event.stream_type,
                stream_id=event.stream_id,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                recorded_at=event.recorded_at,
                correlation_id=event.correlation_id,
                causation_id=event.causation_id,
                cause_occurred_at=(
                    occurred_by_event_id.get(event.causation_id)
                    if event.causation_id is not None
                    else None
                ),
            )
            for event in newer
        ]
        last = newer[-1]
        next_cursor = EventActivityCursor(
            transaction_id=str(last.transaction_id), position=last.position
        )
        return rows, next_cursor
