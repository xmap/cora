"""Pure decider for the `EndProcedureIteration` command.

Closes the currently-open convergence-loop iteration on a Running or
Held Procedure. Iteration is orthogonal to the lifecycle FSM; this
folds onto the iteration denorm by clearing the open-index marker.

`Held` is accepted (alongside `Running`) so an iteration left open when
an operator paused the conduct can still be closed while paused
([[project_resumable_conduct_design]] Tier 1). `start_iteration` is NOT
widened: a new iteration cannot be opened while paused (resume first).

`reason` is optional; when present it is trimmed and bounded 1-500
chars via the shared `validate_bounded_text` helper (matching the
abort / truncate reason posture), so a whitespace-only reason is
rejected and the persisted `ProcedureIterationEnded.reason` carries the
trimmed string. None passes through unvalidated.

Invariants:
  - state is None -> ProcedureNotFoundError
  - command.reason, when present, must be 1-500 chars after trimming
    -> InvalidProcedureIterationEndReasonError
  - status is not in {Running, Held}, OR no iteration is open
    (current_iteration_index is None), OR iteration_index does not equal
    the open current_iteration_index -> ProcedureCannotEndIterationError
"""

from datetime import datetime

from cora.operation.aggregates.procedure import (
    InvalidProcedureIterationEndReasonError,
    Procedure,
    ProcedureCannotEndIterationError,
    ProcedureIterationEnded,
    ProcedureNotFoundError,
    ProcedureStatus,
)
from cora.operation.features.end_iteration.command import EndProcedureIteration
from cora.shared.bounded_text import validate_bounded_text
from cora.shared.text_bounds import REASON_MAX_LENGTH

_ITERATION_ENDABLE_STATUSES: tuple[ProcedureStatus, ...] = (
    ProcedureStatus.RUNNING,
    ProcedureStatus.HELD,
)


def decide(
    state: Procedure | None,
    command: EndProcedureIteration,
    *,
    now: datetime,
) -> list[ProcedureIterationEnded]:
    """Decide the events produced by ending the open Procedure iteration."""
    if state is None:
        raise ProcedureNotFoundError(command.procedure_id)
    reason = (
        validate_bounded_text(
            command.reason,
            max_length=REASON_MAX_LENGTH,
            error_class=InvalidProcedureIterationEndReasonError,
        )
        if command.reason is not None
        else None
    )
    if (
        state.status not in _ITERATION_ENDABLE_STATUSES
        or state.current_iteration_index is None
        or command.iteration_index != state.current_iteration_index
    ):
        raise ProcedureCannotEndIterationError(
            state.id,
            current_status=state.status,
            current_iteration_index=state.current_iteration_index,
            iteration_index=command.iteration_index,
        )
    return [
        ProcedureIterationEnded(
            procedure_id=state.id,
            iteration_index=command.iteration_index,
            converged=command.converged,
            reason=reason,
            occurred_at=now,
        )
    ]
