"""Pure decider for the `AbortProcedure` command.

Single-source emergency-exit terminal: `Running -> Aborted`. Source
set is just `Running` today (Held / Resumed deferred to 10c-c per
pilot need; if Held lands, this source set widens to `Running | Held`
to mirror Run BC's `abort_run` precedent).

`reason` validation goes through the `ProcedureAbortReason` VO (which
calls the shared `validate_bounded_text` helper). The on-the-wire
payload in `ProcedureAborted.reason` carries the trimmed string.

Invariants:
  - State must not be None  -> ProcedureNotFoundError
  - command.reason must be 1-500 chars after trimming
    -> InvalidProcedureAbortReasonError
  - State.status must be in {Running}
    -> ProcedureCannotAbortError(current_status=...)
"""

from datetime import datetime

from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureAborted,
    ProcedureAbortReason,
    ProcedureCannotAbortError,
    ProcedureNotFoundError,
    ProcedureStatus,
)
from cora.operation.features.abort_procedure.command import AbortProcedure

_ABORTABLE_STATUSES: tuple[ProcedureStatus, ...] = (ProcedureStatus.RUNNING,)


def decide(
    state: Procedure | None,
    command: AbortProcedure,
    *,
    now: datetime,
) -> list[ProcedureAborted]:
    """Decide the events produced by aborting an existing Procedure."""
    if state is None:
        raise ProcedureNotFoundError(command.procedure_id)
    reason = ProcedureAbortReason(command.reason)
    if state.status not in _ABORTABLE_STATUSES:
        raise ProcedureCannotAbortError(state.id, current_status=state.status)
    return [
        ProcedureAborted(
            procedure_id=state.id,
            reason=reason.value,
            actuation_kind=command.actuation_kind,
            occurred_at=now,
        )
    ]
