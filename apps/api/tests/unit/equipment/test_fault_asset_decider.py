"""Unit tests for the `fault_asset` slice's pure decider.

Target-state transition: any condition -> Faulted.
Mirror of `degrade_asset` decider tests; same shape, different
target.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCondition,
    AssetFaulted,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import fault_asset
from cora.equipment.features.fault_asset import FaultAsset

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)


def _asset(
    *,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
    condition: AssetCondition = AssetCondition.NOMINAL,
) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("Pump-Edwards-XDS35i"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        condition=condition,
    )


@pytest.mark.unit
def test_decide_emits_event_when_faulting_from_nominal() -> None:
    state = _asset(condition=AssetCondition.NOMINAL)
    events = fault_asset.decide(
        state=state,
        command=FaultAsset(asset_id=state.id, reason="vacuum pump seized"),
        now=_NOW,
    )
    assert events == [
        AssetFaulted(
            asset_id=state.id,
            reason="vacuum pump seized",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_emits_event_when_faulting_from_degraded() -> None:
    """Worsening: Degraded -> Faulted via fault_asset."""
    state = _asset(condition=AssetCondition.DEGRADED)
    events = fault_asset.decide(
        state=state,
        command=FaultAsset(asset_id=state.id, reason="bearing failure"),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].reason == "bearing failure"


@pytest.mark.unit
def test_decide_no_op_when_already_faulted() -> None:
    state = _asset(condition=AssetCondition.FAULTED)
    events = fault_asset.decide(
        state=state,
        command=FaultAsset(asset_id=state.id, reason="still broken"),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        fault_asset.decide(
            state=None,
            command=FaultAsset(asset_id=target_id, reason="missing"),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "lifecycle",
    [
        AssetLifecycle.COMMISSIONED,
        AssetLifecycle.ACTIVE,
        AssetLifecycle.MAINTENANCE,
        AssetLifecycle.DECOMMISSIONED,
    ],
)
def test_decide_accepts_fault_in_any_lifecycle_state(
    lifecycle: AssetLifecycle,
) -> None:
    state = _asset(lifecycle=lifecycle, condition=AssetCondition.NOMINAL)
    events = fault_asset.decide(
        state=state,
        command=FaultAsset(asset_id=state.id, reason="check"),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _asset()
    command = FaultAsset(asset_id=state.id, reason="check")
    first = fault_asset.decide(state=state, command=command, now=_NOW)
    second = fault_asset.decide(state=state, command=command, now=_NOW)
    assert first == second
