"""Pure decider for the `ActivateAllocation` command.

Single-source transition: `Granted -> Active`. Strict-not-idempotent.

`activated_by` is the envelope's acting principal, injected by the
actor-stamping handler so the `(activated_at, activated_by)` fact-act
folds with its attribution half.

## Validation

  - State must not be None -> `AllocationNotFoundError`
  - Current status must be `Granted` -> `AllocationCannotActivateError`
"""

from datetime import datetime

from cora.budget.aggregates.allocation import (
    Allocation,
    AllocationActivated,
    AllocationCannotActivateError,
    AllocationNotFoundError,
    AllocationStatus,
)
from cora.budget.features.activate_allocation.command import ActivateAllocation
from cora.shared.identity import ActorId

_ACTIVATABLE_STATUSES: tuple[AllocationStatus, ...] = (AllocationStatus.GRANTED,)


def decide(
    state: Allocation | None,
    command: ActivateAllocation,
    *,
    now: datetime,
    activated_by: ActorId,
) -> list[AllocationActivated]:
    """Decide the events produced by activating a Granted Allocation.

    Invariants:
      - State must not be None -> AllocationNotFoundError
      - Current status must be Granted -> AllocationCannotActivateError
    """
    if state is None:
        raise AllocationNotFoundError(command.allocation_id)
    if state.status not in _ACTIVATABLE_STATUSES:
        raise AllocationCannotActivateError(state.id, state.status)

    return [
        AllocationActivated(
            allocation_id=state.id,
            activated_by=activated_by,
            occurred_at=now,
        )
    ]
