"""The `CheckInVisit` command -- intent dataclass.

Adds an open presence entry for `actor_id` to a Visit. Requires
`Visit.status in {Arrived, InProgress, OnHold}` -- presence is
orthogonal to lifecycle per V6 (operator must explicitly `record_visit_arrival`
first; check-in does NOT auto-transition Planned -> Arrived).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.trust.aggregates.visit import PresenceMode


@dataclass(frozen=True)
class CheckInVisit:
    """Add an open presence entry for `actor_id` in `mode` to the Visit."""

    visit_id: UUID
    actor_id: UUID
    mode: PresenceMode
