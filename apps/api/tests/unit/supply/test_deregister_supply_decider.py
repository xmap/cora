"""Pure-decider tests for `deregister_supply` slice.

Widest-source transition: any non-Decommissioned status -> Decommissioned.
Strict-not-idempotent (re-issuing on a Decommissioned Supply raises).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    InvalidSupplyReasonError,
    Supply,
    SupplyCannotDeregisterError,
    SupplyDeregistered,
    SupplyName,
    SupplyNotFoundError,
    SupplyScope,
    SupplyStatus,
)
from cora.supply.features import deregister_supply
from cora.supply.features.deregister_supply import DeregisterSupply

_NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
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
    [
        SupplyStatus.UNKNOWN,
        SupplyStatus.AVAILABLE,
        SupplyStatus.DEGRADED,
        SupplyStatus.UNAVAILABLE,
        SupplyStatus.RECOVERING,
    ],
)
@pytest.mark.unit
def test_decide_emits_event_from_any_non_decommissioned_status(
    current_status: SupplyStatus,
) -> None:
    events = deregister_supply.decide(
        state=_supply(current_status),
        command=DeregisterSupply(supply_id=_SUPPLY_ID, reason="typo; re-registering"),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events == [
        SupplyDeregistered(
            supply_id=_SUPPLY_ID,
            from_status=current_status.value,
            reason="typo; re-registering",
            trigger="Operator",
            triggered_by=_ACTOR_ID,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_rejects_when_already_decommissioned() -> None:
    """Strict-not-idempotent: re-deregistering a Decommissioned Supply raises."""
    with pytest.raises(SupplyCannotDeregisterError) as exc_info:
        deregister_supply.decide(
            state=_supply(SupplyStatus.DECOMMISSIONED),
            command=DeregisterSupply(supply_id=_SUPPLY_ID, reason="r"),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )
    assert exc_info.value.current_status == SupplyStatus.DECOMMISSIONED
    assert exc_info.value.supply_id == _SUPPLY_ID


@pytest.mark.unit
def test_decide_rejects_when_supply_not_found() -> None:
    with pytest.raises(SupplyNotFoundError):
        deregister_supply.decide(
            state=None,
            command=DeregisterSupply(supply_id=_SUPPLY_ID, reason="r"),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )


@pytest.mark.unit
def test_decide_trims_reason() -> None:
    events = deregister_supply.decide(
        state=_supply(SupplyStatus.AVAILABLE),
        command=DeregisterSupply(supply_id=_SUPPLY_ID, reason="  duplicate entry  "),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events[0].reason == "duplicate entry"


@pytest.mark.unit
def test_decide_hardcodes_trigger_to_operator() -> None:
    """No substream or timer should ever auto-decommission; operator intent only."""
    events = deregister_supply.decide(
        state=_supply(SupplyStatus.AVAILABLE),
        command=DeregisterSupply(supply_id=_SUPPLY_ID, reason="r"),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events[0].trigger == "Operator"


@pytest.mark.unit
def test_decide_rejects_empty_reason() -> None:
    with pytest.raises(InvalidSupplyReasonError):
        deregister_supply.decide(
            state=_supply(SupplyStatus.AVAILABLE),
            command=DeregisterSupply(supply_id=_SUPPLY_ID, reason=""),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )


@pytest.mark.unit
def test_decide_uses_supplied_now_for_occurred_at() -> None:
    """Non-determinism injected from handler per project_non_determinism_principle."""
    custom_now = datetime(2099, 1, 1, 0, 0, 0, tzinfo=UTC)
    events = deregister_supply.decide(
        state=_supply(SupplyStatus.AVAILABLE),
        command=DeregisterSupply(supply_id=_SUPPLY_ID, reason="r"),
        now=custom_now,
        triggered_by=_ACTOR_ID,
    )
    assert events[0].occurred_at == custom_now
