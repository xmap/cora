"""Pure decider for the `RecordVisitArrival` command.

Single-source transition: `Planned -> Arrived`. Strict-not-idempotent
(re-arriving an already-Arrived visit raises).
"""

from datetime import datetime

from cora.trust.aggregates.visit import (
    Visit,
    VisitArrived,
    VisitCannotArriveError,
    VisitNotFoundError,
    VisitStatus,
)
from cora.trust.features.record_visit_arrival.command import RecordVisitArrival

_PERMITTED: tuple[VisitStatus, ...] = (VisitStatus.PLANNED,)


def decide(
    state: Visit | None,
    command: RecordVisitArrival,
    *,
    now: datetime,
) -> list[VisitArrived]:
    """Decide events for arriving at a Planned Visit.

    Invariants:
      - State must not be None -> VisitNotFoundError
      - Status must be Planned -> VisitCannotArriveError
    """
    if state is None:
        raise VisitNotFoundError(command.visit_id)
    if state.status not in _PERMITTED:
        raise VisitCannotArriveError(
            visit_id=state.id,
            current_status=state.status,
            permitted_sources=_PERMITTED,
        )
    return [VisitArrived(visit_id=state.id, occurred_at=now)]
