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

from datetime import datetime
from typing import TYPE_CHECKING, cast

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


def extract_capture_progress(event: StoredEvent) -> dict[str, int] | None:
    """Pull the frame tallies from a terminal-Run event's progress snapshot.

    Present on terminal events for witnessed captures, absent otherwise,
    so `None` is an ordinary answer rather than a fault.

    Counts arrive as floats because they come off numeric PVs; they are
    coerced to int here because a frame count of `1530.0` invites a
    reader, human or model, to wonder what the fraction means.

    Names are symmetric on purpose: `frames_saved` /
    `frames_saved_expected` and `frames_collected` /
    `frames_collected_expected`. An earlier cut called the first total
    `frames_expected`, which read like a grand total the collected count
    fell short of, and a model duly compared 1541 saved against 10
    collected and reported a "substantial data shortfall" on a scan that
    was complete on both counters. The two are independently sourced
    upstream (FPNumCapture against CamNumImages) and are only ever
    comparable WITHIN a pair; the naming now says so without needing the
    prompt to.

    Carries the four tallies AND how stale the reading was, because the
    tallies alone are not interpretable. `CaptureProgressSnapshot`
    documents why: these are the last counts that REACHED CORA before
    the terminal, so a count short of its total may mean frames were
    lost or may only mean the last reading arrived early. The VO
    deliberately exposes no `all_counts_matched`, precisely to refuse
    that verdict.

    Measured on 2-BM's record 2026-08-19, the distinction is not
    hypothetical: across 609 completions, those showing a shortfall had
    a mean reading lag of 70 s against 12 s for those showing none, and
    the shortfall tracked the lag. Handing a model the counts without
    the lag would invite it to report data loss from what looks like a
    telemetry stall.

    The VO's docstring names this comparison as the one a reader should
    make, so computing it here is sanctioned; what stays refused is
    turning it into a completeness judgment.
    """
    raw = event.payload.get("capture_progress_snapshot")
    if not isinstance(raw, dict):
        return None
    snapshot = cast("dict[str, object]", raw)
    tallies: dict[str, int] = {}
    lag = _reading_lag_seconds(snapshot.get("saved_at"), event.payload.get("observed_at"))
    if lag is not None:
        tallies["reading_age_seconds_before_terminal"] = lag
    for source, name in (
        ("saved_count", "frames_saved"),
        ("saved_total", "frames_saved_expected"),
        ("collected_count", "frames_collected"),
        ("collected_total", "frames_collected_expected"),
    ):
        value = snapshot.get(source)
        if isinstance(value, (int, float)):
            tallies[name] = int(value)
    return tallies or None


def _reading_lag_seconds(saved_at: object, observed_at: object) -> int | None:
    """How old the last progress reading was when the Run terminated.

    `None` when either timestamp is missing or unparseable, which is an
    ordinary answer: a deployment that reports no progress at all has no
    lag to report either.
    """
    if not isinstance(saved_at, str) or not isinstance(observed_at, str):
        return None
    try:
        taken = datetime.fromisoformat(saved_at)
        ended = datetime.fromisoformat(observed_at)
    except ValueError:
        return None
    return max(0, int((ended - taken).total_seconds()))


def extract_interrupted_at(event: StoredEvent) -> str | None:
    """Pull `interrupted_at` from a terminal-Run event payload.

    `RunTruncated`-only field; absent on every other terminal type.
    """
    interrupted_at = event.payload.get("interrupted_at")
    return str(interrupted_at) if interrupted_at is not None else None


__all__ = [
    "TERMINAL_RUN_EVENTS",
    "extract_capture_progress",
    "extract_interrupted_at",
    "extract_reason",
    "find_terminal_run_event",
]
