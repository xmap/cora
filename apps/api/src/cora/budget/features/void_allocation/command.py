"""The `VoidAllocation` command -- intent dataclass for this slice.

Withdraws a mistaken grant: `Granted | Active -> Voided`, terminal.
Distinct from the seal: the void records that the award never stood
(no spend snapshot), while the seal closes an open window's books.

`reason` is REQUIRED: withdrawing an award is a governance act the
audit log must always carry context for. The voiding actor's
identity lives on the event envelope (`StoredEvent.principal_id`);
no actor field on the command/event.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class VoidAllocation:
    """Void a Granted or Active Allocation (`-> Voided`, terminal)."""

    allocation_id: UUID
    reason: str
