"""Pure decider for the `UpdateAllocationCeiling` command.

PUT semantics: the supplied ceiling IS the post-update ceiling.
Source set is `{Granted, Active}`. Idempotent: an update that
matches the current ceiling returns `[]` (the update_agent_budget
precedent; a retried PUT must not append a second identical fact).

## Validation

  - State must not be None -> `AllocationNotFoundError`
  - Current status must be Granted or Active
    -> `AllocationCannotUpdateCeilingError`
  - `ceiling_usd` must be finite and strictly positive
    -> `InvalidAllocationCeilingError`
"""

from datetime import datetime

from cora.budget.aggregates.allocation import (
    Allocation,
    AllocationCannotUpdateCeilingError,
    AllocationCeilingUpdated,
    AllocationNotFoundError,
    AllocationStatus,
    validate_allocation_ceiling,
)
from cora.budget.features.update_allocation_ceiling.command import UpdateAllocationCeiling

_UPDATABLE_STATUSES: tuple[AllocationStatus, ...] = (
    AllocationStatus.GRANTED,
    AllocationStatus.ACTIVE,
)


def decide(
    state: Allocation | None,
    command: UpdateAllocationCeiling,
    *,
    now: datetime,
) -> list[AllocationCeilingUpdated]:
    """Decide the events produced by updating an Allocation's ceiling.

    Invariants:
      - State must not be None -> AllocationNotFoundError
      - Current status must be Granted or Active
        -> AllocationCannotUpdateCeilingError
      - Ceiling must be finite and strictly positive
        -> InvalidAllocationCeilingError
    """
    if state is None:
        raise AllocationNotFoundError(command.allocation_id)
    if state.status not in _UPDATABLE_STATUSES:
        raise AllocationCannotUpdateCeilingError(state.id, state.status)

    # Validate BEFORE the idempotency short-circuit so a bad ceiling
    # fires even when it happens to equal the stored value shape-wise.
    validate_allocation_ceiling(command.ceiling_usd)

    if command.ceiling_usd == state.ceiling_usd:
        return []

    return [
        AllocationCeilingUpdated(
            allocation_id=state.id,
            ceiling_usd=command.ceiling_usd,
            occurred_at=now,
        )
    ]
