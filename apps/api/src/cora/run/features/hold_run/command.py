"""The `HoldRun` command — intent dataclass for this slice.

Pause transition: `Running | Held -> Held`, placing ONE hold claim.
No free-text reason at the API layer (PackML / Bluesky precedent that
pause is routine), but the command does carry `cause`: which concern is
holding. That is not a reason field — it is the claim's identity, and it
is what lets a second concern hold a Run without erasing the first.

Per-event timestamping (`occurred_at`) and the new event id are
injected by the handler from infrastructure ports — same capture-
don't-recompute principle as every other slice.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.run.aggregates.run import HOLD_CAUSE_OPERATOR


@dataclass(frozen=True)
class HoldRun:
    """Pause an actively-running Run (Running → Held).

    `decided_by_decision_id` (mirrors AbortRun + AdjustRun + StartRun):
    optional Decision BC reference to the record that justified this
    hold. The operator-facing route leaves it None (routine holds need
    no justification); an in-process agent runtime (RunSupervisor) sets
    it to link an autonomous hold to its Decision. NO existence check at
    the decider per the cross-BC eventual-consistency stance.

    `cause` names the concern placing the hold and must be in
    `HOLD_CAUSES`. Defaults to `operator`, which is what the
    operator-facing route and tool mean and is why neither had to change.
    The RunSupervisor passes `supervisor-envelope`. The claim id itself is
    not a command field: it is derived from (run_id, cause), so a holder
    and a releaser agree on it without either storing it.
    """

    run_id: UUID
    decided_by_decision_id: UUID | None = None
    cause: str = HOLD_CAUSE_OPERATOR
