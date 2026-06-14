"""The `CompleteProcedure` command -- intent dataclass for this slice.

Single-source happy-path terminal: `Running -> Completed`. Slim
command (id + the conduct-observed actuation kind); no reason field.
Mirrors `CompleteRun`.

`actuation_kind` is the raw `ActuationKind` value (Physical /
Simulated / Hybrid) the Conductor observed during the conduct that is
now completing, or None when nothing instrumented was actuated. It is
server-supplied by the Conductor (not an operator input); the decider
snapshots it onto `ProcedureCompleted` so the Data BC can read it back
to gate Dataset promotion. None for completes issued outside a conduct.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CompleteProcedure:
    """Mark an existing Procedure as completed (happy-path terminal)."""

    procedure_id: UUID
    actuation_kind: str | None = None
