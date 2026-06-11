"""Unit tests for the `restore_asset` slice's pure decider.

Target-state transition: any condition -> Nominal.
Mirror of `degrade_asset` decider tests; same shape, target Nominal.

Distinct from `exit_asset_maintenance` which moves lifecycle
(Maintenance -> Active); this slice moves condition (any -> Nominal).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCondition,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetRestored,
    AssetTier,
)
from cora.equipment.features import restore_asset
from cora.equipment.features.restore_asset import RestoreAsset

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)


def _asset(
    *,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
    condition: AssetCondition = AssetCondition.FAULTED,
) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("Stage-Aerotech-A3200"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        condition=condition,
    )


@pytest.mark.unit
def test_decide_emits_event_when_restoring_from_faulted() -> None:
    state = _asset(condition=AssetCondition.FAULTED)
    events = restore_asset.decide(
        state=state,
        command=RestoreAsset(asset_id=state.id, reason="replaced flat cable"),
        now=_NOW,
    )
    assert events == [
        AssetRestored(
            asset_id=state.id,
            reason="replaced flat cable",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_emits_event_when_restoring_from_degraded() -> None:
    state = _asset(condition=AssetCondition.DEGRADED)
    events = restore_asset.decide(
        state=state,
        command=RestoreAsset(asset_id=state.id, reason="hot pixel mapped out"),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].reason == "hot pixel mapped out"


@pytest.mark.unit
def test_decide_no_op_when_already_nominal() -> None:
    state = _asset(condition=AssetCondition.NOMINAL)
    events = restore_asset.decide(
        state=state,
        command=RestoreAsset(asset_id=state.id, reason="redundant call"),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        restore_asset.decide(
            state=None,
            command=RestoreAsset(asset_id=target_id, reason="missing"),
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
def test_decide_accepts_restore_in_any_lifecycle_state(
    lifecycle: AssetLifecycle,
) -> None:
    state = _asset(lifecycle=lifecycle, condition=AssetCondition.FAULTED)
    events = restore_asset.decide(
        state=state,
        command=RestoreAsset(asset_id=state.id, reason="check"),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _asset()
    command = RestoreAsset(asset_id=state.id, reason="check")
    first = restore_asset.decide(state=state, command=command, now=_NOW)
    second = restore_asset.decide(state=state, command=command, now=_NOW)
    assert first == second
