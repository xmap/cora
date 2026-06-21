"""Pure decider for the `ResumeProcedure` command.

Single-source resume transition: `Held -> Running`. The inverse of
hold (which requires `Running`). Resuming an already-`Running` Procedure
raises (strict-not-idempotent); resuming a `Defined` or terminal
Procedure raises. Mirrors `resume_run`.

The off-diagonal guard (refuse while the parent Run is `Held`) is NOT
in this pure decider: it needs a cross-aggregate Run read and lands in
the handler in a follow-up slice (it raises the same
`ProcedureCannotResumeError`). See [[project_resumable_conduct_design]].

Invariants:
  - State must not be None  -> ProcedureNotFoundError
  - command.re_establishment_boundary must be >= 0
    -> InvalidProcedureReEstablishmentBoundaryError
  - State.status must be in {Held}
    -> ProcedureCannotResumeError(current_status=...)
"""

from datetime import datetime

from cora.operation.aggregates.procedure import (
    InvalidProcedureReEstablishmentBoundaryError,
    Procedure,
    ProcedureCannotResumeError,
    ProcedureNotFoundError,
    ProcedureResumed,
    ProcedureStatus,
)
from cora.operation.features.resume_procedure.command import ResumeProcedure

_RESUMABLE_STATUSES: tuple[ProcedureStatus, ...] = (ProcedureStatus.HELD,)


def decide(
    state: Procedure | None,
    command: ResumeProcedure,
    *,
    now: datetime,
) -> list[ProcedureResumed]:
    """Decide the events produced by resuming a held Procedure."""
    if state is None:
        raise ProcedureNotFoundError(command.procedure_id)
    if command.re_establishment_boundary < 0:
        raise InvalidProcedureReEstablishmentBoundaryError(command.re_establishment_boundary)
    if state.status not in _RESUMABLE_STATUSES:
        raise ProcedureCannotResumeError(state.id, current_status=state.status)
    return [
        ProcedureResumed(
            procedure_id=state.id,
            re_establishment_boundary=command.re_establishment_boundary,
            decided_by_decision_id=command.decided_by_decision_id,
            occurred_at=now,
        )
    ]
