"""The `AbortProcedure` command -- intent dataclass for this slice.

Single-source emergency-exit terminal: `Running -> Aborted`. Carries
operator-supplied free-form `reason` string (1-500 chars after trim;
validated at the API boundary AND defensively at the decider via
`ProcedureAbortReason` VO). Mirrors `AbortRun` exactly.

Why free-form vs. structured taxonomy: same posture as Run BC's
abort-reason. Future-additive when documented re-evaluation triggers
fire (vocabulary convergence, Decision BC adoption, regulated-pilot
audit demand).

`actuation_kind` is the raw `ActuationKind` value (Physical /
Simulated / Hybrid) the Conductor observed before the abort, or None
(no instrumented actuation observed, or the abort was issued outside a
conduct, for example a cancel mid-execute where no result was
returned). Server-supplied by the Conductor; the decider snapshots it
onto `ProcedureAborted` so a Dataset produced by an aborted conduct
still carries honest provenance. Conservative: routes attempted before
the failing step still taint the kind.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AbortProcedure:
    """Mark an existing Procedure as aborted (emergency-exit terminal)."""

    procedure_id: UUID
    reason: str
    actuation_kind: str | None = None
