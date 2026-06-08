"""Pure-decider tests for `retire_caution` slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.caution.aggregates.caution import (
    AssetTarget,
    Caution,
    CautionCannotRetireError,
    CautionCategory,
    CautionNotFoundError,
    CautionRetired,
    CautionRetireReason,
    CautionSeverity,
    CautionStatus,
    CautionText,
    CautionWorkaround,
)
from cora.caution.features import retire_caution
from cora.caution.features.retire_caution import RetireCaution
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_AUTHOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000030001"))
_ASSET_ID = UUID("01900000-0000-7000-8000-000000030002")


def _existing(status: CautionStatus = CautionStatus.ACTIVE) -> Caution:
    return Caution(
        id=uuid4(),
        target=AssetTarget(asset_id=_ASSET_ID),
        category=CautionCategory.WEAR,
        severity=CautionSeverity.CAUTION,
        text=CautionText("some text"),
        workaround=CautionWorkaround("some workaround"),
        authored_by=_AUTHOR_ID,
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_caution_retired_when_active() -> None:
    state = _existing()
    events = retire_caution.decide(
        state=state,
        command=RetireCaution(caution_id=state.id, reason=CautionRetireReason.RESOLVED),
        now=_NOW,
    )
    assert events == [
        CautionRetired(
            caution_id=state.id,
            reason="Resolved",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    "reason",
    [
        CautionRetireReason.RESOLVED,
        CautionRetireReason.NO_LONGER_APPLIES,
        CautionRetireReason.WRONG_TARGET,
    ],
)
def test_decide_carries_each_reason_value(reason: CautionRetireReason) -> None:
    state = _existing()
    events = retire_caution.decide(
        state=state,
        command=RetireCaution(caution_id=state.id, reason=reason),
        now=_NOW,
    )
    assert events[0].reason == reason.value


@pytest.mark.unit
def test_decide_rejects_when_state_none() -> None:
    caution_id = uuid4()
    with pytest.raises(CautionNotFoundError) as exc_info:
        retire_caution.decide(
            state=None,
            command=RetireCaution(caution_id=caution_id, reason=CautionRetireReason.RESOLVED),
            now=_NOW,
        )
    assert exc_info.value.caution_id == caution_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [CautionStatus.SUPERSEDED, CautionStatus.RETIRED],
)
def test_decide_rejects_when_not_active(status: CautionStatus) -> None:
    state = _existing(status=status)
    with pytest.raises(CautionCannotRetireError) as exc_info:
        retire_caution.decide(
            state=state,
            command=RetireCaution(caution_id=state.id, reason=CautionRetireReason.RESOLVED),
            now=_NOW,
        )
    assert exc_info.value.current_status == status
