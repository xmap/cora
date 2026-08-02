"""The `CheckOutVisit` command -- intent dataclass.

Closes the CALLING principal's open presence entry. Multi-shift is
supported: the same actor may check in / out repeatedly within a single
Visit -- each cycle produces a separate `PresenceEntry`.

The command carries no `actor_id`, for the same reason `CheckInVisit` does
not. A caller-supplied actor let any authorized principal close anyone
else's presence entry, which left "is X present now" a caller-influenced
answer even once check-in was fixed. Closing a third party's presence is a
separate intent with its own grant.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CheckOutVisit:
    """Close the calling principal's currently-open presence entry."""

    visit_id: UUID
