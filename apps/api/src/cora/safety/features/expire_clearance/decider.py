"""Pure decider for the `ExpireClearance` command.

Single-source transition: `Active -> Expired`. Strict-not-idempotent.
Terminal-good: expired clearances cannot be revived; an amended child
clearance (`amend_clearance`) is the path forward.

## Validation

  - State must not be None -> `ClearanceNotFoundError`
  - Current status must be `Active` -> `ClearanceCannotExpireError`
  - `reason` validated 1-500 chars after trim ->
    `InvalidClearanceExpireReasonError`
"""

from datetime import datetime

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotExpireError,
    ClearanceExpired,
    ClearanceNotFoundError,
    ClearanceStatus,
    InvalidClearanceExpireReasonError,
)
from cora.safety.features.expire_clearance.command import ExpireClearance
from cora.shared.bounded_text import validate_bounded_text
from cora.shared.text_bounds import REASON_MAX_LENGTH

_EXPIRABLE_STATUSES: tuple[ClearanceStatus, ...] = (ClearanceStatus.ACTIVE,)


def decide(
    state: Clearance | None,
    command: ExpireClearance,
    *,
    now: datetime,
) -> list[ClearanceExpired]:
    """Decide the events produced by expiring an Active clearance.

    Invariants:
      - State must not be None -> ClearanceNotFoundError
      - Current status must be Active -> ClearanceCannotExpireError
      - Reason must be valid -> InvalidClearanceExpireReasonError
    """
    if state is None:
        raise ClearanceNotFoundError(command.clearance_id)
    if state.status not in _EXPIRABLE_STATUSES:
        raise ClearanceCannotExpireError(state.id, state.status)

    reason = validate_bounded_text(
        command.reason,
        max_length=REASON_MAX_LENGTH,
        error_class=InvalidClearanceExpireReasonError,
    )

    return [
        ClearanceExpired(
            clearance_id=state.id,
            reason=reason,
            occurred_at=now,
        )
    ]
