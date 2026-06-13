"""Pure decider for the `StartProcedureIteration` command.

Begins one convergence-loop iteration on a Running Procedure. Iteration
is orthogonal to the lifecycle FSM (the Procedure stays Running), so
this is not a status transition; it folds onto the iteration denorm.

Invariants:
  - state is None -> ProcedureNotFoundError
  - status is not Running (iterations only exist within an active
    execution; same lifecycle gate as append_activities), OR an
    iteration is already open (current_iteration_index is not None;
    iterations do not nest), OR iteration_index is not the strict
    successor of iteration_count (operator-supplied index; monotonic,
    no gaps or duplicates) -> ProcedureCannotStartIterationError
  - the consecutive-unconverged "patience" streak has reached the
    declared cap (max_consecutive_unconverged_iterations)
    -> ProcedureIterationLimitReachedError (the loop gives up). Checked
    AFTER the sequencing guards so a malformed request still gets the
    sequencing error; a well-formed next-iteration request that exhausts
    the budget gets the limit error. No auto-abort (mirrors Agent.budget).
"""

from datetime import datetime

from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureCannotStartIterationError,
    ProcedureIterationLimitReachedError,
    ProcedureIterationStarted,
    ProcedureNotFoundError,
    ProcedureStatus,
)
from cora.operation.features.start_iteration.command import StartProcedureIteration


def decide(
    state: Procedure | None,
    command: StartProcedureIteration,
    *,
    now: datetime,
) -> list[ProcedureIterationStarted]:
    """Decide the events produced by starting a new Procedure iteration."""
    if state is None:
        raise ProcedureNotFoundError(command.procedure_id)
    expected = state.iteration_count + 1
    if (
        state.status is not ProcedureStatus.RUNNING
        or state.current_iteration_index is not None
        or command.iteration_index != expected
    ):
        raise ProcedureCannotStartIterationError(
            state.id,
            current_status=state.status,
            current_iteration_index=state.current_iteration_index,
            expected_iteration_index=expected,
            iteration_index=command.iteration_index,
        )
    cap = state.max_consecutive_unconverged_iterations
    if cap is not None and state.consecutive_unconverged_iterations >= cap:
        raise ProcedureIterationLimitReachedError(
            state.id,
            consecutive_unconverged_iterations=state.consecutive_unconverged_iterations,
            max_consecutive_unconverged_iterations=cap,
        )
    return [
        ProcedureIterationStarted(
            procedure_id=state.id,
            iteration_index=command.iteration_index,
            occurred_at=now,
        )
    ]
