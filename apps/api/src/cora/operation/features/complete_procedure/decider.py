"""Pure decider for the `CompleteProcedure` command.

Single-source happy-path terminal: `Running -> Completed`. Mirrors
`complete_run`. Re-completing an already-`Completed` Procedure raises
(strict-not-idempotent); completing any other state raises.

Source-state guard uses tuple-membership for forward-compat with a
future Held source if pilot operator feedback surfaces a need
(today: just Running).

Invariants:
  - State must not be None  -> ProcedureNotFoundError
  - State.status must be in {Running} -> ProcedureCannotCompleteError
"""

from datetime import datetime

from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureCannotCompleteError,
    ProcedureCompleted,
    ProcedureNotFoundError,
    ProcedureStatus,
)
from cora.operation.features.complete_procedure.command import CompleteProcedure

_COMPLETABLE_STATUSES: tuple[ProcedureStatus, ...] = (ProcedureStatus.RUNNING,)


def decide(
    state: Procedure | None,
    command: CompleteProcedure,
    *,
    now: datetime,
) -> list[ProcedureCompleted]:
    """Decide the events produced by completing an existing Procedure."""
    if state is None:
        raise ProcedureNotFoundError(command.procedure_id)
    if state.status not in _COMPLETABLE_STATUSES:
        raise ProcedureCannotCompleteError(state.id, current_status=state.status)
    return [
        ProcedureCompleted(
            procedure_id=state.id,
            actuation_kind=command.actuation_kind,
            occurred_at=now,
        )
    ]
