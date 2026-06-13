"""Visit aggregate: state, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.trust.features.<verb>_visit/` and import from here for state and
event types.

Per `[[project_visit_aggregate_design]]`, Visit is the operational-
envelope counterpart to Trust's authz-topology primitives. 8-state FSM
locked day one: Planned -> Arrived -> InProgress <-> OnHold ->
Completed; +Cancelled (pre-work) +Aborted (mid-work) +Voided
(registration-error). Concerns are layered as additive slices: lifecycle
(register + 8 transitions), presence (check-in / check-out), and
Surface control (take / release).
"""

from cora.trust.aggregates.visit.events import (
    VisitAborted,
    VisitArrived,
    VisitCancelled,
    VisitCheckedIn,
    VisitCheckedOut,
    VisitCompleted,
    VisitEvent,
    VisitHeld,
    VisitRegistered,
    VisitResumed,
    VisitStarted,
    VisitSurfaceControlReleased,
    VisitSurfaceControlTaken,
    VisitVoided,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.trust.aggregates.visit.evolver import evolve, fold
from cora.trust.aggregates.visit.read import (
    VisitLifecycleTimestamps,
    load_visit,
    load_visit_timestamps,
)
from cora.trust.aggregates.visit.state import (
    InvalidVisitPlannedPeriodError,
    InvalidVisitReasonError,
    PresenceEntry,
    PresenceMode,
    Visit,
    VisitActorNotCheckedInError,
    VisitAlreadyCheckedInError,
    VisitAlreadyExistsError,
    VisitCannotAbortError,
    VisitCannotArriveError,
    VisitCannotCancelError,
    VisitCannotCheckInError,
    VisitCannotCompleteError,
    VisitCannotHoldError,
    VisitCannotReleaseControlError,
    VisitCannotResumeError,
    VisitCannotStartError,
    VisitCannotTakeControlError,
    VisitCannotVoidError,
    VisitNotFoundError,
    VisitParentMismatchedSurfaceError,
    VisitParentNotFoundError,
    VisitStatus,
    VisitType,
)

__all__ = [
    "InvalidVisitPlannedPeriodError",
    "InvalidVisitReasonError",
    "PresenceEntry",
    "PresenceMode",
    "Visit",
    "VisitAborted",
    "VisitActorNotCheckedInError",
    "VisitAlreadyCheckedInError",
    "VisitAlreadyExistsError",
    "VisitArrived",
    "VisitCancelled",
    "VisitCannotAbortError",
    "VisitCannotArriveError",
    "VisitCannotCancelError",
    "VisitCannotCheckInError",
    "VisitCannotCompleteError",
    "VisitCannotHoldError",
    "VisitCannotReleaseControlError",
    "VisitCannotResumeError",
    "VisitCannotStartError",
    "VisitCannotTakeControlError",
    "VisitCannotVoidError",
    "VisitCheckedIn",
    "VisitCheckedOut",
    "VisitCompleted",
    "VisitEvent",
    "VisitHeld",
    "VisitLifecycleTimestamps",
    "VisitNotFoundError",
    "VisitParentMismatchedSurfaceError",
    "VisitParentNotFoundError",
    "VisitRegistered",
    "VisitResumed",
    "VisitStarted",
    "VisitStatus",
    "VisitSurfaceControlReleased",
    "VisitSurfaceControlTaken",
    "VisitType",
    "VisitVoided",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_visit",
    "load_visit_timestamps",
    "to_payload",
]
