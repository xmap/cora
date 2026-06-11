"""Unit tests for the `degrade_asset` slice's pure decider.

Target-state transition: any condition -> Degraded. The
decider:
  - Raises AssetNotFoundError on empty state
  - No-ops (returns []) when current condition is already Degraded
  - Emits AssetDegraded(reason, occurred_at) otherwise
  - Is independent of lifecycle (works in any lifecycle state,
    including Decommissioned)
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCondition,
    AssetDegraded,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import degrade_asset
from cora.equipment.features.degrade_asset import DegradeAsset

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)


def _asset(
    *,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
    condition: AssetCondition = AssetCondition.NOMINAL,
) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("Detector-FLIR-Oryx-001"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        condition=condition,
    )


@pytest.mark.unit
def test_decide_emits_event_when_degrading_from_nominal() -> None:
    state = _asset(condition=AssetCondition.NOMINAL)
    events = degrade_asset.decide(
        state=state,
        command=DegradeAsset(asset_id=state.id, reason="hot pixel detected"),
        now=_NOW,
    )
    assert events == [
        AssetDegraded(
            asset_id=state.id,
            reason="hot pixel detected",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_emits_event_when_degrading_from_faulted() -> None:
    """Partial repair: Faulted -> Degraded uses degrade_asset, not
    restore_asset (each slice has a fixed target)."""
    state = _asset(condition=AssetCondition.FAULTED)
    events = degrade_asset.decide(
        state=state,
        command=DegradeAsset(asset_id=state.id, reason="partial repair complete"),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].reason == "partial repair complete"


@pytest.mark.unit
def test_decide_no_op_when_already_degraded() -> None:
    """Re-degrading an already-Degraded asset is a no-op (matches
    5g-a's no-op-on-unchanged precedent). Reason changes alone do
    NOT emit a new event."""
    state = _asset(condition=AssetCondition.DEGRADED)
    events = degrade_asset.decide(
        state=state,
        command=DegradeAsset(asset_id=state.id, reason="different reason"),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        degrade_asset.decide(
            state=None,
            command=DegradeAsset(asset_id=target_id, reason="missing"),
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
def test_decide_accepts_degrade_in_any_lifecycle_state(
    lifecycle: AssetLifecycle,
) -> None:
    """Condition transitions are independent of lifecycle. Even a
    Decommissioned asset can be marked Degraded (honest about
    device-state-in-storage; an asset discovered Faulted on inventory
    check is a legit audit fact)."""
    state = _asset(lifecycle=lifecycle, condition=AssetCondition.NOMINAL)
    events = degrade_asset.decide(
        state=state,
        command=DegradeAsset(asset_id=state.id, reason="check"),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _asset()
    command = DegradeAsset(asset_id=state.id, reason="check")
    first = degrade_asset.decide(state=state, command=command, now=_NOW)
    second = degrade_asset.decide(state=state, command=command, now=_NOW)
    assert first == second
