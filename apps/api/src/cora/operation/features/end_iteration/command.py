"""The `EndProcedureIteration` command -- intent dataclass for this slice.

Single-stream update on a Running Procedure: close the currently-open
convergence-loop iteration. `iteration_index` must match the open
`current_iteration_index` (validated at the decider). `converged`
carries the convergence verdict (True / False / None when no verdict);
`reason` is an optional free-form note bounded at the API boundary.
Slice-dir name drops the aggregate qualifier (`end_iteration`); the
command class carries it (`EndProcedureIteration`). `reason` is
optional; the decider trims and bounds it (1-500 chars) when present.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class EndProcedureIteration:
    """Close the open convergence-loop iteration on a Running Procedure."""

    procedure_id: UUID
    iteration_index: int
    converged: bool | None
    reason: str | None
