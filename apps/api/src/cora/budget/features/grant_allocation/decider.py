"""Pure decider for the `GrantAllocation` command.

Pure function: given the current Allocation state (None for a fresh
stream) and a `GrantAllocation` command, returns the events to append
on the Allocation stream. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports; `granted_by` is the envelope's acting
principal, injected so the genesis fact-act folds with its
attribution half (the non-determinism principle: capture, don't
recompute).

## Validation

  - State must be None (genesis-only) -> `AllocationAlreadyExistsError`
  - `ceiling_usd` must be finite and strictly positive
    -> `InvalidAllocationCeilingError`
  - `note` wrapped via `AllocationNote(...)`; 1-200 chars
    after trim -> `InvalidAllocationNoteError`
  - `campaign_id` is a bare cross-BC reference; NOT resolved here
    (eventual-consistency stance per the Caution / Calibration
    precedent), so no validation beyond the boundary's UUID typing.

Initial status is implicit `Granted` (event type IS the state-change
indicator; the genesis evolver hardcodes the mapping).
"""

from datetime import datetime
from uuid import UUID

from cora.budget.aggregates.allocation import (
    Allocation,
    AllocationAlreadyExistsError,
    AllocationGranted,
    AllocationNote,
    validate_allocation_ceiling,
)
from cora.budget.features.grant_allocation.command import GrantAllocation
from cora.shared.identity import ActorId


def decide(
    state: Allocation | None,
    command: GrantAllocation,
    *,
    now: datetime,
    new_id: UUID,
    granted_by: ActorId,
) -> list[AllocationGranted]:
    """Decide the events produced by granting a new Allocation.

    Invariants:
      - State must be None (genesis-only) -> AllocationAlreadyExistsError
      - Ceiling must be finite and strictly positive
        -> InvalidAllocationCeilingError
      - Note must be valid -> InvalidAllocationNoteError
        (via AllocationNote VO)
    """
    if state is not None:
        raise AllocationAlreadyExistsError(state.id)

    validate_allocation_ceiling(command.ceiling_usd)
    note = AllocationNote(command.note)

    return [
        AllocationGranted(
            allocation_id=new_id,
            ceiling_usd=command.ceiling_usd,
            campaign_id=command.campaign_id,
            note=note.value,
            granted_by=granted_by,
            occurred_at=now,
        )
    ]
