"""Pure decider for the `HoldProcedure` command.

Single-source pause transition: `Running -> Held`. Re-holding an
already-`Held` Procedure raises (strict-not-idempotent); holding a
`Defined` or terminal Procedure raises. Mirrors `hold_run`.

Hold <-> Resume is bidirectional and unlimited-cycle: an operator can
hold -> resume -> hold repeatedly within one conduct, each hold
requiring an intervening resume.

`reason` validation goes through the `ProcedureHoldReason` VO (which
calls the shared `validate_bounded_text` helper). The on-the-wire
payload in `ProcedureHeld.reason` carries the trimmed string.

Invariants:
  - State must not be None  -> ProcedureNotFoundError
  - command.reason must be 1-500 chars after trimming
    -> InvalidProcedureHoldReasonError
  - State.status must be in {Running}
    -> ProcedureCannotHoldError(current_status=...)
"""

from datetime import datetime

from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureCannotHoldError,
    ProcedureHeld,
    ProcedureHoldReason,
    ProcedureNotFoundError,
    ProcedureStatus,
)
from cora.operation.features.hold_procedure.command import HoldProcedure

_HOLDABLE_STATUSES: tuple[ProcedureStatus, ...] = (ProcedureStatus.RUNNING,)


def decide(
    state: Procedure | None,
    command: HoldProcedure,
    *,
    now: datetime,
) -> list[ProcedureHeld]:
    """Decide the events produced by holding an existing Procedure."""
    if state is None:
        raise ProcedureNotFoundError(command.procedure_id)
    reason = ProcedureHoldReason(command.reason)
    if state.status not in _HOLDABLE_STATUSES:
        raise ProcedureCannotHoldError(state.id, current_status=state.status)
    return [
        ProcedureHeld(
            procedure_id=state.id,
            reason=reason.value,
            decided_by_decision_id=command.decided_by_decision_id,
            occurred_at=now,
            actuation_kind=command.actuation_kind,
        )
    ]
