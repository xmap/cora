"""Procedure hold-claim folding: the set of concerns currently holding a conduct.

`status` alone is one bit, so a second holder arriving at an already-Held
Procedure could not record its intent and the first holder's resume restarted
the conduct with the second's cause unenforced. These tests pin the fold that
replaces the bit, and the legacy replay that keeps historical streams meaning
exactly what they meant before claims existed.
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
    ProcedureAborted,
    ProcedureCompleted,
    ProcedureEvent,
    ProcedureHeld,
    ProcedureHoldClaimReleased,
    ProcedureRegistered,
    ProcedureResumed,
    ProcedureStarted,
    ProcedureStatus,
    ProcedureTruncated,
    fold,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
_PID = UUID("01900000-0000-7000-8000-0000000c1a10")
_OPERATOR_CLAIM = UUID("01900000-0000-7000-8000-00000000aa01")
_FAULT_CLAIM = UUID("01900000-0000-7000-8000-00000000bb02")


def _fold(events: list[ProcedureEvent]) -> Procedure:
    """`fold` is Optional; every test here folds a genesis-first stream."""
    state = fold(events)
    assert state is not None
    return state


def _running() -> list[ProcedureEvent]:
    events: list[ProcedureEvent] = [
        ProcedureRegistered(
            procedure_id=_PID,
            name="alignment",
            kind="alignment",
            target_asset_ids=(),
            parent_run_id=None,
            occurred_at=_NOW,
        ),
        ProcedureStarted(procedure_id=_PID, occurred_at=_NOW),
    ]
    return events


def _held(claim_id: UUID | None, cause: str | None) -> ProcedureHeld:
    return ProcedureHeld(
        procedure_id=_PID,
        reason="parked",
        occurred_at=_NOW,
        claim_id=claim_id,
        cause=cause,
    )


def test_two_concerns_hold_the_same_procedure_and_both_are_recorded() -> None:
    state = _fold(
        [
            *_running(),
            _held(_FAULT_CLAIM, HOLD_CAUSE_STEP_FAULT),
            _held(_OPERATOR_CLAIM, HOLD_CAUSE_OPERATOR),
        ]
    )
    assert state.status is ProcedureStatus.HELD
    assert state.hold_claims == (
        (_FAULT_CLAIM, HOLD_CAUSE_STEP_FAULT),
        (_OPERATOR_CLAIM, HOLD_CAUSE_OPERATOR),
    )


def test_releasing_one_of_two_claims_leaves_the_procedure_held() -> None:
    """The fault this whole slice exists to fix: the first holder discharging
    must NOT restart a conduct the second holder still wants parked."""
    state = _fold(
        [
            *_running(),
            _held(_FAULT_CLAIM, HOLD_CAUSE_STEP_FAULT),
            _held(_OPERATOR_CLAIM, HOLD_CAUSE_OPERATOR),
            ProcedureHoldClaimReleased(
                procedure_id=_PID,
                claim_id=_FAULT_CLAIM,
                cause=HOLD_CAUSE_STEP_FAULT,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state.status is ProcedureStatus.HELD
    assert state.hold_claims == ((_OPERATOR_CLAIM, HOLD_CAUSE_OPERATOR),)


def test_resuming_the_last_claim_clears_it_and_runs() -> None:
    state = _fold(
        [
            *_running(),
            _held(_OPERATOR_CLAIM, HOLD_CAUSE_OPERATOR),
            ProcedureResumed(
                procedure_id=_PID,
                re_establishment_boundary=0,
                occurred_at=_NOW,
                released_claim_id=_OPERATOR_CLAIM,
            ),
        ]
    )
    assert state.status is ProcedureStatus.RUNNING
    assert state.hold_claims == ()


def test_re_holding_under_a_live_claim_id_is_idempotent() -> None:
    """A re-delivered hold from the same concern re-derives the same claim id,
    so it must fold to one claim rather than stacking a second."""
    state = _fold(
        [
            *_running(),
            _held(_FAULT_CLAIM, HOLD_CAUSE_STEP_FAULT),
            _held(_FAULT_CLAIM, HOLD_CAUSE_STEP_FAULT),
        ]
    )
    assert state.hold_claims == ((_FAULT_CLAIM, HOLD_CAUSE_STEP_FAULT),)


def test_a_distinct_conductor_concern_holds_alongside_a_step_fault() -> None:
    """A stood-down steering driver is discharged by the driver being
    reinstated, not by the equipment recovering, so the two coexist."""
    driver_claim = uuid4()
    state = _fold(
        [
            *_running(),
            _held(_FAULT_CLAIM, HOLD_CAUSE_STEP_FAULT),
            _held(driver_claim, HOLD_CAUSE_DRIVER_STAND_DOWN),
        ]
    )
    assert dict(state.hold_claims) == {
        _FAULT_CLAIM: HOLD_CAUSE_STEP_FAULT,
        driver_claim: HOLD_CAUSE_DRIVER_STAND_DOWN,
    }


def test_legacy_claimless_hold_folds_to_the_single_legacy_claim() -> None:
    state = _fold([*_running(), _held(None, None)])
    assert state.hold_claims == ((LEGACY_CLAIM_ID, LEGACY_CAUSE),)


def test_repeated_legacy_holds_collapse_to_one_claim() -> None:
    """Pre-claim streams replay to their original one-bit meaning, so repeated
    claimless holds must not accumulate."""
    state = _fold([*_running(), _held(None, None), _held(None, None)])
    assert state.hold_claims == ((LEGACY_CLAIM_ID, LEGACY_CAUSE),)


def test_legacy_bare_resume_clears_every_claim() -> None:
    """A resume with no released_claim_id is the old one-bit semantics, which
    cleared the hold outright."""
    state = _fold(
        [
            *_running(),
            _held(_FAULT_CLAIM, HOLD_CAUSE_STEP_FAULT),
            _held(_OPERATOR_CLAIM, HOLD_CAUSE_OPERATOR),
            ProcedureResumed(procedure_id=_PID, re_establishment_boundary=0, occurred_at=_NOW),
        ]
    )
    assert state.status is ProcedureStatus.RUNNING
    assert state.hold_claims == ()


def test_releasing_an_inactive_claim_is_a_fold_level_no_op() -> None:
    """The evolver folds whatever the stream says and leaves rejection to the
    deciders, which is what keeps replay total over any historical stream."""
    state = _fold(
        [
            *_running(),
            _held(_OPERATOR_CLAIM, HOLD_CAUSE_OPERATOR),
            ProcedureHoldClaimReleased(
                procedure_id=_PID,
                claim_id=uuid4(),
                cause=HOLD_CAUSE_STEP_FAULT,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state.hold_claims == ((_OPERATOR_CLAIM, HOLD_CAUSE_OPERATOR),)


@pytest.mark.parametrize(
    "terminal",
    [
        ProcedureCompleted(procedure_id=_PID, occurred_at=_NOW),
        ProcedureAborted(procedure_id=_PID, reason="gave up", occurred_at=_NOW),
        ProcedureTruncated(
            procedure_id=_PID,
            reason="cut short",
            interrupted_at=_NOW,
            occurred_at=_NOW,
        ),
    ],
    ids=["completed", "aborted", "truncated"],
)
def test_a_terminal_clears_every_claim(terminal: ProcedureEvent) -> None:
    """A finished Procedure holds nothing, however many concerns were holding."""
    state = _fold(
        [
            *_running(),
            _held(_FAULT_CLAIM, HOLD_CAUSE_STEP_FAULT),
            _held(_OPERATOR_CLAIM, HOLD_CAUSE_OPERATOR),
            terminal,
        ]
    )
    assert state.hold_claims == ()


def test_a_release_preserves_every_other_field() -> None:
    """The audit-only arm changes one field. Pinned because the evolver's other
    arms hand-list every field, which is how one gets silently dropped."""
    before = _fold([*_running(), _held(_OPERATOR_CLAIM, HOLD_CAUSE_OPERATOR)])
    after = _fold(
        [
            *_running(),
            _held(_OPERATOR_CLAIM, HOLD_CAUSE_OPERATOR),
            _held(_FAULT_CLAIM, HOLD_CAUSE_STEP_FAULT),
            ProcedureHoldClaimReleased(
                procedure_id=_PID,
                claim_id=_FAULT_CLAIM,
                cause=HOLD_CAUSE_STEP_FAULT,
                occurred_at=_NOW,
            ),
        ]
    )
    assert after == before
