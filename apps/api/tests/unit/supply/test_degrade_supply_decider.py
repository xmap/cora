"""Pure-decider tests for `degrade_supply` slice (10a-b).

Multi-source guard: source set `{Unknown, Available, Recovering}`.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    InvalidSupplyReasonError,
    Supply,
    SupplyCannotDegradeError,
    SupplyDegraded,
    SupplyName,
    SupplyNotFoundError,
    SupplyScope,
    SupplyStatus,
)
from cora.supply.features import degrade_supply
from cora.supply.features.degrade_supply import DegradeSupply

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


@pytest.mark.parametrize(
    "current_status",
    [SupplyStatus.UNKNOWN, SupplyStatus.AVAILABLE, SupplyStatus.RECOVERING],
)
@pytest.mark.unit
def test_decide_emits_supply_degraded_from_legal_source(
    current_status: SupplyStatus,
) -> None:
    events = degrade_supply.decide(
        state=_supply(current_status),
        command=DegradeSupply(supply_id=_SUPPLY_ID, reason="half-current"),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events == [
        SupplyDegraded(
            supply_id=_SUPPLY_ID,
            from_status=current_status.value,
            reason="half-current",
            trigger="Operator",
            triggered_by=_ACTOR_ID,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.parametrize(
    "current_status",
    [SupplyStatus.DEGRADED, SupplyStatus.UNAVAILABLE],
)
@pytest.mark.unit
def test_decide_rejects_when_status_not_in_source_set(
    current_status: SupplyStatus,
) -> None:
    """`Unavailable` cannot degrade directly (must go via mark_recovering first).
    `Degraded` raises strict-not-idempotent."""
    with pytest.raises(SupplyCannotDegradeError) as exc_info:
        degrade_supply.decide(
            state=_supply(current_status),
            command=DegradeSupply(supply_id=_SUPPLY_ID, reason="r"),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )
    assert exc_info.value.current_status == current_status


@pytest.mark.unit
def test_decide_rejects_when_supply_not_found() -> None:
    with pytest.raises(SupplyNotFoundError) as exc_info:
        degrade_supply.decide(
            state=None,
            command=DegradeSupply(supply_id=_SUPPLY_ID, reason="r"),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )
    assert exc_info.value.supply_id == _SUPPLY_ID


@pytest.mark.unit
def test_decide_trims_reason() -> None:
    events = degrade_supply.decide(
        state=_supply(SupplyStatus.AVAILABLE),
        command=DegradeSupply(supply_id=_SUPPLY_ID, reason="  half-current  "),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events[0].reason == "half-current"


@pytest.mark.unit
def test_decide_hardcodes_trigger_to_operator() -> None:
    events = degrade_supply.decide(
        state=_supply(SupplyStatus.AVAILABLE),
        command=DegradeSupply(supply_id=_SUPPLY_ID, reason="r"),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events[0].trigger == "Operator"


@pytest.mark.unit
def test_decide_rejects_empty_reason() -> None:
    with pytest.raises(InvalidSupplyReasonError):
        degrade_supply.decide(
            state=_supply(SupplyStatus.AVAILABLE),
            command=DegradeSupply(supply_id=_SUPPLY_ID, reason="   "),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )
