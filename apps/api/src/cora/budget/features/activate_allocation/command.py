"""The `ActivateAllocation` command -- intent dataclass for this slice.

Opens a Granted envelope's spend window: `Granted -> Active`. From
this moment the envelope check arms and the event's `occurred_at`
becomes the `activated_at` window start every total-spend fold uses.
Source set is `{Granted}` only; re-activating any other status raises
`AllocationCannotActivateError` (silently resetting the window would
corrupt the seal's spend snapshot).

Activation stays an operator ceremony at v1 (the bootstrap-then-
promote shape); auto-activate on CampaignStarted is deferred until
the manual step demonstrably chafes. The activating actor's identity
is injected by the handler from the envelope's `principal_id` (the
decider's `activated_by` kwarg); no actor field on the command.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ActivateAllocation:
    """Activate a Granted Allocation (`Granted -> Active`)."""

    allocation_id: UUID
