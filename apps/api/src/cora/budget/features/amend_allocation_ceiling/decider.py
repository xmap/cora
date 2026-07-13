"""Pure decider for the `AmendAllocationCeiling` command.

PUT semantics: the supplied ceiling IS the post-amend ceiling.
Source set is `{Granted, Active}`. Idempotent: an amendment that
matches the current ceiling returns `[]` (the update_agent_budget
precedent; a retried PUT must not append a second identical fact).

## Validation

  - State must not be None -> `AllocationNotFoundError`
  - Current status must be Granted or Active
    -> `AllocationCannotAmendCeilingError`
  - `ceiling_usd` must be finite and strictly positive
    -> `InvalidAllocationCeilingError`
"""

from datetime import datetime

from cora.budget.aggregates.allocation import (
    Allocation,
    AllocationCannotAmendCeilingError,
    AllocationCeilingAmended,
    AllocationNotFoundError,
    AllocationStatus,
    validate_allocation_ceiling,
)
from cora.budget.features.amend_allocation_ceiling.command import AmendAllocationCeiling

_AMENDABLE_STATUSES: tuple[AllocationStatus, ...] = (
    AllocationStatus.GRANTED,
    AllocationStatus.ACTIVE,
)


def decide(
    state: Allocation | None,
    command: AmendAllocationCeiling,
    *,
    now: datetime,
) -> list[AllocationCeilingAmended]:
    """Decide the events produced by amending an Allocation's ceiling.

    Invariants:
      - State must not be None -> AllocationNotFoundError
      - Current status must be Granted or Active
        -> AllocationCannotAmendCeilingError
      - Ceiling must be finite and strictly positive
        -> InvalidAllocationCeilingError
    """
    if state is None:
        raise AllocationNotFoundError(command.allocation_id)
    if state.status not in _AMENDABLE_STATUSES:
        raise AllocationCannotAmendCeilingError(state.id, state.status)

    # Validate BEFORE the idempotency short-circuit so a bad ceiling
    # fires even when it happens to equal the stored value shape-wise.
    validate_allocation_ceiling(command.ceiling_usd)

    if command.ceiling_usd == state.ceiling_usd:
        return []

    return [
        AllocationCeilingAmended(
            allocation_id=state.id,
            ceiling_usd=command.ceiling_usd,
            occurred_at=now,
        )
    ]
