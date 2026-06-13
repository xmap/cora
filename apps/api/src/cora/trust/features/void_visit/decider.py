"""Pure decider for the `VoidVisit` command.

Multi-source transition: any non-terminal status -> Voided. FHIR R5
entered-in-error analog. Reachable from {Planned, Arrived, InProgress,
OnHold} -- everything except already-terminal statuses (Completed,
Cancelled, Aborted, Voided itself).
"""

from datetime import datetime

from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.aggregates.visit import (
    InvalidVisitReasonError,
    Visit,
    VisitCannotVoidError,
    VisitNotFoundError,
    VisitStatus,
    VisitVoided,
)
from cora.trust.features.void_visit.command import VoidVisit

_PERMITTED: tuple[VisitStatus, ...] = (
    VisitStatus.PLANNED,
    VisitStatus.ARRIVED,
    VisitStatus.IN_PROGRESS,
    VisitStatus.ON_HOLD,
)


def decide(
    state: Visit | None,
    command: VoidVisit,
    *,
    now: datetime,
) -> list[VisitVoided]:
    """Decide events for voiding a non-terminal Visit.

    Invariants:
      - State must not be None -> VisitNotFoundError
      - Status must be non-terminal (Planned/Arrived/InProgress/OnHold)
        -> VisitCannotVoidError (terminals refuse re-voiding)
      - Reason 1-500 chars after trim -> InvalidVisitReasonError
    """
    if state is None:
        raise VisitNotFoundError(command.visit_id)
    if state.status not in _PERMITTED:
        raise VisitCannotVoidError(
            visit_id=state.id,
            current_status=state.status,
            permitted_sources=_PERMITTED,
        )
    trimmed = command.reason.strip()
    if not trimmed or len(trimmed) > REASON_MAX_LENGTH:
        raise InvalidVisitReasonError(command.reason)
    return [VisitVoided(visit_id=state.id, reason=trimmed, occurred_at=now)]
