"""The `ListProcedureIterations` query -- intent dataclass for this read slice.

Lists the convergence-loop iterations of one Procedure from the
per-iteration projection (`proj_operation_procedure_iterations`),
ordered by iteration_index. Bounded per parent (a procedure has a
handful of iterations at pilot scale), so no cursor pagination -- the
full set returns in one page. If a Procedure ever exceeds the
substream-promotion trigger (>100 iterations), this read moves to the
promoted entries table per [[project_iteration_first_class_research]].
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListProcedureIterations:
    """Read all per-iteration rows for one Procedure, ordered by index."""

    procedure_id: UUID
