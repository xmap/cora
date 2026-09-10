"""Pure decider for the `HoldProcedure` command.

Pause transition: `Running | Held -> Held`, placing ONE hold claim.

`Held` is a legal starting status. It was not, and re-holding raised on
the PackML and Bluesky precedent that hold and resume alternate. That was
right while a hold had one author and became a safety fault once
independent concerns could each park the same conduct: a second concern
arriving at an already-Held Procedure could not record its intent at all,
so the FIRST concern's release restarted the conduct with the second's
cause unenforced.

So the guard moved from "is this Procedure un-held" to "is THIS CONCERN
already holding it". Alternation is still enforced per claim, which is
what the original precedent was protecting. What is newly admitted is two
DIFFERENT concerns holding at once, because that is the situation that
actually arises. Mirrors `hold_run`.

`reason` validation goes through the `ProcedureHoldReason` VO (which
calls the shared `validate_bounded_text` helper). The on-the-wire
payload in `ProcedureHeld.reason` carries the trimmed string.

Invariants:
  - State must not be None  -> ProcedureNotFoundError
  - command.reason must be 1-500 chars after trimming
    -> InvalidProcedureHoldReasonError
  - State.status must be in {Running, Held}
    -> ProcedureCannotHoldError(current_status=...)
  - command.cause must be in HOLD_CAUSES -> ValueError
  - This cause's claim must not already be active
    -> ProcedureCannotHoldError(current_status=...)
"""

from datetime import datetime

from cora.operation.aggregates.procedure import (
    HOLD_CAUSES,
    Procedure,
    ProcedureCannotHoldError,
    ProcedureHeld,
    ProcedureHoldReason,
    ProcedureNotFoundError,
    ProcedureStatus,
    derive_claim_id,
)
from cora.operation.features.hold_procedure.command import HoldProcedure

_HOLDABLE_STATUSES: tuple[ProcedureStatus, ...] = (
    ProcedureStatus.RUNNING,
    ProcedureStatus.HELD,
)


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
    if command.cause not in HOLD_CAUSES:
        raise ValueError(
            f"Unknown hold cause {command.cause!r}; expected one of {sorted(HOLD_CAUSES)}"
        )
    claim_id = derive_claim_id(state.id, command.cause)
    # Per-claim alternation: this concern must discharge before holding again,
    # which is what the original strict-not-idempotent rule was protecting. Two
    # DIFFERENT concerns holding at once is what this decider now admits, and is
    # the whole point of the change.
    if any(active_id == claim_id for active_id, _ in state.hold_claims):
        raise ProcedureCannotHoldError(state.id, current_status=state.status)
    return [
        ProcedureHeld(
            procedure_id=state.id,
            reason=reason.value,
            decided_by_decision_id=command.decided_by_decision_id,
            occurred_at=now,
            actuation_kind=command.actuation_kind,
            claim_id=claim_id,
            cause=command.cause,
        )
    ]
