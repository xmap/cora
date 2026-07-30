"""Pure decider for the `ResumeRun` command.

Resume transition: `Held -> Running`, discharging ONE hold claim, and
only when it is the last one active. The inverse of hold.

## Three outcomes, not one

A Run can be held by several concerns at once, so "release my hold" and
"resume the Run" stopped being the same act. The caller's own claim is
derived from (run_id, cause), and:

  - own claim is the ONLY active claim -> `RunResumed(released_claim_id)`,
    Held → Running. The Run resumes because nothing is holding it.
  - own claim is active, others remain -> `HoldClaimReleased(claim_id)`,
    status unchanged. This concern has stopped holding; the Run stays Held
    on behalf of whoever else is.
  - own claim is NOT active            -> `RunHoldClaimsRemainError`.
    Something else is holding this Run and the caller never placed a hold,
    so resuming would clear a hold it does not own. This is the branch that
    makes the reproduced fault impossible: a settled co-signature cannot
    resume a Run the kill-switch is holding.

Emitting `RunResumed` only in the first case is what makes the transition
to `Running` mean "no concern is holding this Run" rather than "whoever
spoke last is done".

Invariants:
  - State must not be None      -> RunNotFoundError
  - State.status must be Held   -> RunCannotResumeError(current_status=...)
  - `cause` must be in HOLD_CAUSES -> ValueError
  - Caller's claim must be active, else other claims block
                                -> RunHoldClaimsRemainError(blocking_causes=...)

## Legacy holds

A hold placed before holds carried claims has no recorded owner, so no derived
claim id matches it, which would have made every Run held at the moment this
shipped permanently unresumable. Such a hold folds to `LEGACY_CLAIM_ID`, the
operator's resume owns it in addition to its own claim, and clearing it emits a
bare `RunResumed` that clears the hold outright: exactly the one-bit semantics
it was placed under.
"""

from datetime import datetime

from cora.run.aggregates.run import (
    HOLD_CAUSE_OPERATOR,
    HOLD_CAUSES,
    LEGACY_CLAIM_ID,
    HoldClaimReleased,
    Run,
    RunCannotResumeError,
    RunHoldClaimsRemainError,
    RunNotFoundError,
    RunResumed,
    RunStatus,
    derive_claim_id,
)
from cora.run.features.resume_run.command import ResumeRun

_RESUMABLE_STATUSES: tuple[RunStatus, ...] = (RunStatus.HELD,)


def decide(
    state: Run | None,
    command: ResumeRun,
    *,
    now: datetime,
) -> list[RunResumed | HoldClaimReleased]:
    """Decide the events produced by releasing this caller's hold on a Run."""
    if state is None:
        raise RunNotFoundError(command.run_id)
    if state.status not in _RESUMABLE_STATUSES:
        raise RunCannotResumeError(state.id, current_status=state.status)
    if command.cause not in HOLD_CAUSES:
        raise ValueError(
            f"Unknown hold cause {command.cause!r}; expected one of {sorted(HOLD_CAUSES)}"
        )
    claim_id = derive_claim_id(state.id, command.cause)
    active = tuple(active_id for active_id, _ in state.hold_claims)
    if not active:
        # Held with no active claim. Not reachable from a well-formed stream (a
        # `RunHeld` always yields at least the legacy claim), but if it happens
        # the safety property is satisfied (no concern is holding this Run), so
        # resume rather than wedge it.
        return [
            RunResumed(
                run_id=state.id,
                decided_by_decision_id=command.decided_by_decision_id,
                released_claim_id=None,
                occurred_at=now,
            )
        ]
    # A hold placed BEFORE holds were cause-scoped has no recorded owner, so no
    # derived claim id can match it and it would otherwise be unresumable:
    # every Run held at the moment this shipped. The operator is the authority
    # that could always clear such a hold, so the operator's resume owns the
    # legacy claim in addition to its own.
    owned = {claim_id}
    if command.cause == HOLD_CAUSE_OPERATOR:
        owned.add(LEGACY_CLAIM_ID)
    held_by_caller = tuple(cid for cid in active if cid in owned)
    if not held_by_caller:
        # Held, but not by us. Refuse and name who is, so the caller learns
        # which concern to address instead of only that it was refused.
        raise RunHoldClaimsRemainError(
            state.id,
            blocking_causes=tuple(cause for _, cause in state.hold_claims),
        )
    # Legacy one-bit hold: clearing it means clearing the hold outright, which is
    # what a bare `RunResumed` does at the fold.
    if set(active) <= {LEGACY_CLAIM_ID}:
        return [
            RunResumed(
                run_id=state.id,
                decided_by_decision_id=command.decided_by_decision_id,
                released_claim_id=None,
                occurred_at=now,
            )
        ]
    claim_id = held_by_caller[0]
    if len(active) > 1:
        # Others still hold it: discharge our claim without moving status.
        return [
            HoldClaimReleased(
                run_id=state.id,
                claim_id=claim_id,
                cause=command.cause,
                decided_by_decision_id=command.decided_by_decision_id,
                occurred_at=now,
            )
        ]
    return [
        RunResumed(
            run_id=state.id,
            decided_by_decision_id=command.decided_by_decision_id,
            released_claim_id=claim_id,
            occurred_at=now,
        )
    ]
