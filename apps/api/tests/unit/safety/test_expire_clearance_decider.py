"""Pure-decider tests for `expire_clearance` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotExpireError,
    ClearanceExpired,
    ClearanceNotFoundError,
    ClearanceStatus,
    ClearanceTitle,
    InvalidClearanceExpireReasonError,
    RunBinding,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.features import expire_clearance
from cora.safety.features.expire_clearance import ExpireClearance
from cora.shared.facility_code import FacilityCode
from cora.shared.text_bounds import REASON_MAX_LENGTH

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _clearance(status: ClearanceStatus = ClearanceStatus.ACTIVE) -> Clearance:
    return Clearance(
        id=uuid4(),
        template_id=ClearanceTemplateId(clearance_template_stream_id("aps", "ESAF")),
        facility_code=FacilityCode("aps"),
        title=ClearanceTitle("Pilot"),
        bindings=frozenset({RunBinding(run_id=uuid4())}),
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_expired_from_active() -> None:
    state = _clearance(ClearanceStatus.ACTIVE)
    events = expire_clearance.decide(
        state=state,
        command=ExpireClearance(
            clearance_id=state.id,
            reason="validity window elapsed",
        ),
        now=_NOW,
    )
    assert events == [
        ClearanceExpired(
            clearance_id=state.id,
            reason="validity window elapsed",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_trims_reason() -> None:
    state = _clearance()
    events = expire_clearance.decide(
        state=state,
        command=ExpireClearance(clearance_id=state.id, reason="  expired  "),
        now=_NOW,
    )
    assert events[0].reason == "expired"


@pytest.mark.unit
def test_decide_rejects_empty_reason() -> None:
    state = _clearance()
    with pytest.raises(InvalidClearanceExpireReasonError):
        expire_clearance.decide(
            state=state,
            command=ExpireClearance(clearance_id=state.id, reason="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_too_long_reason() -> None:
    state = _clearance()
    with pytest.raises(InvalidClearanceExpireReasonError):
        expire_clearance.decide(
            state=state,
            command=ExpireClearance(
                clearance_id=state.id,
                reason="x" * (REASON_MAX_LENGTH + 1),
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_when_state_none() -> None:
    cid = uuid4()
    with pytest.raises(ClearanceNotFoundError):
        expire_clearance.decide(
            state=None,
            command=ExpireClearance(clearance_id=cid, reason="x"),
            now=_NOW,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [
        ClearanceStatus.DEFINED,
        ClearanceStatus.SUBMITTED,
        ClearanceStatus.UNDER_REVIEW,
        ClearanceStatus.APPROVED,
        ClearanceStatus.EXPIRED,
        ClearanceStatus.REJECTED,
        ClearanceStatus.SUPERSEDED,
    ],
)
def test_decide_rejects_when_status_not_active(status: ClearanceStatus) -> None:
    state = _clearance(status)
    with pytest.raises(ClearanceCannotExpireError):
        expire_clearance.decide(
            state=state,
            command=ExpireClearance(clearance_id=state.id, reason="x"),
            now=_NOW,
        )
