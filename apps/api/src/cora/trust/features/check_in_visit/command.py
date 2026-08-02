"""The `CheckInVisit` command -- intent dataclass.

Adds an open presence entry for the CALLING principal to a Visit. Requires
`Visit.status in {Arrived, InProgress, OnHold}` -- presence is
orthogonal to lifecycle per V6 (operator must explicitly `record_visit_arrival`
first; check-in does NOT auto-transition Planned -> Arrived).

The command carries no `actor_id`. Presence records who is present, and a
caller-supplied actor let any authorized principal record anyone else as
present, so nothing downstream could treat a presence row as resolved. Checking
a third party in is a different intent with a different accountability story
and belongs to its own command with its own grant, not to a field here.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.trust.aggregates.visit import PresenceMode


@dataclass(frozen=True)
class CheckInVisit:
    """Add an open presence entry for the calling principal in `mode`."""

    visit_id: UUID
    mode: PresenceMode
