"""An `EventStore` that reads but refuses to append.

Wraps the real store when the process booted against a schema it does not
expect and an operator explicitly asked for that rather than a refusal
(`allow_schema_version_mismatch`, see `schema_version`). Reading a
restored database is useful and harmless. Writing to one is neither: the
event log is append-only at the role level, so a bad append is history
rather than a row to correct.

## Why a wrapper and not a flag

Same reasoning as `ReadOnlyControlPort`: this refuses at CONSTRUCTION.
The composition root decides once, and every call site downstream holds a
store that cannot write, rather than one that consults a flag and could
be reached on a path that forgets to. There is no compensating action
available after a wrong append, so there is no room for a gate that can
be talked past.

## Completeness

`EventStore` has exactly three methods and this covers all three. Nothing
in `src/` reaches an event store by `getattr` or narrows one by
`isinstance`, so unlike the ControlPort registry (whose `aclose` lookup
made a partial wrapper leak connections) there is no attribute a wrapper
can hide by omission. `test_read_only_event_store_covers_protocol` pins
that: it fails if `EventStore` grows a method this class does not.

## Scope: this guards the event log, NOT every write

Say this precisely, because the tempting summary ("degraded means writes
are off") is not true. Each BC builds its own Postgres-backed stores from
`deps.pool` in `wire_<bc>(deps)` (Decision's `InferenceStore`,
Operation's `ActivityStore` and `OutcomeStore`, Run's
`ObservationStore`, and the projection workers). None of those pass
through this wrapper, so a degraded process can still write to them.

That is a deliberate ordering rather than an oversight. The event log is
the append-only record of truth and cannot be corrected once written;
everything listed above is derived state that a rebuild reconstructs from
those events. Protecting the irreversible thing first is the whole
trade. Widening the guard to those stores means a port each, and the
trigger for doing it is a real incident in one of them, not this comment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from cora.infrastructure.ports.event_store import (
        EventStore,
        NewEvent,
        StoredEvent,
        StreamAppend,
    )


class EventWritesDisabledError(RuntimeError):
    """An append was attempted on a store that boots read-only.

    Mirrors `ControlWritesDisabledError` in shape and intent: named for
    the refusal, raised before any substrate is contacted.
    """

    def __init__(self, applied: str, expected: str) -> None:
        super().__init__(
            f"Refusing to write: this process booted against a schema it does "
            f"not expect.\n"
            f"\n"
            f"  database is at   {applied}\n"
            f"  this build needs {expected}\n"
            f"\n"
            f"It started anyway because the mismatch was explicitly allowed, "
            f"which permits reading a restored database and nothing else. "
            f"Events are append-only, so a write here could not be undone.\n"
            f"\n"
            f"To write: bring the schema and the image into agreement, then "
            f"restart without the override."
        )
        self.applied = applied
        self.expected = expected


class ReadOnlyEventStore:
    """Delegates `load`, refuses `append` and `append_streams`.

    The versions are carried rather than re-read so the refusal can name
    both sides of the mismatch. A caller who hits this is usually not the
    operator who set the override, and "writes are off" without the two
    numbers leaves them guessing at why.
    """

    def __init__(self, inner: EventStore, *, applied: str, expected: str) -> None:
        self._inner = inner
        self._applied = applied
        self._expected = expected

    async def load(
        self,
        stream_type: str,
        stream_id: UUID,
    ) -> tuple[list[StoredEvent], int]:
        return await self._inner.load(stream_type, stream_id)

    async def append(
        self,
        stream_type: str,
        stream_id: UUID,
        expected_version: int,
        events: Sequence[NewEvent],
    ) -> int:
        raise EventWritesDisabledError(self._applied, self._expected)

    async def append_streams(
        self,
        streams: Sequence[StreamAppend],
        *,
        conn: object | None = None,
    ) -> dict[UUID, int]:
        raise EventWritesDisabledError(self._applied, self._expected)


__all__ = ["EventWritesDisabledError", "ReadOnlyEventStore"]
