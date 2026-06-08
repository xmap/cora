"""Pure decider for the `StartClearanceReview` command.

Single-source transition: `Submitted -> UnderReview`. Strict-not-
idempotent.

## Validation

  - State must not be None -> `ClearanceNotFoundError`
  - Current status must be `Submitted` -> `ClearanceCannotStartReviewError`
  - `first_reviewer_role` validated 1-50 chars after trim ->
    `InvalidClearanceReviewerRoleError` (free-form facility vocabulary;
    role-taxonomy closed-StrEnum promotion deferred per design memo
    watch item)
"""

from datetime import datetime

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotStartReviewError,
    ClearanceNotFoundError,
    ClearanceReviewStarted,
    ClearanceStatus,
    InvalidClearanceReviewerRoleError,
)
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
)
from cora.safety.features.start_clearance_review.command import StartClearanceReview
from cora.shared.bounded_text import validate_bounded_text

_REVIEW_STARTABLE_STATUSES: tuple[ClearanceStatus, ...] = (ClearanceStatus.SUBMITTED,)


def decide(
    state: Clearance | None,
    command: StartClearanceReview,
    *,
    now: datetime,
) -> list[ClearanceReviewStarted]:
    """Decide the events produced by starting review on a Submitted clearance.

    Invariants:
      - State must not be None -> ClearanceNotFoundError
      - Current status must be Submitted
        -> ClearanceCannotStartReviewError
      - first_reviewer_role must be valid
        -> InvalidClearanceReviewerRoleError
    """
    if state is None:
        raise ClearanceNotFoundError(command.clearance_id)
    if state.status not in _REVIEW_STARTABLE_STATUSES:
        raise ClearanceCannotStartReviewError(state.id, state.status)

    role = validate_bounded_text(
        command.first_reviewer_role,
        max_length=CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
        error_class=InvalidClearanceReviewerRoleError,
    )

    return [
        ClearanceReviewStarted(
            clearance_id=state.id,
            first_reviewer_role=role,
            occurred_at=now,
        )
    ]
