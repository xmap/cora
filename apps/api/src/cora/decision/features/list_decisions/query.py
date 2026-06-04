"""The `ListDecisions` query: intent dataclass for keyset-paginated
list of decisions from the projection.

Three optional filters: confidence_band (Low / Medium / High /
Certain — denormalized from the stored confidence float at INSERT
time per the ConfidenceBand stance), rule (filter
by categorical rule label from cora.decision.catalog), actor_id
(who decided). Cursor encodes (created_at, decision_id).
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

ConfidenceBandFilter = Literal["Low", "Medium", "High", "Certain"]


@dataclass(frozen=True)
class ListDecisions:
    """Read a keyset-paginated page of decisions from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    confidence_band: ConfidenceBandFilter | None = None
    """Optional confidence-band filter (Low / Medium / High /
    Certain). Decisions with `confidence=None` have no band and are
    NOT returned when this filter is set."""

    rule: str | None = None
    """Optional categorical filter on the decision rule label
    (per cora.decision.catalog). Decisions with `rule=None`
    are NOT returned when this filter is set."""

    actor_id: UUID | None = None
    """Optional `actor_id` filter: returns Decisions made by the
    given Actor. Pass `None` (omit) for "any Actor"."""

    choice: str | None = None
    """Optional categorical filter on the DecisionChoice value
    (RUN_DEBRIEF_CHOICES / CAUTION_PROPOSAL_CHOICES values).
    Filter to one specific outcome (e.g. ``NominalCompletion``).
    Mutually compatible with ``exclude_choices``; both filters can be
    set, although a contradictory combination returns zero rows."""

    exclude_choices: tuple[str, ...] | None = None
    """Optional negative filter on the DecisionChoice value. Pass a
    tuple of choice values to EXCLUDE from results -- the common case
    is dropping the audit-only ``DebriefConflicted`` /
    ``CautionDraftConflicted`` rows emitted by the cross-agent debrief
    lease (per project_run_debriefer_lease_design). Empty tuple is
    treated as "no exclusion"."""
