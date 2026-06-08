"""Pure-decider tests for `mark_supply_available` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    InvalidSupplyReasonError,
    Supply,
    SupplyCannotMarkAvailableError,
    SupplyMarkedAvailable,
    SupplyName,
    SupplyNotFoundError,
    SupplyScope,
    SupplyStatus,
)
from cora.supply.features import mark_supply_available
from cora.supply.features.mark_supply_available import MarkSupplyAvailable

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_SUPPLY_ID = uuid4()
_ACTOR_ID = ActorId(uuid4())


def _supply(status: SupplyStatus = SupplyStatus.UNKNOWN) -> Supply:
    return Supply(
        id=_SUPPLY_ID,
        scope=SupplyScope.BEAMLINE,
        kind="LiquidNitrogen",
        name=SupplyName("2-BM LN2"),
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_supply_marked_available_when_unknown() -> None:
    events = mark_supply_available.decide(
        state=_supply(SupplyStatus.UNKNOWN),
        command=MarkSupplyAvailable(supply_id=_SUPPLY_ID, reason="operator walkdown"),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events == [
        SupplyMarkedAvailable(
            supply_id=_SUPPLY_ID,
            from_status="Unknown",
            reason="operator walkdown",
            trigger="Operator",
            triggered_by=_ACTOR_ID,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_trims_reason() -> None:
    events = mark_supply_available.decide(
        state=_supply(SupplyStatus.UNKNOWN),
        command=MarkSupplyAvailable(supply_id=_SUPPLY_ID, reason="  control room confirms  "),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events[0].reason == "control room confirms"


@pytest.mark.unit
def test_decide_hardcodes_trigger_to_operator() -> None:
    """10a-a only emits Operator-triggered transitions; Monitor + Auto reserved for later."""
    events = mark_supply_available.decide(
        state=_supply(SupplyStatus.UNKNOWN),
        command=MarkSupplyAvailable(supply_id=_SUPPLY_ID, reason="r"),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events[0].trigger == "Operator"
    assert events[0].triggered_by == _ACTOR_ID


@pytest.mark.unit
def test_decide_rejects_when_supply_not_found() -> None:
    with pytest.raises(SupplyNotFoundError) as exc_info:
        mark_supply_available.decide(
            state=None,
            command=MarkSupplyAvailable(supply_id=_SUPPLY_ID, reason="r"),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )
    assert exc_info.value.supply_id == _SUPPLY_ID


@pytest.mark.parametrize(
    "current_status",
    [
        SupplyStatus.AVAILABLE,
        SupplyStatus.DEGRADED,
        SupplyStatus.UNAVAILABLE,
        SupplyStatus.RECOVERING,
    ],
)
@pytest.mark.unit
def test_decide_rejects_when_status_is_not_unknown(current_status: SupplyStatus) -> None:
    """Single-source guard: only Unknown can be marked Available via this slice.
    Recovering -> Available exits exclusively via restore_supply (10a-b)."""
    with pytest.raises(SupplyCannotMarkAvailableError) as exc_info:
        mark_supply_available.decide(
            state=_supply(current_status),
            command=MarkSupplyAvailable(supply_id=_SUPPLY_ID, reason="r"),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )
    assert exc_info.value.current_status == current_status


@pytest.mark.unit
def test_decide_rejects_empty_reason() -> None:
    with pytest.raises(InvalidSupplyReasonError):
        mark_supply_available.decide(
            state=_supply(SupplyStatus.UNKNOWN),
            command=MarkSupplyAvailable(supply_id=_SUPPLY_ID, reason="   "),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )


@pytest.mark.unit
def test_decide_rejects_too_long_reason() -> None:
    with pytest.raises(InvalidSupplyReasonError):
        mark_supply_available.decide(
            state=_supply(SupplyStatus.UNKNOWN),
            command=MarkSupplyAvailable(supply_id=_SUPPLY_ID, reason="a" * 501),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )
