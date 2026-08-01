"""The `UpdateAllocationCeiling` command -- intent dataclass for this slice.

Carries the FULL desired post-update ceiling (PUT semantics, not a
delta): the updated ceiling IS the supplied number. The cost-overrun
tighten lever must land at an exact figure the operator chose, and a
delta would compound across retries.

Allowed from `{Granted, Active}`; a terminal envelope's books are
closed and updating them would rewrite audit history.

The updating actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class UpdateAllocationCeiling:
    """Update an Allocation's USD ceiling (PUT semantics)."""

    allocation_id: UUID
    ceiling_usd: float
