"""Property-based tests for `detach_asset_from_fixture.decide`."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

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
from tests._strategies import aware_datetimes

_ANY_LIFECYCLE = st.sampled_from(
    (
        AssetLifecycle.COMMISSIONED,
        AssetLifecycle.ACTIVE,
        AssetLifecycle.MAINTENANCE,
        AssetLifecycle.DECOMMISSIONED,
    )
)


def _asset(
    asset_id: UUID,
    *,
    lifecycle: AssetLifecycle = AssetLifecycle.COMMISSIONED,
    fixture_id: UUID | None = None,
) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("X"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        fixture_id=fixture_id,
    )


@pytest.mark.unit
@given(now=aware_datetimes())
def test_decide_none_state_always_raises_not_found(now: datetime) -> None:
    target = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        detach_asset_from_fixture.decide(
            state=None,
            command=DetachAssetFromFixture(asset_id=target, fixture_id=uuid4()),
            now=now,
        )
    assert exc_info.value.asset_id == target


@pytest.mark.unit
@given(now=aware_datetimes())
def test_decide_standalone_asset_always_raises_not_attached(now: datetime) -> None:
    asset_id = uuid4()
    asset = _asset(asset_id, fixture_id=None)
    with pytest.raises(AssetNotAttachedToFixtureError) as exc_info:
        detach_asset_from_fixture.decide(
            state=asset,
            command=DetachAssetFromFixture(asset_id=asset_id, fixture_id=uuid4()),
            now=now,
        )
    assert exc_info.value.asset_id == asset_id


@pytest.mark.unit
@given(now=aware_datetimes())
def test_decide_different_fixture_always_raises_attached_to_different(
    now: datetime,
) -> None:
    asset_id = uuid4()
    current = uuid4()
    requested = uuid4()
    asset = _asset(asset_id, fixture_id=current)
    with pytest.raises(AssetAttachedToDifferentFixtureError) as exc_info:
        detach_asset_from_fixture.decide(
            state=asset,
            command=DetachAssetFromFixture(asset_id=asset_id, fixture_id=requested),
            now=now,
        )
    assert exc_info.value.current_fixture_id == current
    assert exc_info.value.requested_fixture_id == requested


@pytest.mark.unit
@given(lifecycle=_ANY_LIFECYCLE, now=aware_datetimes())
def test_decide_any_lifecycle_with_matching_fixture_emits_event(
    lifecycle: AssetLifecycle,
    now: datetime,
) -> None:
    """Detach is lifecycle-agnostic by design (cleanup workflow)."""
    asset_id = uuid4()
    fixture_id = uuid4()
    asset = _asset(asset_id, lifecycle=lifecycle, fixture_id=fixture_id)
    events = detach_asset_from_fixture.decide(
        state=asset,
        command=DetachAssetFromFixture(asset_id=asset_id, fixture_id=fixture_id),
        now=now,
    )
    assert len(events) == 1
    assert isinstance(events[0], AssetDetachedFromFixture)
