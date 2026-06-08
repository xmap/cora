"""Pure-decider tests for `mark_supply_recovering` slice (10a-b).

Single-source guard: source set `{Unavailable}` only.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    InvalidSupplyReasonError,
    Supply,
    SupplyCannotMarkRecoveringError,
    SupplyMarkedRecovering,
    SupplyName,
    SupplyNotFoundError,
    SupplyScope,
    SupplyStatus,
)
from cora.supply.features import mark_supply_recovering
from cora.supply.features.mark_supply_recovering import MarkSupplyRecovering

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_SUPPLY_ID = uuid4()
_ACTOR_ID = ActorId(uuid4())


def _supply(status: SupplyStatus) -> Supply:
    return Supply(
        id=_SUPPLY_ID,
        scope=SupplyScope.BEAMLINE,
        kind="LiquidNitrogen",
        name=SupplyName("2-BM LN2"),
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_event_from_unavailable() -> None:
    events = mark_supply_recovering.decide(
        state=_supply(SupplyStatus.UNAVAILABLE),
        command=MarkSupplyRecovering(supply_id=_SUPPLY_ID, reason="beam returning"),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events == [
        SupplyMarkedRecovering(
            supply_id=_SUPPLY_ID,
            from_status="Unavailable",
            reason="beam returning",
            trigger="Operator",
            triggered_by=_ACTOR_ID,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.parametrize(
    "current_status",
    [
        SupplyStatus.UNKNOWN,
        SupplyStatus.AVAILABLE,
        SupplyStatus.DEGRADED,
        SupplyStatus.RECOVERING,
    ],
)
@pytest.mark.unit
def test_decide_rejects_from_any_non_unavailable_status(
    current_status: SupplyStatus,
) -> None:
    with pytest.raises(SupplyCannotMarkRecoveringError) as exc_info:
        mark_supply_recovering.decide(
            state=_supply(current_status),
            command=MarkSupplyRecovering(supply_id=_SUPPLY_ID, reason="r"),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )
    assert exc_info.value.current_status == current_status


@pytest.mark.unit
def test_decide_rejects_when_supply_not_found() -> None:
    with pytest.raises(SupplyNotFoundError):
        mark_supply_recovering.decide(
            state=None,
            command=MarkSupplyRecovering(supply_id=_SUPPLY_ID, reason="r"),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )


@pytest.mark.unit
def test_decide_trims_reason() -> None:
    events = mark_supply_recovering.decide(
        state=_supply(SupplyStatus.UNAVAILABLE),
        command=MarkSupplyRecovering(supply_id=_SUPPLY_ID, reason="  beam returning  "),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events[0].reason == "beam returning"


@pytest.mark.unit
def test_decide_hardcodes_trigger_to_operator() -> None:
    events = mark_supply_recovering.decide(
        state=_supply(SupplyStatus.UNAVAILABLE),
        command=MarkSupplyRecovering(supply_id=_SUPPLY_ID, reason="r"),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events[0].trigger == "Operator"


@pytest.mark.unit
def test_decide_rejects_empty_reason() -> None:
    with pytest.raises(InvalidSupplyReasonError):
        mark_supply_recovering.decide(
            state=_supply(SupplyStatus.UNAVAILABLE),
            command=MarkSupplyRecovering(supply_id=_SUPPLY_ID, reason="   "),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )
