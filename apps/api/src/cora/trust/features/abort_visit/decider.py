"""Pure decider for the `AbortVisit` command.

Multi-source transition: `InProgress | OnHold -> Aborted`. Mid-work
abnormal terminator. Strict-not-idempotent.
"""

from datetime import datetime

from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.aggregates.visit import (
    InvalidVisitReasonError,
    Visit,
    VisitAborted,
    VisitCannotAbortError,
    VisitNotFoundError,
    VisitStatus,
)
from cora.trust.features.abort_visit.command import AbortVisit

_PERMITTED: tuple[VisitStatus, ...] = (VisitStatus.IN_PROGRESS, VisitStatus.ON_HOLD)


def decide(
    state: Visit | None,
    command: AbortVisit,
    *,
    now: datetime,
) -> list[VisitAborted]:
    """Decide events for aborting an InProgress or OnHold Visit.

    Invariants:
      - State must not be None -> VisitNotFoundError
      - Status must be InProgress or OnHold -> VisitCannotAbortError
        (pre-work Visits must use cancel_visit; terminals refuse)
      - Reason 1-500 chars after trim -> InvalidVisitReasonError
    """
    if state is None:
        raise VisitNotFoundError(command.visit_id)
    if state.status not in _PERMITTED:
        raise VisitCannotAbortError(
            visit_id=state.id,
            current_status=state.status,
            permitted_sources=_PERMITTED,
        )
    trimmed = command.reason.strip()
    if not trimmed or len(trimmed) > REASON_MAX_LENGTH:
        raise InvalidVisitReasonError(command.reason)
    return [VisitAborted(visit_id=state.id, reason=trimmed, occurred_at=now)]
