"""Pure-decider tests for the `restore_supply` slice.

Multi-source guard: `{Recovering, Degraded} -> Available`, an operator
declaring a resource back to nominal. Distinct from
`mark_supply_available` (which exits `Unknown -> Available`); the two
slices reach the same status with different audit semantics per the
Phoebus latched-alarm precedent.

`from_status` is asserted on both permitted sources, because it is what
lets one event class carry two facts and is therefore the reason the
source set could widen without a second event.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    InvalidSupplyReasonError,
    Supply,
    SupplyCannotRestoreError,
    SupplyName,
    SupplyNotFoundError,
    SupplyRestored,
    SupplyStatus,
)
from cora.supply.features import restore_supply
from cora.supply.features.restore_supply import RestoreSupply

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_SUPPLY_ID = uuid4()
_ACTOR_ID = ActorId(uuid4())
_FACILITY_CODE = FacilityCode("aps")


def _supply(status: SupplyStatus) -> Supply:
    return Supply(
        id=_SUPPLY_ID,
        kind="LiquidNitrogen",
        name=SupplyName("2-BM LN2"),
        facility_code=_FACILITY_CODE,
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
        SupplyStatus.UNAVAILABLE,
        SupplyStatus.DECOMMISSIONED,
    ],
)
@pytest.mark.unit
def test_decide_rejects_from_a_disqualifying_status(
    current_status: SupplyStatus,
) -> None:
    """Restore accepts Recovering and Degraded; these four are the rest.

    `Unknown` exits via mark_supply_available instead (distinct audit
    semantics: first observation, not a return to nominal). `Available`
    is already there and this slice is strict-not-idempotent.
    `Unavailable` has to pass through `Recovering` first, because a
    resource that was down deserves the intermediate step where a
    monitor can say it looks better before a person says it is.
    `Decommissioned` is the lifecycle terminal.
    """
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


@pytest.mark.unit
def test_decide_emits_event_from_degraded() -> None:
    """The transition the FSM documented and nothing could perform.

    Before this, a degraded resource could only go deeper: the exit ran
    through `mark_supply_unavailable`, which meant appending "this was
    unavailable" about a resource that was never down.
    """
    events = restore_supply.decide(
        state=_supply(SupplyStatus.DEGRADED),
        command=RestoreSupply(supply_id=_SUPPLY_ID, reason="flow back above set point"),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events == [
        SupplyRestored(
            supply_id=_SUPPLY_ID,
            from_status="Degraded",
            reason="flow back above set point",
            trigger="Operator",
            triggered_by=_ACTOR_ID,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_from_status_distinguishes_the_two_permitted_sources() -> None:
    """One event class, two readable facts. This is the whole design.

    If `from_status` did not carry the source, "restored after an outage"
    and "restored after a shortfall" would be indistinguishable in the
    record and the widening would have needed a second event class.
    """
    command = RestoreSupply(supply_id=_SUPPLY_ID, reason="back to nominal")
    from_recovering = restore_supply.decide(
        state=_supply(SupplyStatus.RECOVERING),
        command=command,
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    from_degraded = restore_supply.decide(
        state=_supply(SupplyStatus.DEGRADED),
        command=command,
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert from_recovering[0].from_status == "Recovering"
    assert from_degraded[0].from_status == "Degraded"
    assert type(from_recovering[0]) is type(from_degraded[0])
