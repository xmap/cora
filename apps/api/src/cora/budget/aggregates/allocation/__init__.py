"""Allocation aggregate: status FSM, holder-note and reason VOs,
ceiling validation, errors, events, evolver, read repo.

The spending envelope the deployment's beamline receives and spends,
homed in the budget BC. Design lock: [[project_allocation_design]].

Vertical slices that operate on this aggregate live under
`cora.budget.features.<verb>_allocation*/` and import from here for
state and event types.

Public surface: enum + VOs + ceiling validator + errors + events +
evolver + load_allocation.
"""

from cora.budget.aggregates.allocation.events import (
    AllocationActivated,
    AllocationCeilingAmended,
    AllocationEvent,
    AllocationGranted,
    AllocationSealed,
    AllocationVoided,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.budget.aggregates.allocation.evolver import evolve, fold
from cora.budget.aggregates.allocation.read import load_allocation
from cora.budget.aggregates.allocation.state import (
    ALLOCATION_HOLDER_NOTE_MAX_LENGTH,
    Allocation,
    AllocationAlreadyExistsError,
    AllocationCannotActivateError,
    AllocationCannotAmendError,
    AllocationCannotSealError,
    AllocationCannotVoidError,
    AllocationHolderNote,
    AllocationNotFoundError,
    AllocationReason,
    AllocationStatus,
    InvalidAllocationCeilingError,
    InvalidAllocationHolderNoteError,
    InvalidAllocationReasonError,
    validate_allocation_ceiling,
)

__all__ = [
    "ALLOCATION_HOLDER_NOTE_MAX_LENGTH",
    "Allocation",
    "AllocationActivated",
    "AllocationAlreadyExistsError",
    "AllocationCannotActivateError",
    "AllocationCannotAmendError",
    "AllocationCannotSealError",
    "AllocationCannotVoidError",
    "AllocationCeilingAmended",
    "AllocationEvent",
    "AllocationGranted",
    "AllocationHolderNote",
    "AllocationNotFoundError",
    "AllocationReason",
    "AllocationSealed",
    "AllocationStatus",
    "AllocationVoided",
    "InvalidAllocationCeilingError",
    "InvalidAllocationHolderNoteError",
    "InvalidAllocationReasonError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_allocation",
    "to_payload",
    "validate_allocation_ceiling",
]
