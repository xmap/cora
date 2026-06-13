"""Pure-decider tests for `reject_clearance` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotRejectError,
    ClearanceNotFoundError,
    ClearanceRejected,
    ClearanceStatus,
    ClearanceTitle,
    InvalidClearanceRejectReasonError,
    RunBinding,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.features import reject_clearance
from cora.safety.features.reject_clearance import RejectClearance
from cora.shared.facility_code import FacilityCode
from cora.shared.text_bounds import REASON_MAX_LENGTH

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _clearance(status: ClearanceStatus = ClearanceStatus.UNDER_REVIEW) -> Clearance:
    return Clearance(
        id=uuid4(),
        template_id=ClearanceTemplateId(clearance_template_stream_id("aps", "ESAF")),
        facility_code=FacilityCode("aps"),
        title=ClearanceTitle("Pilot"),
        bindings=frozenset({RunBinding(run_id=uuid4())}),
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_rejected_from_under_review() -> None:
    state = _clearance(ClearanceStatus.UNDER_REVIEW)
    events = reject_clearance.decide(
        state=state,
        command=RejectClearance(
            clearance_id=state.id,
            reason="ESRB found insufficient PPE specification",
        ),
        now=_NOW,
    )
    assert events == [
        ClearanceRejected(
            clearance_id=state.id,
            reason="ESRB found insufficient PPE specification",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_trims_reason() -> None:
    state = _clearance()
    events = reject_clearance.decide(
        state=state,
        command=RejectClearance(
            clearance_id=state.id,
            reason="  bad  ",
        ),
        now=_NOW,
    )
    assert events[0].reason == "bad"


@pytest.mark.unit
def test_decide_rejects_empty_reason() -> None:
    state = _clearance()
    with pytest.raises(InvalidClearanceRejectReasonError):
        reject_clearance.decide(
            state=state,
            command=RejectClearance(clearance_id=state.id, reason="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_too_long_reason() -> None:
    state = _clearance()
    with pytest.raises(InvalidClearanceRejectReasonError):
        reject_clearance.decide(
            state=state,
            command=RejectClearance(
                clearance_id=state.id,
                reason="x" * (REASON_MAX_LENGTH + 1),
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_when_state_none() -> None:
    cid = uuid4()
    with pytest.raises(ClearanceNotFoundError):
        reject_clearance.decide(
            state=None,
            command=RejectClearance(clearance_id=cid, reason="x"),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_when_status_not_under_review() -> None:
    state = _clearance(ClearanceStatus.DEFINED)
    with pytest.raises(ClearanceCannotRejectError):
        reject_clearance.decide(
            state=state,
            command=RejectClearance(clearance_id=state.id, reason="x"),
            now=_NOW,
        )
