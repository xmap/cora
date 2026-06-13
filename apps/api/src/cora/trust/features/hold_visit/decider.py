"""Pure decider for the `HoldVisit` command.

Single-source transition: `InProgress -> OnHold`. Strict-not-idempotent.
Reason is mandatory and validated 1-500 chars after trim.
"""

from datetime import datetime

from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.aggregates.visit import (
    InvalidVisitReasonError,
    Visit,
    VisitCannotHoldError,
    VisitHeld,
    VisitNotFoundError,
    VisitStatus,
)
from cora.trust.features.hold_visit.command import HoldVisit

_PERMITTED: tuple[VisitStatus, ...] = (VisitStatus.IN_PROGRESS,)


def decide(
    state: Visit | None,
    command: HoldVisit,
    *,
    now: datetime,
) -> list[VisitHeld]:
    """Decide events for holding an InProgress Visit.

    Invariants:
      - State must not be None -> VisitNotFoundError
      - Status must be InProgress -> VisitCannotHoldError
      - Reason 1-500 chars after trim -> InvalidVisitReasonError
    """
    if state is None:
        raise VisitNotFoundError(command.visit_id)
    if state.status not in _PERMITTED:
        raise VisitCannotHoldError(
            visit_id=state.id,
            current_status=state.status,
            permitted_sources=_PERMITTED,
        )
    trimmed = command.reason.strip()
    if not trimmed or len(trimmed) > REASON_MAX_LENGTH:
        raise InvalidVisitReasonError(command.reason)
    return [VisitHeld(visit_id=state.id, reason=trimmed, occurred_at=now)]
