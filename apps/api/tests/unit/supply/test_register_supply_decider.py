"""Pure-decider tests for `register_supply` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    InvalidSupplyKindError,
    InvalidSupplyNameError,
    Supply,
    SupplyAlreadyExistsError,
    SupplyName,
    SupplyRegistered,
    SupplyScope,
    SupplyStatus,
)
from cora.supply.features import register_supply
from cora.supply.features.register_supply import RegisterSupply

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_ACTOR_ID = ActorId(uuid4())


@pytest.mark.unit
def test_decide_emits_supply_registered_when_stream_is_empty() -> None:
    new_id = uuid4()
    events = register_supply.decide(
        state=None,
        command=RegisterSupply(scope=SupplyScope.BEAMLINE, kind="LiquidNitrogen", name="2-BM LN2"),
        now=_NOW,
        new_id=new_id,
        triggered_by=_ACTOR_ID,
    )
    assert events == [
        SupplyRegistered(
            supply_id=new_id,
            scope="Beamline",
            kind="LiquidNitrogen",
            name="2-BM LN2",
            trigger="Operator",
            triggered_by=_ACTOR_ID,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_trims_kind_and_name() -> None:
    new_id = uuid4()
    events = register_supply.decide(
        state=None,
        command=RegisterSupply(
            scope=SupplyScope.FACILITY,
            kind="  PhotonBeam  ",
            name="  APS storage-ring beam  ",
        ),
        now=_NOW,
        new_id=new_id,
        triggered_by=_ACTOR_ID,
    )
    assert events[0].kind == "PhotonBeam"
    assert events[0].name == "APS storage-ring beam"


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Supply(
        id=uuid4(),
        scope=SupplyScope.BEAMLINE,
        kind="LiquidNitrogen",
        name=SupplyName("2-BM LN2"),
        status=SupplyStatus.UNKNOWN,
    )
    with pytest.raises(SupplyAlreadyExistsError) as exc_info:
        register_supply.decide(
            state=existing,
            command=RegisterSupply(scope=SupplyScope.BEAMLINE, kind="LiquidNitrogen", name="other"),
            now=_NOW,
            new_id=uuid4(),
            triggered_by=_ACTOR_ID,
        )
    assert exc_info.value.supply_id == existing.id


@pytest.mark.unit
def test_decide_rejects_empty_kind() -> None:
    with pytest.raises(InvalidSupplyKindError):
        register_supply.decide(
            state=None,
            command=RegisterSupply(scope=SupplyScope.BEAMLINE, kind="   ", name="2-BM"),
            now=_NOW,
            new_id=uuid4(),
            triggered_by=_ACTOR_ID,
        )


@pytest.mark.unit
def test_decide_rejects_too_long_kind() -> None:
    with pytest.raises(InvalidSupplyKindError):
        register_supply.decide(
            state=None,
            command=RegisterSupply(scope=SupplyScope.BEAMLINE, kind="a" * 51, name="2-BM"),
            now=_NOW,
            new_id=uuid4(),
            triggered_by=_ACTOR_ID,
        )


@pytest.mark.unit
def test_decide_rejects_empty_name() -> None:
    with pytest.raises(InvalidSupplyNameError):
        register_supply.decide(
            state=None,
            command=RegisterSupply(scope=SupplyScope.BEAMLINE, kind="LiquidNitrogen", name="   "),
            now=_NOW,
            new_id=uuid4(),
            triggered_by=_ACTOR_ID,
        )


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    command = RegisterSupply(scope=SupplyScope.BEAMLINE, kind="LiquidNitrogen", name="2-BM LN2")
    first = register_supply.decide(
        state=None, command=command, now=_NOW, new_id=new_id, triggered_by=_ACTOR_ID
    )
    second = register_supply.decide(
        state=None, command=command, now=_NOW, new_id=new_id, triggered_by=_ACTOR_ID
    )
    assert first == second
