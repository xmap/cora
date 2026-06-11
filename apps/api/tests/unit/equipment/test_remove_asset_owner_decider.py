"""Unit tests for the `remove_asset_owner` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotAddOwnerError,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetOwner,
    AssetOwnerName,
    AssetOwnerNotPresentError,
    AssetOwnerRemoved,
    AssetTier,
)
from cora.equipment.features import remove_asset_owner
from cora.equipment.features.remove_asset_owner import RemoveAssetOwner

_NOW = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)


def _asset(
    *,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
    owners: frozenset[AssetOwner] = frozenset(),
) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("Detector-X"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        owners=owners,
    )


@pytest.mark.unit
def test_remove_existing_owner_succeeds() -> None:
    owner = AssetOwner(name=AssetOwnerName("HZB"))
    state = _asset(owners=frozenset({owner, AssetOwner(name=AssetOwnerName("APS"))}))
    events = remove_asset_owner.decide(
        state=state,
        command=RemoveAssetOwner(asset_id=state.id, owner_name=owner.name),
        now=_NOW,
    )
    assert events == [AssetOwnerRemoved(asset_id=state.id, owner_name=owner.name, occurred_at=_NOW)]


@pytest.mark.unit
def test_remove_last_owner_succeeds() -> None:
    """Lock 7: removing the last owner is allowed. The aggregate
    stores 0-n owners; PIDINST 1-n cardinality is a serializer-time
    gate, not an aggregate-time invariant."""
    only_owner = AssetOwner(name=AssetOwnerName("HZB"))
    state = _asset(owners=frozenset({only_owner}))
    events = remove_asset_owner.decide(
        state=state,
        command=RemoveAssetOwner(asset_id=state.id, owner_name=only_owner.name),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].owner_name == only_owner.name


@pytest.mark.unit
def test_remove_unknown_owner_name_raises_not_present_error() -> None:
    state = _asset(owners=frozenset({AssetOwner(name=AssetOwnerName("HZB"))}))
    missing_name = AssetOwnerName("APS")
    with pytest.raises(AssetOwnerNotPresentError) as exc_info:
        remove_asset_owner.decide(
            state=state,
            command=RemoveAssetOwner(asset_id=state.id, owner_name=missing_name),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.name.value == "APS"


@pytest.mark.unit
def test_remove_owner_from_decommissioned_asset_raises_cannot_add_owner_error() -> None:
    owner = AssetOwner(name=AssetOwnerName("HZB"))
    state = _asset(lifecycle=AssetLifecycle.DECOMMISSIONED, owners=frozenset({owner}))
    with pytest.raises(AssetCannotAddOwnerError) as exc_info:
        remove_asset_owner.decide(
            state=state,
            command=RemoveAssetOwner(asset_id=state.id, owner_name=owner.name),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert "Decommissioned" in exc_info.value.reason


@pytest.mark.unit
def test_remove_owner_from_unknown_asset_raises() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        remove_asset_owner.decide(
            state=None,
            command=RemoveAssetOwner(asset_id=target_id, owner_name=AssetOwnerName("HZB")),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id
