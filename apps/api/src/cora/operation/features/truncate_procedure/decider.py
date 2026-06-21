"""Pure decider for the `TruncateProcedure` command.

Multi-source partial-data terminal: `Running | Held -> Truncated`.
`Held` was added when resumable conduct landed
([[project_resumable_conduct_design]] Tier 1); truncate widened to
accept it so a paused-then-de-facto-dead Procedure can be closed
retroactively. Mirrors Run BC's `truncate_run` (`Running | Held`).

Truncating any terminal (Completed | Aborted | Truncated) raises;
re-truncating a `Truncated` Procedure raises (strict-not-idempotent).
Truncating a `Defined` Procedure also raises -- a Defined Procedure
hasn't started, so there's no execution to truncate (use a different
workflow: leave it Defined, or extend the FSM with a cancel-defined
slice if pilot operators surface that need).

`reason` validation goes through the `ProcedureTruncateReason` VO
(which calls the shared `validate_bounded_text` helper). The on-the-
wire payload in `ProcedureTruncated.reason` carries the trimmed
string.

`interrupted_at` is operator-supplied and optional. When provided,
must not be in the future relative to `now` (operator should be
marking a past interruption); the decider does NOT enforce a lower
bound. Mirrors `truncate_run`'s `InvalidRunInterruptedAtError`
posture.

Invariants:
  - State must not be None  -> ProcedureNotFoundError
  - command.reason must be 1-500 chars after trimming
    -> InvalidProcedureTruncateReasonError
  - command.interrupted_at, when set, must not be in the future
    -> InvalidProcedureInterruptedAtError
  - State.status must be in {Running, Held}
    -> ProcedureCannotTruncateError(current_status=...)
"""

from datetime import datetime

from cora.operation.aggregates.procedure import (
    InvalidProcedureInterruptedAtError,
    Procedure,
    ProcedureCannotTruncateError,
    ProcedureNotFoundError,
    ProcedureStatus,
    ProcedureTruncated,
    ProcedureTruncateReason,
)
from cora.operation.features.truncate_procedure.command import TruncateProcedure

_TRUNCATABLE_STATUSES: tuple[ProcedureStatus, ...] = (
    ProcedureStatus.RUNNING,
    ProcedureStatus.HELD,
)


def decide(
    state: Procedure | None,
    command: TruncateProcedure,
    *,
    now: datetime,
) -> list[ProcedureTruncated]:
    """Decide the events produced by truncating an existing Procedure."""
    if state is None:
        raise ProcedureNotFoundError(command.procedure_id)
    reason = ProcedureTruncateReason(command.reason)
    if command.interrupted_at is not None and command.interrupted_at > now:
        raise InvalidProcedureInterruptedAtError(command.interrupted_at, now)
    if state.status not in _TRUNCATABLE_STATUSES:
        raise ProcedureCannotTruncateError(state.id, current_status=state.status)
    return [
        ProcedureTruncated(
            procedure_id=state.id,
            reason=reason.value,
            interrupted_at=command.interrupted_at,
            occurred_at=now,
        )
    ]
