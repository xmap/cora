"""Unit tests for the `enter_asset_maintenance` slice's pure decider.

Single-source-state guard: `Active -> Maintenance`. Strict
not-idempotent semantics. Mirrors `test_activate_asset_decider.py`.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotEnterMaintenanceError,
    AssetLifecycle,
    AssetMaintenanceEntered,
    AssetName,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import enter_asset_maintenance
from cora.equipment.features.enter_asset_maintenance import EnterAssetMaintenance

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _asset(*, lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("APS-2BM"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=lifecycle,
    )


@pytest.mark.unit
def test_decide_emits_asset_maintenance_entered_for_active_asset() -> None:
    state = _asset(lifecycle=AssetLifecycle.ACTIVE)
    events = enter_asset_maintenance.decide(
        state=state,
        command=EnterAssetMaintenance(asset_id=state.id),
        now=_NOW,
    )
    assert events == [AssetMaintenanceEntered(asset_id=state.id, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        enter_asset_maintenance.decide(
            state=None,
            command=EnterAssetMaintenance(asset_id=target_id),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "current",
    [
        AssetLifecycle.COMMISSIONED,
        AssetLifecycle.MAINTENANCE,
        AssetLifecycle.DECOMMISSIONED,
    ],
)
def test_decide_raises_cannot_enter_asset_maintenance_for_every_disallowed_source(
    current: AssetLifecycle,
) -> None:
    """Strict semantics: Active is the only valid source. Pinned
    that re-entering on already-Maintenance also raises (not no-op),
    and that pre-service Commissioned and post-service Decommissioned
    are both rejected."""
    state = _asset(lifecycle=current)
    with pytest.raises(AssetCannotEnterMaintenanceError) as exc_info:
        enter_asset_maintenance.decide(
            state=state,
            command=EnterAssetMaintenance(asset_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.current_lifecycle is current


@pytest.mark.unit
def test_decide_error_message_lists_active_as_required_source() -> None:
    """Pinned because the route's 409 body surfaces this string and
    the operator needs to see which source state is required."""
    state = _asset(lifecycle=AssetLifecycle.COMMISSIONED)
    with pytest.raises(AssetCannotEnterMaintenanceError) as exc_info:
        enter_asset_maintenance.decide(
            state=state,
            command=EnterAssetMaintenance(asset_id=state.id),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Commissioned" in msg
    assert "Active" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _asset(lifecycle=AssetLifecycle.ACTIVE)
    command = EnterAssetMaintenance(asset_id=state.id)
    first = enter_asset_maintenance.decide(state=state, command=command, now=_NOW)
    second = enter_asset_maintenance.decide(state=state, command=command, now=_NOW)
    assert first == second
