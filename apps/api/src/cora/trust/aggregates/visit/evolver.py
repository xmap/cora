"""Evolver: replay events to reconstruct Visit state.

Mirror of the Campaign / Policy evolvers, generalized for Visit's 8-state
FSM. The terminal `assert_never` case forces pyright (and the runtime) to
error if a new event type is added to `VisitEvent` without a matching
match arm.

Non-genesis events update the existing state's `status` (and
`last_status_reason` when the event carries one), preserving everything
else. `last_status_reason` from VisitHeld / VisitCancelled / VisitAborted
/ VisitVoided is preserved on VisitResumed (audit breadcrumb survives).
"""

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from typing import assert_never

from cora.trust.aggregates.visit.events import (
    VisitAborted,
    VisitArrived,
    VisitCancelled,
    VisitCheckedIn,
    VisitCheckedOut,
    VisitCompleted,
    VisitEvent,
    VisitHeld,
    VisitPresenceClosed,
    VisitRegistered,
    VisitResumed,
    VisitStarted,
    VisitSurfaceControlReleased,
    VisitSurfaceControlTaken,
    VisitVoided,
)
from cora.trust.aggregates.visit.state import (
    PresenceEntry,
    PresenceMode,
    Visit,
    VisitStatus,
    VisitType,
)


def _closed_at(
    entries: frozenset[PresenceEntry], occurred_at: datetime
) -> frozenset[PresenceEntry]:
    """Close every open presence entry at `occurred_at`.

    A Visit reaching a terminal state ends presence by implication: nobody is
    at a beamline for a Visit that has completed, been cancelled, aborted, or
    voided. Deriving that here rather than emitting per-actor close events
    keeps the terminal deciders ignorant of presence, and means the closing
    timestamp is exactly the transition's own, with no second clock reading.

    Same frozen-replace shape as the `VisitCheckedOut` arm. Returns `entries`
    unchanged when nothing is open, so the common case allocates nothing.
    """
    open_entries = {e for e in entries if e.check_out_at is None}
    if not open_entries:
        return entries
    closed = {replace(e, check_out_at=occurred_at) for e in open_entries}
    return (entries - open_entries) | closed


def evolve(state: Visit | None, event: VisitEvent) -> Visit:
    """Apply one event to the current state."""
    match event:
        case VisitRegistered(
            visit_id=visit_id,
            policy_id=policy_id,
            surface_id=surface_id,
            type=type_,
            planned_start_at=planned_start_at,
            planned_end_at=planned_end_at,
            parent_id=parent_id,
            external_refs=external_refs,
        ):
            _ = state  # VisitRegistered is genesis; prior state ignored
            return Visit(
                id=visit_id,
                policy_id=policy_id,
                surface_id=surface_id,
                type=VisitType(type_),
                planned_start_at=planned_start_at,
                planned_end_at=planned_end_at,
                parent_id=parent_id,
                external_refs=external_refs,
                status=VisitStatus.PLANNED,
                last_status_reason=None,
            )
        case VisitArrived():
            assert state is not None, "VisitArrived requires prior state"
            return replace(state, status=VisitStatus.ARRIVED)
        case VisitStarted():
            assert state is not None, "VisitStarted requires prior state"
            return replace(state, status=VisitStatus.IN_PROGRESS)
        case VisitHeld(reason=reason):
            assert state is not None, "VisitHeld requires prior state"
            return replace(state, status=VisitStatus.ON_HOLD, last_status_reason=reason)
        case VisitResumed():
            assert state is not None, "VisitResumed requires prior state"
            # Preserve last_status_reason audit breadcrumb across resume.
            return replace(state, status=VisitStatus.IN_PROGRESS)
        case VisitCompleted(occurred_at=occurred_at):
            assert state is not None, "VisitCompleted requires prior state"
            return replace(
                state,
                status=VisitStatus.COMPLETED,
                presence_entries=_closed_at(state.presence_entries, occurred_at),
            )
        case VisitCancelled(reason=reason, occurred_at=occurred_at):
            assert state is not None, "VisitCancelled requires prior state"
            return replace(
                state,
                status=VisitStatus.CANCELLED,
                last_status_reason=reason,
                presence_entries=_closed_at(state.presence_entries, occurred_at),
            )
        case VisitAborted(reason=reason, occurred_at=occurred_at):
            assert state is not None, "VisitAborted requires prior state"
            return replace(
                state,
                status=VisitStatus.ABORTED,
                last_status_reason=reason,
                presence_entries=_closed_at(state.presence_entries, occurred_at),
            )
        case VisitVoided(reason=reason, occurred_at=occurred_at):
            assert state is not None, "VisitVoided requires prior state"
            return replace(
                state,
                status=VisitStatus.VOIDED,
                last_status_reason=reason,
                presence_entries=_closed_at(state.presence_entries, occurred_at),
            )
        case VisitCheckedIn(actor_id=actor_id, mode=mode, occurred_at=occurred_at):
            assert state is not None, "VisitCheckedIn requires prior state"
            # Set-union add. Decider has already guarded against open-entry duplicates;
            # full-4-tuple frozenset dedup catches event replay.
            new_entry = PresenceEntry(
                actor_id=actor_id,
                mode=PresenceMode(mode),
                check_in_at=occurred_at,
                check_out_at=None,
            )
            return replace(state, presence_entries=state.presence_entries | {new_entry})
        case (
            VisitCheckedOut(actor_id=actor_id, occurred_at=occurred_at)
            | VisitPresenceClosed(actor_id=actor_id, occurred_at=occurred_at)
        ):
            # One arm for both: the state change is identical and only the
            # cause differs, which the event TYPE already carries.
            assert state is not None, "presence-closing event requires prior state"
            # Frozen-replace: find the actor's OPEN entry, remove it, insert a new
            # entry with check_out_at populated. Old + new are distinct frozenset
            # members because PresenceEntry's hash covers all 4 fields. Decider
            # guarantees exactly one open entry exists.
            open_entry = next(
                e
                for e in state.presence_entries
                if e.actor_id == actor_id and e.check_out_at is None
            )
            closed_entry = PresenceEntry(
                actor_id=open_entry.actor_id,
                mode=open_entry.mode,
                check_in_at=open_entry.check_in_at,
                check_out_at=occurred_at,
            )
            return replace(
                state,
                presence_entries=(state.presence_entries - {open_entry}) | {closed_entry},
            )
        case VisitSurfaceControlTaken() | VisitSurfaceControlReleased():
            # Control events do not mutate aggregate state: the "who drives
            # now" concern lives entirely on the `proj_surface_active_visit`
            # projection so concurrent take/release cycles never collide
            # with the lifecycle FSM or presence collection.
            assert state is not None, "Control event requires prior state"
            return state
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[VisitEvent]) -> Visit | None:
    """Replay a stream of events from the empty initial state."""
    state: Visit | None = None
    for event in events:
        state = evolve(state, event)
    return state
