"""Unit tests for the `activate_asset` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetActivated,
    AssetCannotActivateError,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import activate_asset
from cora.equipment.features.activate_asset import ActivateAsset

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _asset(*, lifecycle: AssetLifecycle = AssetLifecycle.COMMISSIONED) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("APS-2BM"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=lifecycle,
    )


@pytest.mark.unit
def test_decide_emits_asset_activated_when_lifecycle_is_commissioned() -> None:
    state = _asset(lifecycle=AssetLifecycle.COMMISSIONED)
    events = activate_asset.decide(
        state=state,
        command=ActivateAsset(asset_id=state.id),
        now=_NOW,
    )
    assert events == [AssetActivated(asset_id=state.id, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    """Update-style precondition: state must exist."""
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        activate_asset.decide(
            state=None,
            command=ActivateAsset(asset_id=target_id),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "current",
    [
        AssetLifecycle.ACTIVE,
        AssetLifecycle.MAINTENANCE,
        AssetLifecycle.DECOMMISSIONED,
    ],
)
def test_decide_raises_cannot_activate_for_every_non_commissioned_lifecycle(
    current: AssetLifecycle,
) -> None:
    """Strict semantics, not idempotent: re-activating an already-Active asset raises.

    Three wrong states tested explicitly so a future relaxation has to flip every
    parametrized case deliberately. (Maintenance and Decommissioned
    aren't reachable yet but the lifecycle enum vocabulary is
    complete; pinning them now means later additions don't surprise.)
    """
    state = _asset(lifecycle=current)
    with pytest.raises(AssetCannotActivateError) as exc_info:
        activate_asset.decide(
            state=state,
            command=ActivateAsset(asset_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.current_lifecycle is current


@pytest.mark.unit
def test_decide_error_carries_current_lifecycle_for_diagnostics() -> None:
    """The error message includes both the current state and the
    expected source state — pinned because the route's 409 body
    surfaces this string."""
    state = _asset(lifecycle=AssetLifecycle.ACTIVE)
    with pytest.raises(AssetCannotActivateError) as exc_info:
        activate_asset.decide(
            state=state,
            command=ActivateAsset(asset_id=state.id),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Active" in msg
    assert "Commissioned" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _asset(lifecycle=AssetLifecycle.COMMISSIONED)
    command = ActivateAsset(asset_id=state.id)
    first = activate_asset.decide(state=state, command=command, now=_NOW)
    second = activate_asset.decide(state=state, command=command, now=_NOW)
    assert first == second
