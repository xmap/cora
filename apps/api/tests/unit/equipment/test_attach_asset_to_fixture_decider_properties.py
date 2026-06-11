"""Property-based tests for `attach_asset_to_fixture.decide`."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import (
    Asset,
    AssetAlreadyAttachedToFixtureError,
    AssetAttachedToFixture,
    AssetCannotAttachToFixtureError,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.aggregates.fixture import (
    Fixture,
    FixtureNotFoundError,
    SlotAssetBinding,
)
from cora.equipment.features import attach_asset_to_fixture
from cora.equipment.features.attach_asset_to_fixture import (
    AttachAssetToFixture,
    AttachAssetToFixtureContext,
)
from tests._strategies import aware_datetimes


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


def _fixture(fixture_id: UUID, *, bound_asset_ids: frozenset[UUID]) -> Fixture:
    return Fixture(
        id=fixture_id,
        assembly_id=uuid4(),
        assembly_content_hash="a" * 64,
        surface_id=uuid4(),
        slot_asset_bindings=frozenset(
            SlotAssetBinding(slot_name="camera", asset_id=aid) for aid in bound_asset_ids
        ),
    )


_ATTACHABLE_LIFECYCLES = st.sampled_from(
    (
        AssetLifecycle.COMMISSIONED,
        AssetLifecycle.ACTIVE,
        AssetLifecycle.MAINTENANCE,
    )
)


@pytest.mark.unit
@given(now=aware_datetimes())
def test_decide_none_asset_always_raises_not_found(now: datetime) -> None:
    target = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        attach_asset_to_fixture.decide(
            state=None,
            command=AttachAssetToFixture(asset_id=target, fixture_id=uuid4()),
            context=AttachAssetToFixtureContext(asset_state=None, fixture_state=None),
            now=now,
        )
    assert exc_info.value.asset_id == target


@pytest.mark.unit
@given(now=aware_datetimes())
def test_decide_none_fixture_always_raises_fixture_not_found(now: datetime) -> None:
    asset_id = uuid4()
    fixture_target = uuid4()
    asset = _asset(asset_id)
    with pytest.raises(FixtureNotFoundError) as exc_info:
        attach_asset_to_fixture.decide(
            state=asset,
            command=AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_target),
            context=AttachAssetToFixtureContext(asset_state=asset, fixture_state=None),
            now=now,
        )
    assert exc_info.value.fixture_id == fixture_target


@pytest.mark.unit
@given(lifecycle=_ATTACHABLE_LIFECYCLES, now=aware_datetimes())
def test_decide_any_attachable_lifecycle_emits_event(
    lifecycle: AssetLifecycle,
    now: datetime,
) -> None:
    asset_id = uuid4()
    fixture_id = uuid4()
    asset = _asset(asset_id, lifecycle=lifecycle)
    fixture = _fixture(fixture_id, bound_asset_ids=frozenset({asset_id}))
    events = attach_asset_to_fixture.decide(
        state=asset,
        command=AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id),
        context=AttachAssetToFixtureContext(asset_state=asset, fixture_state=fixture),
        now=now,
    )
    assert len(events) == 1
    assert isinstance(events[0], AssetAttachedToFixture)


@pytest.mark.unit
@given(now=aware_datetimes())
def test_decide_already_attached_always_raises(now: datetime) -> None:
    asset_id = uuid4()
    fixture_id = uuid4()
    existing = uuid4()
    asset = _asset(asset_id, fixture_id=existing)
    fixture = _fixture(fixture_id, bound_asset_ids=frozenset({asset_id}))
    with pytest.raises(AssetAlreadyAttachedToFixtureError) as exc_info:
        attach_asset_to_fixture.decide(
            state=asset,
            command=AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id),
            context=AttachAssetToFixtureContext(
                asset_state=asset,
                fixture_state=fixture,
            ),
            now=now,
        )
    assert exc_info.value.current_fixture_id == existing


@pytest.mark.unit
@given(now=aware_datetimes())
def test_decide_decommissioned_always_raises_cannot_attach(now: datetime) -> None:
    asset_id = uuid4()
    fixture_id = uuid4()
    asset = _asset(asset_id, lifecycle=AssetLifecycle.DECOMMISSIONED)
    fixture = _fixture(fixture_id, bound_asset_ids=frozenset({asset_id}))
    with pytest.raises(AssetCannotAttachToFixtureError):
        attach_asset_to_fixture.decide(
            state=asset,
            command=AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id),
            context=AttachAssetToFixtureContext(
                asset_state=asset,
                fixture_state=fixture,
            ),
            now=now,
        )
