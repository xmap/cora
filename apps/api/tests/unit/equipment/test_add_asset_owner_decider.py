"""Unit tests for the `add_asset_owner` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotAddOwnerError,
    AssetLevel,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetOwner,
    AssetOwnerAdded,
    AssetOwnerAlreadyPresentError,
    AssetOwnerContact,
    AssetOwnerName,
)
from cora.equipment.features import add_asset_owner
from cora.equipment.features.add_asset_owner import AddAssetOwner

_NOW = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)


def _asset(
    *,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
    owners: frozenset[AssetOwner] = frozenset(),
) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("Detector-X"),
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        owners=owners,
    )


@pytest.mark.unit
def test_add_owner_to_asset_with_no_owners_succeeds() -> None:
    owner = AssetOwner(name=AssetOwnerName("HZB"))
    state = _asset()
    events = add_asset_owner.decide(
        state=state,
        command=AddAssetOwner(asset_id=state.id, owner=owner),
        now=_NOW,
    )
    assert events == [AssetOwnerAdded(asset_id=state.id, owner=owner, occurred_at=_NOW)]


@pytest.mark.unit
def test_add_owner_to_asset_with_existing_owners_succeeds() -> None:
    existing = AssetOwner(name=AssetOwnerName("APS"))
    new_owner = AssetOwner(name=AssetOwnerName("HZB"))
    state = _asset(owners=frozenset({existing}))
    events = add_asset_owner.decide(
        state=state,
        command=AddAssetOwner(asset_id=state.id, owner=new_owner),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].owner == new_owner


@pytest.mark.unit
def test_add_duplicate_name_raises_already_present_error() -> None:
    """Lock 6: owner names are unique within a single Asset. Adding a
    second owner with the same name but different optional fields
    rejects."""
    existing = AssetOwner(
        name=AssetOwnerName("HZB"),
        contact=AssetOwnerContact("a@hzb.de"),
    )
    duplicate = AssetOwner(
        name=AssetOwnerName("HZB"),
        contact=AssetOwnerContact("b@hzb.de"),
    )
    state = _asset(owners=frozenset({existing}))
    with pytest.raises(AssetOwnerAlreadyPresentError) as exc_info:
        add_asset_owner.decide(
            state=state,
            command=AddAssetOwner(asset_id=state.id, owner=duplicate),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.name.value == "HZB"


@pytest.mark.unit
@pytest.mark.parametrize(
    "lifecycle",
    [
        AssetLifecycle.COMMISSIONED,
        AssetLifecycle.ACTIVE,
        AssetLifecycle.MAINTENANCE,
    ],
)
def test_add_owner_to_non_decommissioned_asset_succeeds(
    lifecycle: AssetLifecycle,
) -> None:
    """Lifecycle independence holds across every non-Decommissioned
    state. Symmetric with `add_asset_alternate_identifier`."""
    state = _asset(lifecycle=lifecycle)
    events = add_asset_owner.decide(
        state=state,
        command=AddAssetOwner(asset_id=state.id, owner=AssetOwner(name=AssetOwnerName("HZB"))),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_add_owner_to_decommissioned_asset_raises_cannot_add_owner_error() -> None:
    state = _asset(lifecycle=AssetLifecycle.DECOMMISSIONED)
    with pytest.raises(AssetCannotAddOwnerError) as exc_info:
        add_asset_owner.decide(
            state=state,
            command=AddAssetOwner(asset_id=state.id, owner=AssetOwner(name=AssetOwnerName("HZB"))),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.name.value == "HZB"
    assert "Decommissioned" in exc_info.value.reason


@pytest.mark.unit
def test_add_owner_to_unknown_asset_raises() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        add_asset_owner.decide(
            state=None,
            command=AddAssetOwner(asset_id=target_id, owner=AssetOwner(name=AssetOwnerName("HZB"))),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id
