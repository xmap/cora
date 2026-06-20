"""The `HoldRun` command — intent dataclass for this slice.

Single-source pause transition: `Running -> Held`. Single-field
command (just run_id); no body at the API layer. Hold ⇄ Resume
is a bidirectional cycle with unlimited repeats — no domain reason
field on Hold (matches PackML / Bluesky precedent that pause is a
routine operation).

Per-event timestamping (`occurred_at`) and the new event id are
injected by the handler from infrastructure ports — same capture-
don't-recompute principle as every other slice.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class HoldRun:
    """Pause an actively-running Run (Running → Held).

    `decided_by_decision_id` (mirrors AbortRun + AdjustRun + StartRun):
    optional Decision BC reference to the record that justified this
    hold. The operator-facing route leaves it None (routine holds need
    no justification); an in-process agent runtime (RunSupervisor) sets
    it to link an autonomous hold to its Decision. NO existence check at
    the decider per the cross-BC eventual-consistency stance.
    """

    run_id: UUID
    decided_by_decision_id: UUID | None = None
