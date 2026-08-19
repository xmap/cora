"""Shared payload extractors for subscribers that react to terminal Run events.

Hoisted at rule-of-three (two consumers today, third agent named
in the widening triggers). Only the OBVIOUSLY-stable
extractors live here; the `_compose_and_append` Decision-event
composer remains duplicated across `run_debriefer` and
`caution_drafter` until a third consumer reveals which seams
stabilize (per the simplification audit: deferred composer hoist
to avoid premature parameter-shuffler).

Both extractors are pure (no IO, no I/O ports) and `None`-tolerant:
new terminal event shapes (future) don't crash the consumer when
they omit one of these optional fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from cora.infrastructure.ports.event_store import EventStore, StoredEvent

TERMINAL_RUN_EVENTS = frozenset(
    {
        "RunCompleted",
        "RunAborted",
        "RunStopped",
        "RunTruncated",
    }
)
"""The four event types that end a Run.

Lives here rather than in the subscriber because the on-demand
regenerate path needs the same vocabulary to recover which terminal
event a completed Run actually had, and importing it back from the
subscriber would close an import cycle through this module.
"""


async def find_terminal_run_event(
    event_store: EventStore,
    run_id: UUID,
) -> StoredEvent | None:
    """Return the Run's most recent terminal event, or `None` if it has none.

    The subscriber is handed its terminal event by the projection and
    never needs this. The on-demand path has only a `run_id`, so it
    reads the stream back to find what actually ended the Run.

    Searches from the end because a Run stream can hold more than one
    terminal event in a compensation sequence, and the debrief concerns
    how the Run ended, not how it first tried to.
    """
    events, _ = await event_store.load("Run", run_id)
    for event in reversed(events):
        if event.event_type in TERMINAL_RUN_EVENTS:
            return event
    return None


def extract_reason(event: StoredEvent) -> str | None:
    """Pull the `reason` field from a terminal-Run event payload.

    `RunCompleted` has no `reason`; the other three (`RunAborted`,
    `RunStopped`, `RunTruncated`) carry it. Returns `None` when
    missing rather than KeyError-raising.
    """
    reason = event.payload.get("reason")
    return str(reason) if reason is not None else None


def extract_interrupted_at(event: StoredEvent) -> str | None:
    """Pull `interrupted_at` from a terminal-Run event payload.

    `RunTruncated`-only field; absent on every other terminal type.
    """
    interrupted_at = event.payload.get("interrupted_at")
    return str(interrupted_at) if interrupted_at is not None else None


__all__ = [
    "TERMINAL_RUN_EVENTS",
    "extract_interrupted_at",
    "extract_reason",
    "find_terminal_run_event",
]
