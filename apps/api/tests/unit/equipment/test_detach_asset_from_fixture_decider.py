"""Unit tests for the `detach_asset_from_fixture` slice's pure decider."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetAttachedToDifferentFixtureError,
    AssetDetachedFromFixture,
    AssetLifecycle,
    AssetName,
    AssetNotAttachedToFixtureError,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import detach_asset_from_fixture
from cora.equipment.features.detach_asset_from_fixture import DetachAssetFromFixture

_NOW = datetime(2026, 6, 4, 12, 0, 0, tzinfo=UTC)


def _asset(
    asset_id: UUID,
    *,
    lifecycle: AssetLifecycle = AssetLifecycle.COMMISSIONED,
    fixture_id: UUID | None = None,
) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("Cam-1"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        fixture_id=fixture_id,
    )


@pytest.mark.unit
def test_decide_emits_detached_event_when_attached_to_matching_fixture() -> None:
    asset_id = uuid4()
    fixture_id = uuid4()
    asset = _asset(asset_id, fixture_id=fixture_id)
    events = detach_asset_from_fixture.decide(
        state=asset,
        command=DetachAssetFromFixture(asset_id=asset_id, fixture_id=fixture_id),
        now=_NOW,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, AssetDetachedFromFixture)
    assert event.asset_id == asset_id
    assert event.fixture_id == fixture_id
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decide_rejects_missing_asset_with_asset_not_found() -> None:
    target = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        detach_asset_from_fixture.decide(
            state=None,
            command=DetachAssetFromFixture(asset_id=target, fixture_id=uuid4()),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target


@pytest.mark.unit
def test_decide_rejects_standalone_asset_with_not_attached() -> None:
    asset_id = uuid4()
    asset = _asset(asset_id, fixture_id=None)
    with pytest.raises(AssetNotAttachedToFixtureError) as exc_info:
        detach_asset_from_fixture.decide(
            state=asset,
            command=DetachAssetFromFixture(asset_id=asset_id, fixture_id=uuid4()),
            now=_NOW,
        )
    assert exc_info.value.asset_id == asset_id


@pytest.mark.unit
def test_decide_rejects_different_fixture_with_attached_to_different() -> None:
    asset_id = uuid4()
    current_fixture_id = uuid4()
    requested_fixture_id = uuid4()
    asset = _asset(asset_id, fixture_id=current_fixture_id)
    with pytest.raises(AssetAttachedToDifferentFixtureError) as exc_info:
        detach_asset_from_fixture.decide(
            state=asset,
            command=DetachAssetFromFixture(asset_id=asset_id, fixture_id=requested_fixture_id),
            now=_NOW,
        )
    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.requested_fixture_id == requested_fixture_id
    assert exc_info.value.current_fixture_id == current_fixture_id


@pytest.mark.unit
def test_decide_accepts_decommissioned_asset() -> None:
    """Cleanup workflow: a Decommissioned Asset MUST be detachable."""
    asset_id = uuid4()
    fixture_id = uuid4()
    asset = _asset(
        asset_id,
        lifecycle=AssetLifecycle.DECOMMISSIONED,
        fixture_id=fixture_id,
    )
    events = detach_asset_from_fixture.decide(
        state=asset,
        command=DetachAssetFromFixture(asset_id=asset_id, fixture_id=fixture_id),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], AssetDetachedFromFixture)


@pytest.mark.unit
def test_decide_accepts_active_asset() -> None:
    asset_id = uuid4()
    fixture_id = uuid4()
    asset = _asset(asset_id, lifecycle=AssetLifecycle.ACTIVE, fixture_id=fixture_id)
    events = detach_asset_from_fixture.decide(
        state=asset,
        command=DetachAssetFromFixture(asset_id=asset_id, fixture_id=fixture_id),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_accepts_maintenance_asset() -> None:
    asset_id = uuid4()
    fixture_id = uuid4()
    asset = _asset(asset_id, lifecycle=AssetLifecycle.MAINTENANCE, fixture_id=fixture_id)
    events = detach_asset_from_fixture.decide(
        state=asset,
        command=DetachAssetFromFixture(asset_id=asset_id, fixture_id=fixture_id),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_is_pure_same_inputs_yield_same_events() -> None:
    asset_id = uuid4()
    fixture_id = uuid4()
    asset = _asset(asset_id, fixture_id=fixture_id)
    command = DetachAssetFromFixture(asset_id=asset_id, fixture_id=fixture_id)
    events_a = detach_asset_from_fixture.decide(state=asset, command=command, now=_NOW)
    events_b = detach_asset_from_fixture.decide(state=asset, command=command, now=_NOW)
    assert events_a == events_b
