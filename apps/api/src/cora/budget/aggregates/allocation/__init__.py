"""Allocation aggregate: status FSM, note and reason VOs,
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
    AllocationCeilingUpdated,
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
    ALLOCATION_NOTE_MAX_LENGTH,
    Allocation,
    AllocationAlreadyActiveError,
    AllocationAlreadyExistsError,
    AllocationCannotActivateError,
    AllocationCannotSealError,
    AllocationCannotUpdateCeilingError,
    AllocationCannotVoidError,
    AllocationNote,
    AllocationNotFoundError,
    AllocationReason,
    AllocationStatus,
    InvalidAllocationCeilingError,
    InvalidAllocationNoteError,
    InvalidAllocationReasonError,
    validate_allocation_ceiling,
)

__all__ = [
    "ALLOCATION_NOTE_MAX_LENGTH",
    "Allocation",
    "AllocationActivated",
    "AllocationAlreadyActiveError",
    "AllocationAlreadyExistsError",
    "AllocationCannotActivateError",
    "AllocationCannotSealError",
    "AllocationCannotUpdateCeilingError",
    "AllocationCannotVoidError",
    "AllocationCeilingUpdated",
    "AllocationEvent",
    "AllocationGranted",
    "AllocationNotFoundError",
    "AllocationNote",
    "AllocationReason",
    "AllocationSealed",
    "AllocationStatus",
    "AllocationVoided",
    "InvalidAllocationCeilingError",
    "InvalidAllocationNoteError",
    "InvalidAllocationReasonError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_allocation",
    "to_payload",
    "validate_allocation_ceiling",
]
