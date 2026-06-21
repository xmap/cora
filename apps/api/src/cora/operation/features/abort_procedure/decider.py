"""Pure decider for the `AbortProcedure` command.

Multi-source emergency-exit terminal: `Running | Held -> Aborted`.
`Held` was added when resumable conduct landed
([[project_resumable_conduct_design]] Tier 1); abort widened to accept
it so a paused Procedure stays abortable rather than stranded. Mirrors
Run BC's `abort_run` (`Running | Held` source set).

`reason` validation goes through the `ProcedureAbortReason` VO (which
calls the shared `validate_bounded_text` helper). The on-the-wire
payload in `ProcedureAborted.reason` carries the trimmed string.

Invariants:
  - State must not be None  -> ProcedureNotFoundError
  - command.reason must be 1-500 chars after trimming
    -> InvalidProcedureAbortReasonError
  - State.status must be in {Running, Held}
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

_ABORTABLE_STATUSES: tuple[ProcedureStatus, ...] = (
    ProcedureStatus.RUNNING,
    ProcedureStatus.HELD,
)


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
