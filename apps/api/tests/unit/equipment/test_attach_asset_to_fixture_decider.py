"""Unit tests for the `attach_asset_to_fixture` slice's pure decider."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetAlreadyAttachedToFixtureError,
    AssetAttachedToFixture,
    AssetCannotAttachToFixtureError,
    AssetLifecycle,
    AssetName,
    AssetNotBoundInFixtureError,
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

_NOW = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)


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


def _fixture(
    fixture_id: UUID,
    *,
    bound_asset_ids: frozenset[UUID] = frozenset(),
) -> Fixture:
    return Fixture(
        id=fixture_id,
        assembly_id=uuid4(),
        assembly_content_hash="a" * 64,
        surface_id=uuid4(),
        slot_asset_bindings=frozenset(
            SlotAssetBinding(slot_name="camera", asset_id=aid) for aid in bound_asset_ids
        ),
    )


@pytest.mark.unit
def test_decide_emits_attached_event_when_all_invariants_hold() -> None:
    asset_id = uuid4()
    fixture_id = uuid4()
    asset = _asset(asset_id)
    fixture = _fixture(fixture_id, bound_asset_ids=frozenset({asset_id}))
    events = attach_asset_to_fixture.decide(
        state=asset,
        command=AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id),
        context=AttachAssetToFixtureContext(asset_state=asset, fixture_state=fixture),
        now=_NOW,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, AssetAttachedToFixture)
    assert event.asset_id == asset_id
    assert event.fixture_id == fixture_id
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decide_rejects_missing_asset_with_asset_not_found() -> None:
    target = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        attach_asset_to_fixture.decide(
            state=None,
            command=AttachAssetToFixture(asset_id=target, fixture_id=uuid4()),
            context=AttachAssetToFixtureContext(asset_state=None, fixture_state=None),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target


@pytest.mark.unit
def test_decide_rejects_missing_fixture_with_fixture_not_found() -> None:
    asset_id = uuid4()
    fixture_target = uuid4()
    asset = _asset(asset_id)
    with pytest.raises(FixtureNotFoundError) as exc_info:
        attach_asset_to_fixture.decide(
            state=asset,
            command=AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_target),
            context=AttachAssetToFixtureContext(
                asset_state=asset,
                fixture_state=None,
            ),
            now=_NOW,
        )
    assert exc_info.value.fixture_id == fixture_target


@pytest.mark.unit
def test_decide_rejects_double_attach_with_already_attached() -> None:
    asset_id = uuid4()
    fixture_id = uuid4()
    existing_fixture_id = uuid4()
    asset = _asset(asset_id, fixture_id=existing_fixture_id)
    fixture = _fixture(fixture_id, bound_asset_ids=frozenset({asset_id}))
    with pytest.raises(AssetAlreadyAttachedToFixtureError) as exc_info:
        attach_asset_to_fixture.decide(
            state=asset,
            command=AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id),
            context=AttachAssetToFixtureContext(
                asset_state=asset,
                fixture_state=fixture,
            ),
            now=_NOW,
        )
    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.current_fixture_id == existing_fixture_id


@pytest.mark.unit
def test_decide_rejects_decommissioned_asset_with_cannot_attach() -> None:
    asset_id = uuid4()
    fixture_id = uuid4()
    asset = _asset(asset_id, lifecycle=AssetLifecycle.DECOMMISSIONED)
    fixture = _fixture(fixture_id, bound_asset_ids=frozenset({asset_id}))
    with pytest.raises(AssetCannotAttachToFixtureError) as exc_info:
        attach_asset_to_fixture.decide(
            state=asset,
            command=AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id),
            context=AttachAssetToFixtureContext(
                asset_state=asset,
                fixture_state=fixture,
            ),
            now=_NOW,
        )
    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.current_lifecycle == AssetLifecycle.DECOMMISSIONED


@pytest.mark.unit
def test_decide_rejects_asset_not_in_fixture_bindings() -> None:
    """Phantom back-reference guard: Asset not in Fixture.slot_asset_bindings."""
    asset_id = uuid4()
    other_asset_id = uuid4()  # in fixture's bindings, but not the target
    fixture_id = uuid4()
    asset = _asset(asset_id)
    fixture = _fixture(fixture_id, bound_asset_ids=frozenset({other_asset_id}))
    with pytest.raises(AssetNotBoundInFixtureError) as exc_info:
        attach_asset_to_fixture.decide(
            state=asset,
            command=AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id),
            context=AttachAssetToFixtureContext(
                asset_state=asset,
                fixture_state=fixture,
            ),
            now=_NOW,
        )
    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.fixture_id == fixture_id


@pytest.mark.unit
def test_decide_accepts_active_lifecycle() -> None:
    asset_id = uuid4()
    fixture_id = uuid4()
    asset = _asset(asset_id, lifecycle=AssetLifecycle.ACTIVE)
    fixture = _fixture(fixture_id, bound_asset_ids=frozenset({asset_id}))
    events = attach_asset_to_fixture.decide(
        state=asset,
        command=AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id),
        context=AttachAssetToFixtureContext(asset_state=asset, fixture_state=fixture),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_accepts_maintenance_lifecycle() -> None:
    asset_id = uuid4()
    fixture_id = uuid4()
    asset = _asset(asset_id, lifecycle=AssetLifecycle.MAINTENANCE)
    fixture = _fixture(fixture_id, bound_asset_ids=frozenset({asset_id}))
    events = attach_asset_to_fixture.decide(
        state=asset,
        command=AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id),
        context=AttachAssetToFixtureContext(asset_state=asset, fixture_state=fixture),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_is_pure_same_inputs_yield_same_events() -> None:
    asset_id = uuid4()
    fixture_id = uuid4()
    asset = _asset(asset_id)
    fixture = _fixture(fixture_id, bound_asset_ids=frozenset({asset_id}))
    context = AttachAssetToFixtureContext(asset_state=asset, fixture_state=fixture)
    command = AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id)
    events_a = attach_asset_to_fixture.decide(
        state=asset,
        command=command,
        context=context,
        now=_NOW,
    )
    events_b = attach_asset_to_fixture.decide(
        state=asset,
        command=command,
        context=context,
        now=_NOW,
    )
    assert events_a == events_b
