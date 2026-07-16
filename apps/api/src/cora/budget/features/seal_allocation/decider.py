"""Pure decider for the `SealAllocation` command.

Single-source transition: `Active -> Sealed`. Strict-not-idempotent.

`spent_usd` is the ledger fold the handler computed over the
envelope's window; `sealed_by` is the envelope's acting principal.
Both are injected (the non-determinism principle: the decider stays
pure, the handler owns the ledger read and the clock).

## Validation

  - State must not be None -> `AllocationNotFoundError`
  - Current status must be `Active` -> `AllocationCannotSealError`
  - `reason` (when set) wrapped via `AllocationReason(...)`; 1-500
    chars after trim -> `InvalidAllocationReasonError`. None is
    allowed (means no closing note).
"""

from datetime import datetime

from cora.budget.aggregates.allocation import (
    Allocation,
    AllocationCannotSealError,
    AllocationNotFoundError,
    AllocationReason,
    AllocationSealed,
    AllocationStatus,
)
from cora.budget.features.seal_allocation.command import SealAllocation
from cora.shared.identity import ActorId

_SEALABLE_STATUSES: tuple[AllocationStatus, ...] = (AllocationStatus.ACTIVE,)


def decide(
    state: Allocation | None,
    command: SealAllocation,
    *,
    now: datetime,
    spent_usd: float,
    sealed_by: ActorId,
) -> list[AllocationSealed]:
    """Decide the events produced by sealing an Active Allocation.

    Invariants:
      - State must not be None -> AllocationNotFoundError
      - Current status must be Active -> AllocationCannotSealError
      - Reason (when set) must be valid -> InvalidAllocationReasonError
        (via AllocationReason VO)
    """
    if state is None:
        raise AllocationNotFoundError(command.allocation_id)
    if state.status not in _SEALABLE_STATUSES:
        raise AllocationCannotSealError(state.id, state.status)

    reason: AllocationReason | None = None
    if command.reason is not None:
        reason = AllocationReason(command.reason)

    return [
        AllocationSealed(
            allocation_id=state.id,
            spent_usd=spent_usd,
            reason=reason.value if reason is not None else None,
            sealed_by=sealed_by,
            occurred_at=now,
        )
    ]
