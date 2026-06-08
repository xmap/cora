"""Pure decider for the `RejectClearance` command.

Single-source transition: `UnderReview -> Rejected`. Strict-not-
idempotent. Terminal-bad: rejected clearances cannot be revived; a
new Clearance must be registered if the operator wants to retry.

The rejecting actor's identity lives on the event envelope
(`StoredEvent.principal_id`), not on the command/event payload, per
cross-BC `RunAborted` / `ProcedureAborted` precedent. The projection
reads the envelope at apply time.

## Validation

  - State must not be None -> `ClearanceNotFoundError`
  - Current status must be `UnderReview` -> `ClearanceCannotRejectError`
  - `reason` validated 1-500 chars after trim ->
    `InvalidClearanceRejectReasonError`
"""

from datetime import datetime

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotRejectError,
    ClearanceNotFoundError,
    ClearanceRejected,
    ClearanceStatus,
    InvalidClearanceRejectReasonError,
)
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_REJECT_REASON_MAX_LENGTH,
)
from cora.safety.features.reject_clearance.command import RejectClearance
from cora.shared.bounded_text import validate_bounded_text

_REJECTABLE_STATUSES: tuple[ClearanceStatus, ...] = (ClearanceStatus.UNDER_REVIEW,)


def decide(
    state: Clearance | None,
    command: RejectClearance,
    *,
    now: datetime,
) -> list[ClearanceRejected]:
    """Decide the events produced by rejecting an UnderReview clearance.

    Invariants:
      - State must not be None -> ClearanceNotFoundError
      - Current status must be UnderReview
        -> ClearanceCannotRejectError
      - Reason must be valid -> InvalidClearanceRejectReasonError
    """
    if state is None:
        raise ClearanceNotFoundError(command.clearance_id)
    if state.status not in _REJECTABLE_STATUSES:
        raise ClearanceCannotRejectError(state.id, state.status)

    reason = validate_bounded_text(
        command.reason,
        max_length=CLEARANCE_REJECT_REASON_MAX_LENGTH,
        error_class=InvalidClearanceRejectReasonError,
    )

    return [
        ClearanceRejected(
            clearance_id=state.id,
            reason=reason,
            occurred_at=now,
        )
    ]
