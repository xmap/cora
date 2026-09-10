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

Invariants:
  - command.cause must be in HOLD_CAUSES -> ValueError
  - The caller must hold an active claim, else other concerns block
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

    claim_id = derive_claim_id(state.id, command.cause)
    active = tuple(active_id for active_id, _ in state.hold_claims)
    if not active:
        # Held with no active claim. Unreachable from a well-formed stream (a
        # ProcedureHeld always yields at least the legacy claim), but if it
        # happens the safety property already holds (no concern is holding
        # this), so resume rather than wedge the conduct shut.
        return _resumed(None)
    # A hold placed BEFORE holds carried claims has no recorded owner, so no
    # derived id matches it and it would otherwise be unresumable: every
    # Procedure held at the moment this shipped. The operator is the authority
    # that could always clear such a hold, so an operator resume owns the
    # legacy claim in addition to its own.
    owned = {claim_id}
    if command.cause == HOLD_CAUSE_OPERATOR:
        owned.add(LEGACY_CLAIM_ID)
    held_by_caller = tuple(cid for cid in active if cid in owned)
    if not held_by_caller:
        # Held, but not by us. Refuse, and name who is holding so the caller
        # learns which concern to address rather than only that it was refused.
        raise ProcedureHoldClaimsRemainError(
            state.id,
            blocking_causes=tuple(cause for _, cause in state.hold_claims),
        )
    if set(active) <= {LEGACY_CLAIM_ID}:
        # A legacy one-bit hold: clearing it means clearing the hold outright,
        # which is exactly what a bare ProcedureResumed does at the fold.
        return _resumed(None)
    if len(active) > 1:
        # Others still hold it: discharge our claim without moving the status.
        return [
            ProcedureHoldClaimReleased(
                procedure_id=state.id,
                claim_id=held_by_caller[0],
                cause=command.cause,
                decided_by_decision_id=command.decided_by_decision_id,
                occurred_at=now,
            )
        ]
    return _resumed(held_by_caller[0])
