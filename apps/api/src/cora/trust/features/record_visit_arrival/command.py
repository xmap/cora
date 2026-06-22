"""The `RecordVisitArrival` command -- intent dataclass.

Explicit operator gesture: team is on-site (or remote-checked-in
in spirit). NO presence collection mutation; that's check_in_visit's
job. Per V6 explicit-gesture-only lock, arrival is a distinct gesture
from presence tracking.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RecordVisitArrival:
    """Transition Planned -> Arrived."""

    visit_id: UUID
