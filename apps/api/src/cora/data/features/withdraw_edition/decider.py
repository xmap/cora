"""Pure decider for the `WithdrawEdition` command.

## Firing order (per design memo L17)

  1. UnauthorizedError (handler pre-decider)
  2. EditionNotFoundError (handler load + fold)
  3. InvalidEditionWithdrawalReasonError (WithdrawalReason VO)
  4. EditionCannotWithdrawError (status != Published)
  5. Handler PersistentIdentifierMinter.tombstone -> PersistentIdentifierMinterTombstoneError 502
  6. Decider emits EditionWithdrawn

The PersistentIdentifierMinter.tombstone side effect runs at the handler BEFORE the
decider emits, so a tombstone wire failure aborts the command without
appending an EditionWithdrawn event (the DOI stays Findable; operator
escalates). The decider re-validates the VO + status guards defensively
even though the handler checked status cheaply first.
"""

from datetime import datetime

from cora.data.aggregates.edition import (
    Edition,
    EditionCannotWithdrawError,
    EditionStatus,
    EditionWithdrawn,
)
from cora.data.aggregates.edition.state import WithdrawalReason
from cora.data.features.withdraw_edition.command import WithdrawEdition
from cora.data.features.withdraw_edition.context import WithdrawEditionContext
from cora.shared.identity import ActorId


def decide(
    state: Edition,
    command: WithdrawEdition,
    *,
    context: WithdrawEditionContext,
    now: datetime,
    withdrawn_by: ActorId,
) -> list[EditionWithdrawn]:
    """Decide the events produced by withdrawing a Published Edition.

    `state` is non-None (handler raised EditionNotFoundError if it
    were). Firing order per the module docstring header.

    Invariants:
      - withdrawal_reason validates via WithdrawalReason VO
        -> InvalidEditionWithdrawalReasonError
      - state.status must be PUBLISHED -> EditionCannotWithdrawError
    """
    _ = context

    reason = WithdrawalReason(command.withdrawal_reason)

    if state.status is not EditionStatus.PUBLISHED:
        raise EditionCannotWithdrawError(edition_id=state.id, current_status=state.status)

    return [
        EditionWithdrawn(
            edition_id=state.id,
            withdrawal_reason=reason.value,
            occurred_at=now,
            withdrawn_by=withdrawn_by,
        )
    ]
