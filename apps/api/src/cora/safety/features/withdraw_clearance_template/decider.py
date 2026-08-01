"""Pure decider for the `WithdrawClearanceTemplate` command.

Lifecycle terminal transition: any non-terminal status flows to `Withdrawn`.
Strict-not-idempotent: already-Withdrawn templates raise.

## Validation

  - State must not be None -> `ClearanceTemplateNotFoundError`
  - Current status must be in {Draft, Active, Deprecated}
    -> `ClearanceTemplateCannotWithdrawError`
"""

from datetime import datetime

from cora.safety.aggregates.clearance_template import (
    ClearanceTemplate,
    ClearanceTemplateCannotWithdrawError,
    ClearanceTemplateNotFoundError,
    ClearanceTemplateStatus,
    ClearanceTemplateWithdrawn,
)
from cora.safety.features.withdraw_clearance_template.command import (
    WithdrawClearanceTemplate,
)
from cora.shared.identity import ActorId

_WITHDRAWABLE_STATUSES: tuple[ClearanceTemplateStatus, ...] = (
    ClearanceTemplateStatus.DRAFT,
    ClearanceTemplateStatus.ACTIVE,
    ClearanceTemplateStatus.DEPRECATED,
)


def decide(
    state: ClearanceTemplate | None,
    command: WithdrawClearanceTemplate,
    *,
    now: datetime,
    withdrawn_by: ActorId,
) -> list[ClearanceTemplateWithdrawn]:
    """Decide the events produced by withdrawing a clearance template.

    Invariants:
      - State must not be None -> ClearanceTemplateNotFoundError
      - Current status must be in {Draft, Active, Deprecated}
        -> ClearanceTemplateCannotWithdrawError
    """
    if state is None:
        raise ClearanceTemplateNotFoundError(command.template_id)
    if state.status not in _WITHDRAWABLE_STATUSES:
        raise ClearanceTemplateCannotWithdrawError(state.id, state.status)

    return [
        ClearanceTemplateWithdrawn(
            reason=command.reason,
            template_id=state.id,
            occurred_at=now,
            withdrawn_by=withdrawn_by,
        )
    ]
