"""Pure decider for the `HoldRun` command.

Pause transition: `Running | Held -> Held`, placing ONE hold claim.

## Why `Held` is now a legal starting status

It was not. This decider accepted `Running` only, and re-holding an
already-`Held` Run raised (strict-not-idempotent, on the PackML + Bluesky
precedent that hold ⇄ resume alternate). That was right while a hold had
one author and became a safety fault once independent concerns could each
hold the same Run: a second concern arriving at an already-held Run could
not record its intent at all, so the FIRST concern's release resumed the
Run with the second's cause unenforced.

So the guard moved from "is this Run un-held" to "is THIS CONCERN already
holding it". Alternation is still enforced per claim: a concern cannot
hold twice without an intervening release, which is what the original
precedent was protecting. What is newly admitted is two DIFFERENT concerns
holding concurrently, because that is the situation that actually arises.

Invariants:
  - State must not be None         -> RunNotFoundError
  - Status must be in {Running, Held}
                                   -> RunCannotHoldError(current_status=...)
  - `cause` must be in HOLD_CAUSES -> ValueError
  - This cause's claim must not already be active
                                   -> RunCannotHoldError(current_status=...)
"""

from datetime import datetime

from cora.run.aggregates.run import (
    HOLD_CAUSES,
    Run,
    RunCannotHoldError,
    RunHeld,
    RunNotFoundError,
    RunStatus,
    derive_claim_id,
)
from cora.run.features.hold_run.command import HoldRun

_HOLDABLE_STATUSES: tuple[RunStatus, ...] = (RunStatus.RUNNING, RunStatus.HELD)


def decide(
    state: Run | None,
    command: HoldRun,
    *,
    now: datetime,
) -> list[RunHeld]:
    """Decide the events produced by holding an existing Run."""
    if state is None:
        raise RunNotFoundError(command.run_id)
    if state.status not in _HOLDABLE_STATUSES:
        raise RunCannotHoldError(state.id, current_status=state.status)
    if command.cause not in HOLD_CAUSES:
        raise ValueError(
            f"Unknown hold cause {command.cause!r}; expected one of {sorted(HOLD_CAUSES)}"
        )
    claim_id = derive_claim_id(state.id, command.cause)
    # Per-claim alternation: this concern must release before holding again.
    # Two DIFFERENT concerns holding at once is what this decider now admits,
    # and is the whole point of the change.
    if any(active_id == claim_id for active_id, _ in state.hold_claims):
        raise RunCannotHoldError(state.id, current_status=state.status)
    return [
        RunHeld(
            run_id=state.id,
            decided_by_decision_id=command.decided_by_decision_id,
            claim_id=claim_id,
            cause=command.cause,
            occurred_at=now,
        )
    ]
