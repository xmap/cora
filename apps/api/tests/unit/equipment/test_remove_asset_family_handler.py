"""Unit tests for the `remove_asset_family` application handler.

Mirror of `test_add_asset_family_handler.py`. Shared longhand
shape (extra family_id log field).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.asset import (
    AssetCannotRemoveFamilyError,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import (
    add_asset_family,
    register_asset,
    remove_asset_family,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.remove_asset_family import RemoveAssetFamily
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000fb01")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-00000000fb02")
_ADD_EVENT_ID = UUID("01900000-0000-7000-8000-00000000fb03")
_REMOVE_EVENT_ID = UUID("01900000-0000-7000-8000-00000000fb04")
_PARENT_ID = UUID("01900000-0000-7000-8000-00000000a000")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAP1 = UUID("01900000-0000-7000-8000-000000000111")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    return _build_deps_shared(
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _ADD_EVENT_ID, _REMOVE_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _register_and_add_family(deps: Kernel) -> UUID:
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", tier=AssetTier.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=_CAP1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return asset_id


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_and_add_family(deps)

    result = await remove_asset_family.bind(deps)(
        RemoveAssetFamily(asset_id=asset_id, family_id=_CAP1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_asset_capability_removed_event_with_family_id() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_and_add_family(deps)

    await remove_asset_family.bind(deps)(
        RemoveAssetFamily(asset_id=asset_id, family_id=_CAP1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", asset_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetFamilyAdded",
        "AssetFamilyRemoved",
    ]
    removed = events[2]
    assert removed.event_id == _REMOVE_EVENT_ID
    assert removed.metadata == {"command": "RemoveAssetFamily"}
    assert removed.payload["family_id"] == str(_CAP1)


@pytest.mark.unit
async def test_handler_raises_asset_not_found_when_asset_does_not_exist() -> None:
    deps = _build_deps()
    handler = remove_asset_family.bind(deps)

    with pytest.raises(AssetNotFoundError):
        await handler(
            RemoveAssetFamily(asset_id=uuid4(), family_id=_CAP1),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_remove_when_capability_not_present() -> None:
    """Strict-not-idempotent: removing a capability not in the set raises."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", tier=AssetTier.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    with pytest.raises(AssetCannotRemoveFamilyError) as exc_info:
        await remove_asset_family.bind(deps)(
            RemoveAssetFamily(asset_id=asset_id, family_id=_CAP1),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert "not in" in exc_info.value.reason


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_and_add_family(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError) as exc_info:
        await remove_asset_family.bind(deny_deps)(
            RemoveAssetFamily(asset_id=asset_id, family_id=_CAP1),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_and_add_family(deps)

    await remove_asset_family.bind(deps)(
        RemoveAssetFamily(asset_id=asset_id, family_id=_CAP1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Asset", asset_id)
    assert events[2].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_includes_remove_asset_family() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.remove_asset_family)
