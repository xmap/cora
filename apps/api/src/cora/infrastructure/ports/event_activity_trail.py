"""`EventActivityTrail`: a bounded, cursor-following read over the global
`events` table, event metadata only.

Lives here rather than BC-local (contrast `run.ports.run_observation_trail`)
because its data source is the whole `events` table across every stream
type by construction, not one BC's own stream. It has exactly one consumer
today (the live status push's flowing-mode activity tail, constructed
directly inside `cora.api._status_push`), so it is not a `Kernel` field:
promoting a single-consumer port to the shared kernel would be the reverse
of the rule-of-three this codebase applies to new cross-cutting primitives.

Ships `stream_type`, `stream_id`, `event_type`, `occurred_at`, `recorded_at`
only. NEVER `payload`. `test_run_events_carry_no_pii.py` (and its Access-BC
sibling) are the only two fitness tests that guard event field names against
personal data, and they cover exactly two of the twenty-five stream types
this port's data spans; shipping raw payloads across every BC would carry
that guarantee somewhere it does not hold. A lane needs to know THAT
something happened and WHAT KIND, never the values inside it.

Cursor discipline mirrors `cora.infrastructure.ports.event_store`'s own
documented rule: `position` alone is unsafe (sequences advance on rollback,
and a later-started transaction can commit before an earlier one), so the
lexicographic `(transaction_id, position)` tuple with an in-flight
`pg_snapshot_xmin` exclusion is the only safe advance predicate. Copy the
query shape from `cora.infrastructure.projection.worker`'s `_ADVANCE_SQL`,
not the stream-load query.

Two methods, not one `read_since(cursor: Cursor | None, ...)`: `head()`
answers "start tailing from now, without replaying history" (the same
posture `_DecisionTail` takes by seeding its cursor at construction time),
so a caller establishing a fresh baseline never has to special-case a
`None` cursor inside the read path.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class EventActivityCursor:
    """Opaque advance position: the `(transaction_id, position)` tuple.
    `transaction_id` is carried as `str` (the DB's own `xid8::text` cast)
    since Python has no native 64-bit-unsigned-with-no-wraparound type
    mapping asyncpg trusts uniformly across both adapters."""

    transaction_id: str
    position: int


@dataclass(frozen=True)
class EventActivityRow:
    stream_type: str
    stream_id: UUID
    event_type: str
    occurred_at: datetime
    recorded_at: datetime


class EventActivityTrail(Protocol):
    async def head(self) -> EventActivityCursor:
        """The current tip of the global event stream. A caller that wants
        to start tailing from 'now' uses this as its first cursor, rather
        than replaying everything ever recorded."""
        ...

    async def read_since(
        self, *, cursor: EventActivityCursor, limit: int
    ) -> tuple[list[EventActivityRow], EventActivityCursor]:
        """Rows strictly after `cursor`, oldest-first, capped at `limit`.
        Returns the cursor to use on the next call; when nothing matched,
        that is `cursor` unchanged, never `None`."""
        ...


__all__ = ["EventActivityCursor", "EventActivityRow", "EventActivityTrail"]
