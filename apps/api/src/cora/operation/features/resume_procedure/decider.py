"""Pure decider for the `ResumeProcedure` command.

Single-source resume transition: `Held -> Running`. The inverse of
hold (which requires `Running`). Resuming an already-`Running` Procedure
raises (strict-not-idempotent); resuming a `Defined` or terminal
Procedure raises. Mirrors `resume_run`.

Off-diagonal guard: a Held Procedure whose parent Run is itself `Held`
cannot resume to `Running` and walk real setpoints while the Run is
paused. The decider takes a `parent_run_held` fact the handler derives
from a one-directional Operation -> Run read (tach-legal); there is NO
cascade from Run-resume into Procedure-resume (that is a Layer-3 saga,
deferred). `parent_run_held` defaults False, which is correct for a
standalone Procedure (no parent Run). See
[[project_resumable_conduct_design]].

Invariants:
  - State must not be None  -> ProcedureNotFoundError
  - command.re_establishment_boundary must be >= 0
    -> InvalidProcedureReEstablishmentBoundaryError
  - State.status must be in {Held}
    -> ProcedureCannotResumeError(current_status=...)
  - parent_run_held must be False
    -> ProcedureCannotResumeError(parent_run_held=True)
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
    parent_run_held: bool = False,
    now: datetime,
) -> list[ProcedureResumed]:
    """Decide the events produced by resuming a held Procedure.

    `parent_run_held` is the handler-derived fact that this Procedure's
    parent Run is currently `Held`; standalone Procedures (no parent Run)
    pass the default False.
    """
    if state is None:
        raise ProcedureNotFoundError(command.procedure_id)
    if command.re_establishment_boundary < 0:
        raise InvalidProcedureReEstablishmentBoundaryError(command.re_establishment_boundary)
    if state.status not in _RESUMABLE_STATUSES:
        raise ProcedureCannotResumeError(state.id, current_status=state.status)
    if parent_run_held:
        raise ProcedureCannotResumeError(
            state.id, current_status=state.status, parent_run_held=True
        )
    return [
        ProcedureResumed(
            procedure_id=state.id,
            re_establishment_boundary=command.re_establishment_boundary,
            decided_by_decision_id=command.decided_by_decision_id,
            occurred_at=now,
        )
    ]
