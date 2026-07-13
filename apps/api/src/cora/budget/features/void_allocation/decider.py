"""Pure decider for the `VoidAllocation` command.

Transition: `Granted | Active -> Voided`. Strict-not-idempotent.

## Validation

  - State must not be None -> `AllocationNotFoundError`
  - Current status must be Granted or Active
    -> `AllocationCannotVoidError`
  - `reason` wrapped via `AllocationReason(...)`; REQUIRED, 1-500
    chars after trim -> `InvalidAllocationReasonError`
"""

from datetime import datetime

from cora.budget.aggregates.allocation import (
    Allocation,
    AllocationCannotVoidError,
    AllocationNotFoundError,
    AllocationReason,
    AllocationStatus,
    AllocationVoided,
)
from cora.budget.features.void_allocation.command import VoidAllocation

_VOIDABLE_STATUSES: tuple[AllocationStatus, ...] = (
    AllocationStatus.GRANTED,
    AllocationStatus.ACTIVE,
)


def decide(
    state: Allocation | None,
    command: VoidAllocation,
    *,
    now: datetime,
) -> list[AllocationVoided]:
    """Decide the events produced by voiding an Allocation.

    Invariants:
      - State must not be None -> AllocationNotFoundError
      - Current status must be Granted or Active
        -> AllocationCannotVoidError
      - Reason must be valid -> InvalidAllocationReasonError
        (via AllocationReason VO)
    """
    if state is None:
        raise AllocationNotFoundError(command.allocation_id)
    if state.status not in _VOIDABLE_STATUSES:
        raise AllocationCannotVoidError(state.id, state.status)

    reason = AllocationReason(command.reason)

    return [
        AllocationVoided(
            allocation_id=state.id,
            reason=reason.value,
            occurred_at=now,
        )
    ]
