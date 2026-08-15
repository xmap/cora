"""The `TruncateRun` command, intent dataclass for this slice.

Multi-source partial-data terminal: `Running | Held -> Truncated`.
Carries operator-supplied free-form `reason` string (1-500 chars
after trim; validated at the API boundary AND defensively at the
decider via `RunTruncateReason` VO) plus an optional
`interrupted_at` (operator's best guess at when the actual
interruption occurred; None when unknown).

Distinct from stop: stop = controlled exit while the system is
responsive; truncate = retroactive cleanup for a Run that became
de-facto dead through interruption (power loss, process crash,
hardware fault). Two callers today: an operator (REST / MCP), and
the RunSupervisor's run-liveness act rung, both threading
`decided_by_decision_id` when autonomous. The RunWitness runtime
(`cora.api._run_witness`) is a third, in-process-only caller: it
truncates a witnessed Run whose terminal observation was missed,
recovering the dedup state so a fresh capture on the same code can
promote. None of the three detect de-facto-dead Runs on their own
initiative from nothing; each has its own trigger (an operator's
judgment, a liveness ceiling, a new Begun for an already-open code).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class TruncateRun:
    """Cleanup terminal of an interrupted Run (Running | Held → Truncated)."""

    run_id: UUID
    reason: str
    interrupted_at: datetime | None
    # Optional Decision-causation link (mirrors HoldRun / AbortRun /
    # AdjustRun / StartRun). Lets an autonomous truncate (the RunSupervisor
    # run-liveness act rung) point back to the Decision that justified it; an
    # operator-driven truncate leaves it None. No cross-BC existence check at
    # the decider, per the eventual-consistency stance. Additive default so
    # existing callers (REST / MCP, which do not expose it) are unaffected.
    decided_by_decision_id: UUID | None = None
