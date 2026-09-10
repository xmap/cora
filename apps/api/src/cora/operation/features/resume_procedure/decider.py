"""Pure decider for the `ResumeProcedure` command.

Single-source resume transition: `Held -> Running`. The inverse of
hold (which requires `Running`). Resuming an already-`Running` Procedure
raises (strict-not-idempotent); resuming a `Defined` or terminal
Procedure raises. Mirrors `resume_run`.

Off-diagonal guard: a Held Procedure whose parent Run is itself `Held`
cannot resume to `Running` and walk real setpoints while the Run is
paused. The decider takes a `parent_run_held` fact the handler derives
from a one-directional Operation -> Run read (tach-legal); there is NO
cascade from Run-resume into Procedure-resume (that is a Layer-3 saga,
deferred). `parent_run_held` defaults False, which is correct for a
standalone Procedure (no parent Run). See
[[project_resumable_conduct_design]].

## Who may clear which claim

A resume discharges claims, and only then, if none remain, moves the status.
A machine concern discharges only the claim it placed. An operator discharges
its own, any legacy claim, and every ATTENTION claim, because an attention
claim is the Conductor reporting a conduct it cannot un-stick and no runtime
will ever come back to clear it. Without that widening, wiring the Conductor's
causes would leave every fault-parked conduct permanently unresumable. See
`ATTENTION_HOLD_CAUSES` for why the same widening would be a bypass on a Run.

Today every resume in the system is an operator resume: `cause` defaults to
`operator` and no wire surface exposes it. So the refusal below does not fire
in production yet; it is the guard that keeps a future machine resumer from
clearing a hold it never placed, and the behaviour that changes NOW is that a
machine hold is recorded at all.

Invariants:
  - command.cause must be in HOLD_CAUSES -> ValueError
  - The caller must be entitled to clear at least one active claim
    -> ProcedureHoldClaimsRemainError(blocking_causes=...)
  - State must not be None  -> ProcedureNotFoundError
  - command.re_establishment_boundary must be >= 0
    -> InvalidProcedureReEstablishmentBoundaryError
  - State.status must be in {Held}
    -> ProcedureCannotResumeError(current_status=...)
  - parent_run_held must be False
    -> ProcedureCannotResumeError(parent_run_held=True)
"""

from datetime import datetime
from uuid import UUID

from cora.operation.aggregates.procedure import (
    ATTENTION_HOLD_CAUSES,
    HOLD_CAUSE_OPERATOR,
    HOLD_CAUSES,
    LEGACY_CLAIM_ID,
    InvalidProcedureReEstablishmentBoundaryError,
    Procedure,
    ProcedureCannotResumeError,
    ProcedureHoldClaimReleased,
    ProcedureHoldClaimsRemainError,
    ProcedureNotFoundError,
    ProcedureResumed,
    ProcedureStatus,
    derive_claim_id,
)
from cora.operation.features.resume_procedure.command import ResumeProcedure

_RESUMABLE_STATUSES: tuple[ProcedureStatus, ...] = (ProcedureStatus.HELD,)


def _clearable_by(procedure_id: UUID, cause: str, own_claim_id: UUID) -> set[UUID]:
    """The claims a resumer with this cause is entitled to discharge.

    A machine concern clears only its own. An operator clears its own, plus
    every attention claim, plus a legacy claim, because those are precisely the
    claims nothing else in CORA will ever clear:

      - attention claims (`ATTENTION_HOLD_CAUSES`) are the Conductor saying it
        parked a conduct it cannot un-stick. No runtime discharges them, so
        without this an operator resume would raise
        `ProcedureHoldClaimsRemainError` on every fault-parked conduct and the
        hold would be permanent.
      - a hold placed BEFORE holds carried claims has no recorded owner, so no
        derived id matches it: every Procedure held at the moment claims
        shipped. Clearing one was always the operator's to do.

    `operator` is a CONCERN, not an identity: it is the default cause, so it
    means "the caller named no other concern", and nothing here checks what
    kind of thing the caller is. Every unmarked resume traces to a person
    today only because no agent is granted `ResumeProcedure`, which is what
    `test_no_agent_is_granted_resume_procedure` keeps true.

    Widening this for the operator is safe in a way it would NOT be on a Run,
    where the machine causes are authority claims a co-signature or a
    kill-switch holds deliberately against an operator, and where the wire
    deliberately DOES expose `cause` so a person can name the claim they are
    clearing. See `ATTENTION_HOLD_CAUSES` for the distinction.
    """
    if cause != HOLD_CAUSE_OPERATOR:
        return {own_claim_id}
    return {
        own_claim_id,
        LEGACY_CLAIM_ID,
        *(derive_claim_id(procedure_id, attention) for attention in ATTENTION_HOLD_CAUSES),
    }


def decide(
    state: Procedure | None,
    command: ResumeProcedure,
    *,
    parent_run_held: bool = False,
    now: datetime,
) -> list[ProcedureResumed | ProcedureHoldClaimReleased]:
    """Decide the events produced by resuming a held Procedure.

    `parent_run_held` is the handler-derived fact that this Procedure's
    parent Run is currently `Held`; standalone Procedures (no parent Run)
    pass the default False.
    """
    if state is None:
        raise ProcedureNotFoundError(command.procedure_id)
    if command.re_establishment_boundary < 0:
        raise InvalidProcedureReEstablishmentBoundaryError(command.re_establishment_boundary)
    if state.status not in _RESUMABLE_STATUSES:
        raise ProcedureCannotResumeError(state.id, current_status=state.status)
    if parent_run_held:
        raise ProcedureCannotResumeError(
            state.id, current_status=state.status, parent_run_held=True
        )
    if command.cause not in HOLD_CAUSES:
        raise ValueError(
            f"Unknown hold cause {command.cause!r}; expected one of {sorted(HOLD_CAUSES)}"
        )

    def _resumed(
        released_claim_id: UUID | None,
    ) -> list[ProcedureResumed | ProcedureHoldClaimReleased]:
        return [
            ProcedureResumed(
                procedure_id=state.id,
                re_establishment_boundary=command.re_establishment_boundary,
                decided_by_decision_id=command.decided_by_decision_id,
                occurred_at=now,
                released_claim_id=released_claim_id,
            )
        ]

    def _released(claim_id: UUID, cause: str) -> ProcedureHoldClaimReleased:
        return ProcedureHoldClaimReleased(
            procedure_id=state.id,
            claim_id=claim_id,
            cause=cause,
            decided_by_decision_id=command.decided_by_decision_id,
            occurred_at=now,
        )

    own_claim_id = derive_claim_id(state.id, command.cause)
    active = tuple(active_id for active_id, _ in state.hold_claims)
    if not active:
        # Held with no active claim. Unreachable from a well-formed stream (a
        # ProcedureHeld always yields at least the legacy claim), but if it
        # happens the safety property already holds (no concern is holding
        # this), so resume rather than wedge the conduct shut.
        return _resumed(None)
    owned = _clearable_by(state.id, command.cause, own_claim_id)
    discharged = tuple((cid, cause) for cid, cause in state.hold_claims if cid in owned)
    if not discharged:
        # Held, and by nothing this caller may clear. Refuse, and name who is
        # holding so the caller learns which concern to address rather than
        # only that it was refused.
        raise ProcedureHoldClaimsRemainError(
            state.id,
            blocking_causes=tuple(cause for _, cause in state.hold_claims),
        )
    if any(cid not in owned for cid in active):
        # Something this caller may not clear still holds it: discharge what we
        # can and leave the status where it is.
        return [_released(cid, cause) for cid, cause in discharged]
    if set(active) <= {LEGACY_CLAIM_ID}:
        # A legacy one-bit hold: clearing it means clearing the hold outright,
        # which is exactly what a bare ProcedureResumed does at the fold.
        return _resumed(None)
    # Nothing will remain, so the conduct runs again. The caller's own claim
    # rides the resume; every claim it clears on another concern's behalf gets
    # its own event, so a resume that answers three concerns records three
    # discharges instead of one status change that silently absorbed them.
    extras = [_released(cid, cause) for cid, cause in discharged if cid != own_claim_id]
    own = own_claim_id if any(cid == own_claim_id for cid, _ in discharged) else None
    return [*extras, *_resumed(own)]
