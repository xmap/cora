"""Hold and resume deciders enforcing cause-scoped claims.

The fold in `test_procedure_hold_claims` proves a Procedure can REPRESENT two
concerns holding it. These prove the deciders act on that: a second concern can
record its hold, and a resume that would restart work another concern still
wants parked is refused rather than silently granted.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.operation.aggregates.procedure import (
    HOLD_CAUSE_DRIVER_STAND_DOWN,
    HOLD_CAUSE_OPERATOR,
    HOLD_CAUSE_STEP_FAULT,
    LEGACY_CAUSE,
    LEGACY_CLAIM_ID,
    Procedure,
    ProcedureCannotHoldError,
    ProcedureHeld,
    ProcedureHoldClaimReleased,
    ProcedureHoldClaimsRemainError,
    ProcedureName,
    ProcedureResumed,
    ProcedureStatus,
    derive_claim_id,
)
from cora.operation.features import hold_procedure, resume_procedure
from cora.operation.features.hold_procedure import HoldProcedure
from cora.operation.features.resume_procedure import ResumeProcedure

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
_PID = UUID("01900000-0000-7000-8000-0000000c1a20")


def _procedure(
    *,
    status: ProcedureStatus = ProcedureStatus.RUNNING,
    hold_claims: tuple[tuple[UUID, str], ...] = (),
) -> Procedure:
    return Procedure(
        id=_PID,
        name=ProcedureName("alignment"),
        kind="alignment",
        target_asset_ids=frozenset(),
        status=status,
        parent_run_id=None,
        hold_claims=hold_claims,
    )


def _claim(cause: str) -> UUID:
    return derive_claim_id(_PID, cause)


def _held_by(*causes: str) -> Procedure:
    return _procedure(
        status=ProcedureStatus.HELD,
        hold_claims=tuple((_claim(cause), cause) for cause in causes),
    )


def _resume(cause: str) -> ResumeProcedure:
    return ResumeProcedure(procedure_id=_PID, re_establishment_boundary=0, cause=cause)


def test_a_second_concern_can_hold_an_already_held_procedure() -> None:
    """The fault this slice fixes: previously this was refused outright and the
    second concern's intent went unrecorded."""
    events = hold_procedure.decide(
        state=_held_by(HOLD_CAUSE_STEP_FAULT),
        command=HoldProcedure(
            procedure_id=_PID, reason="swapping the sample", cause=HOLD_CAUSE_OPERATOR
        ),
        now=_NOW,
    )
    assert [type(e) for e in events] == [ProcedureHeld]
    assert isinstance(events[0], ProcedureHeld)
    assert events[0].cause == HOLD_CAUSE_OPERATOR
    assert events[0].claim_id == _claim(HOLD_CAUSE_OPERATOR)


def test_the_same_concern_cannot_hold_twice_without_discharging() -> None:
    """Per-claim alternation survives: what the old status guard protected is
    still protected, just scoped to the concern instead of the Procedure."""
    with pytest.raises(ProcedureCannotHoldError):
        hold_procedure.decide(
            state=_held_by(HOLD_CAUSE_STEP_FAULT),
            command=HoldProcedure(procedure_id=_PID, reason="again", cause=HOLD_CAUSE_STEP_FAULT),
            now=_NOW,
        )


def test_an_unknown_cause_is_refused() -> None:
    with pytest.raises(ValueError, match="Unknown hold cause"):
        hold_procedure.decide(
            state=_procedure(),
            command=HoldProcedure(procedure_id=_PID, reason="x", cause="whatever"),
            now=_NOW,
        )


def test_resuming_while_another_concern_holds_discharges_without_restarting() -> None:
    """The safety property. The step fault clearing must NOT restart a conduct
    the operator is still holding."""
    events = resume_procedure.decide(
        state=_held_by(HOLD_CAUSE_STEP_FAULT, HOLD_CAUSE_OPERATOR),
        command=_resume(HOLD_CAUSE_STEP_FAULT),
        now=_NOW,
    )
    assert [type(e) for e in events] == [ProcedureHoldClaimReleased]
    assert isinstance(events[0], ProcedureHoldClaimReleased)
    assert events[0].claim_id == _claim(HOLD_CAUSE_STEP_FAULT)


def test_resuming_the_last_claim_restarts_the_conduct() -> None:
    events = resume_procedure.decide(
        state=_held_by(HOLD_CAUSE_OPERATOR),
        command=_resume(HOLD_CAUSE_OPERATOR),
        now=_NOW,
    )
    assert [type(e) for e in events] == [ProcedureResumed]
    assert isinstance(events[0], ProcedureResumed)
    assert events[0].released_claim_id == _claim(HOLD_CAUSE_OPERATOR)


def test_resuming_without_a_claim_is_refused_and_names_the_holders() -> None:
    """Refusing is half the job: the caller must learn WHICH concern to address
    rather than only that it was refused."""
    with pytest.raises(ProcedureHoldClaimsRemainError) as exc:
        resume_procedure.decide(
            state=_held_by(HOLD_CAUSE_STEP_FAULT, HOLD_CAUSE_DRIVER_STAND_DOWN),
            command=_resume(HOLD_CAUSE_OPERATOR),
            now=_NOW,
        )
    assert exc.value.blocking_causes == (
        HOLD_CAUSE_STEP_FAULT,
        HOLD_CAUSE_DRIVER_STAND_DOWN,
    )
    assert HOLD_CAUSE_STEP_FAULT in str(exc.value)


def test_an_operator_resume_owns_a_legacy_claim() -> None:
    """A hold placed before claims existed has no owner, so no derived id
    matches it and it would be unresumable forever. The operator is the
    authority that could always clear such a hold."""
    events = resume_procedure.decide(
        state=_procedure(
            status=ProcedureStatus.HELD,
            hold_claims=((LEGACY_CLAIM_ID, LEGACY_CAUSE),),
        ),
        command=_resume(HOLD_CAUSE_OPERATOR),
        now=_NOW,
    )
    assert [type(e) for e in events] == [ProcedureResumed]
    assert isinstance(events[0], ProcedureResumed)
    # Bare resume: at the fold that clears every claim, which is exactly the
    # one-bit behaviour a pre-claim stream had.
    assert events[0].released_claim_id is None


def test_a_machine_concern_does_not_own_a_legacy_claim() -> None:
    """Only the operator inherits an unowned hold. A step fault clearing must
    not silently adopt and discharge a hold nobody can attribute."""
    with pytest.raises(ProcedureHoldClaimsRemainError):
        resume_procedure.decide(
            state=_procedure(
                status=ProcedureStatus.HELD,
                hold_claims=((LEGACY_CLAIM_ID, LEGACY_CAUSE),),
            ),
            command=_resume(HOLD_CAUSE_STEP_FAULT),
            now=_NOW,
        )


def test_a_held_procedure_with_no_claims_resumes_rather_than_wedging() -> None:
    """Unreachable from a well-formed stream, but if it happens the safety
    property already holds, so do not lock the conduct shut."""
    events = resume_procedure.decide(
        state=_procedure(status=ProcedureStatus.HELD),
        command=_resume(HOLD_CAUSE_OPERATOR),
        now=_NOW,
    )
    assert [type(e) for e in events] == [ProcedureResumed]


def test_the_wire_surfaces_cannot_choose_a_cause() -> None:
    """A caller able to pick its own cause could label a machine-parked conduct
    an operator pause. The command defaults instead, and the route and tool do
    not expose the field."""
    assert HoldProcedure(procedure_id=uuid4(), reason="x").cause == HOLD_CAUSE_OPERATOR
    assert (
        ResumeProcedure(procedure_id=uuid4(), re_establishment_boundary=0).cause
        == HOLD_CAUSE_OPERATOR
    )
