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
hardware fault). The system itself does not detect de-facto-dead
Runs (separate liveness concern); truncate is operator-driven.
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
