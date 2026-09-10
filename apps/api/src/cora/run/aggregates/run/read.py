"""Read repository for the Run aggregate.

`load_run(event_store, run_id) -> Run | None` mirrors `load_plan` /
`load_practice` / `load_method` / `load_family` / `load_actor` /
`load_subject` / `load_asset`. Used by the `get_run` query slice
(6f-1) and any future update-style commands (6f-2+).

`load_run_ended_at` answers a question the fold cannot: WHEN the Run
reached its terminal. `Run` state carries the terminal STATUS but no
terminal timestamp, so the fact survives only on the event envelope
and `load_run` discards it. See that function for why the answer is
not taken from `proj_run_summary` instead.
"""

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports import EventStore
from cora.run.aggregates.run.events import (
    RunAborted,
    RunCompleted,
    RunStopped,
    RunTruncated,
    from_stored,
)
from cora.run.aggregates.run.evolver import fold
from cora.run.aggregates.run.state import Run

_STREAM_TYPE = "Run"

# The four reachable terminals (see `RunStatus`). Matched by TYPE rather
# than by taking the last event on the stream: "last event" would
# silently start answering a different question the day any event is
# appended after a terminal.
_TERMINAL_EVENTS = (RunCompleted, RunAborted, RunStopped, RunTruncated)


async def load_run(event_store: EventStore, run_id: UUID) -> Run | None:
    """Load and fold a Run's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, run_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


async def load_run_ended_at(event_store: EventStore, run_id: UUID) -> datetime | None:
    """`occurred_at` of the Run's terminal event, or None when the Run
    is still open, absent, or holds no terminal event.

    Deliberately NOT read from `proj_run_summary.updated_at`: that
    column is `now()` at PROJECTION-WRITE time, which is a different
    instant from the terminal's `occurred_at`, is mutable, and is
    re-derived on every replay. A caller comparing it against a fact
    from outside CORA would be comparing against CORA's own bookkeeping
    rather than against the record.

    Walks from the END of the stream so a terminal Run deserializes one
    event rather than the whole history; an open Run pays a full walk,
    which is the case that returns None and does no further work.
    """
    stored, _version = await event_store.load(_STREAM_TYPE, run_id)
    for raw in reversed(stored):
        event = from_stored(raw)
        if isinstance(event, _TERMINAL_EVENTS):
            return event.occurred_at
    return None
