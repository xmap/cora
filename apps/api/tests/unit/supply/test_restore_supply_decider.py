"""Pure-decider tests for `restore_supply` slice (10a-b).

Single-source guard: source set `{Recovering}` only. Distinct from
`mark_supply_available` (which exits Unknown -> Available); the
two slices target the same Available status with different audit
semantics per the Phoebus latched-alarm precedent.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    InvalidSupplyReasonError,
    Supply,
    SupplyCannotRestoreError,
    SupplyName,
    SupplyNotFoundError,
    SupplyRestored,
    SupplyScope,
    SupplyStatus,
)
from cora.supply.features import restore_supply
from cora.supply.features.restore_supply import RestoreSupply

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
def test_decide_emits_event_from_recovering() -> None:
    events = restore_supply.decide(
        state=_supply(SupplyStatus.RECOVERING),
        command=RestoreSupply(supply_id=_SUPPLY_ID, reason="ops confirms stable"),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events == [
        SupplyRestored(
            supply_id=_SUPPLY_ID,
            from_status="Recovering",
            reason="ops confirms stable",
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
        SupplyStatus.UNAVAILABLE,
    ],
)
@pytest.mark.unit
def test_decide_rejects_from_any_non_recovering_status(
    current_status: SupplyStatus,
) -> None:
    """Restore is exclusively the Recovering -> Available exit. Notably,
    Unknown -> Available exits via mark_supply_available (distinct audit
    semantics)."""
    with pytest.raises(SupplyCannotRestoreError) as exc_info:
        restore_supply.decide(
            state=_supply(current_status),
            command=RestoreSupply(supply_id=_SUPPLY_ID, reason="r"),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )
    assert exc_info.value.current_status == current_status


@pytest.mark.unit
def test_decide_rejects_when_supply_not_found() -> None:
    with pytest.raises(SupplyNotFoundError):
        restore_supply.decide(
            state=None,
            command=RestoreSupply(supply_id=_SUPPLY_ID, reason="r"),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )


@pytest.mark.unit
def test_decide_trims_reason() -> None:
    events = restore_supply.decide(
        state=_supply(SupplyStatus.RECOVERING),
        command=RestoreSupply(supply_id=_SUPPLY_ID, reason="  ops confirms stable  "),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events[0].reason == "ops confirms stable"


@pytest.mark.unit
def test_decide_hardcodes_trigger_to_operator() -> None:
    events = restore_supply.decide(
        state=_supply(SupplyStatus.RECOVERING),
        command=RestoreSupply(supply_id=_SUPPLY_ID, reason="r"),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events[0].trigger == "Operator"


@pytest.mark.unit
def test_decide_rejects_empty_reason() -> None:
    with pytest.raises(InvalidSupplyReasonError):
        restore_supply.decide(
            state=_supply(SupplyStatus.RECOVERING),
            command=RestoreSupply(supply_id=_SUPPLY_ID, reason=""),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )
