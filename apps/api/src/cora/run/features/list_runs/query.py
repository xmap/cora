"""The `ListRuns` query: intent dataclass for keyset-paginated
list of runs from the projection.

Optional filters: status (Running / Held / Completed / Aborted /
Stopped / Truncated), plan_id (which Plan was bound), campaign_id
(Campaign membership), and conduct_mode (Conducted / Witnessed). Cursor
encodes (created_at, run_id).
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

RunStatusFilter = Literal[
    "Running",
    "Held",
    "Completed",
    "Aborted",
    "Stopped",
    "Truncated",
]


@dataclass(frozen=True)
class ListRuns:
    """Read a keyset-paginated page of runs from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    status: RunStatusFilter | None = None
    """Optional status filter (one of the RunStatus values)."""

    plan_id: UUID | None = None
    """Optional `plan_id` filter: returns Runs bound to the given
    Plan. Pass `None` (omit) for "any Plan"."""

    campaign_id: UUID | None = None
    """Optional `campaign_id` filter (Campaign Watch #10):
    returns Runs that are members of the given Campaign. Pass `None`
    (omit) for "any Campaign or none"."""

    conduct_mode: str | None = None
    """Optional `ConductMode` value filter ("Conducted" or "Witnessed").
    Pass `None` (omit) for "any conduct mode". Lets a caller restrict to
    Witnessed Runs, e.g. the RunWitness restart-rebuild query."""
