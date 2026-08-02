"""Pure decider for the `CheckInVisit` command.

Two-part guard:
  - `Visit.status in {Arrived, InProgress, OnHold}` (presence is
    orthogonal to lifecycle; pre-arrival check-in is rejected per V6
    explicit-gesture lock)
  - No open presence entry already exists for the calling principal
    (composite uniqueness on `(actor_id, check_out_at IS NULL)`)

The actor is `checked_in_by`, handler-injected from the request envelope's
`principal_id`, following the `authored_by` precedent in
`caution.features.register_caution.decider`. It is deliberately not a command
field: a caller-supplied actor let any authorized principal record anyone else
as present, and a presence row is only worth reading if it names who was
actually there.
"""

from datetime import datetime

from cora.shared.identity import ActorId
from cora.trust.aggregates.visit import (
    Visit,
    VisitAlreadyCheckedInError,
    VisitCannotCheckInError,
    VisitCheckedIn,
    VisitNotFoundError,
    VisitStatus,
)
from cora.trust.features.check_in_visit.command import CheckInVisit

_PERMITTED: tuple[VisitStatus, ...] = (
    VisitStatus.ARRIVED,
    VisitStatus.IN_PROGRESS,
    VisitStatus.ON_HOLD,
)


def decide(
    state: Visit | None,
    command: CheckInVisit,
    *,
    now: datetime,
    checked_in_by: ActorId,
) -> list[VisitCheckedIn]:
    """Decide events for checking the calling principal in to a Visit.

    Invariants:
      - State must not be None -> VisitNotFoundError
      - Status must be Arrived / InProgress / OnHold
        -> VisitCannotCheckInError
        (operator must record_visit_arrival first; presence does not auto-arrive)
      - No open presence entry for the caller -> VisitAlreadyCheckedInError
    """
    if state is None:
        raise VisitNotFoundError(command.visit_id)
    if state.status not in _PERMITTED:
        raise VisitCannotCheckInError(
            visit_id=state.id,
            current_status=state.status,
            permitted_sources=_PERMITTED,
        )
    open_entry_exists = any(
        e.actor_id == checked_in_by and e.check_out_at is None for e in state.presence_entries
    )
    if open_entry_exists:
        raise VisitAlreadyCheckedInError(visit_id=state.id, actor_id=checked_in_by)
    return [
        VisitCheckedIn(
            visit_id=state.id,
            actor_id=checked_in_by,
            mode=command.mode.value,
            occurred_at=now,
        )
    ]
