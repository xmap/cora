"""The `StartProcedureIteration` command -- intent dataclass for this slice.

Single-stream update on a Running Procedure: begin one convergence-loop
iteration. `iteration_index` is operator-supplied per the
capture-don't-recompute principle (the operator knows the boundary;
the server does not auto-increment); the decider enforces the
strict-successor invariant against the folded `iteration_count`.
Slice-dir name drops the aggregate qualifier (`start_iteration`);
the command class carries it (`StartProcedureIteration`), mirroring
`append_activities` / `AppendProcedureActivities`.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class StartProcedureIteration:
    """Begin one convergence-loop iteration on a Running Procedure."""

    procedure_id: UUID
    iteration_index: int
