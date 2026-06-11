"""Unit tests for the `enter_asset_maintenance` application handler.

Mirror of `activate_asset` handler tests (same single-source
update-style template). Asset path: register + activate (to reach
Active) + enter_asset_maintenance.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.asset import (
    AssetCannotEnterMaintenanceError,
    AssetLifecycle,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import activate_asset, enter_asset_maintenance, register_asset
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.enter_asset_maintenance import EnterAssetMaintenance
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000008ca1")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000008ce1")
_ACTIVATE_EVENT_ID = UUID("01900000-0000-7000-8000-000000008ce2")
_ENTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000008ce3")
_PARENT_ID = UUID("01900000-0000-7000-8000-00000000a000")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    return _build_deps_shared(
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _ACTIVATE_EVENT_ID, _ENTER_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _register_and_activate(deps: Kernel) -> UUID:
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", tier=AssetTier.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return asset_id


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_and_activate(deps)

    result = await enter_asset_maintenance.bind(deps)(
        EnterAssetMaintenance(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_asset_maintenance_entered_event() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_and_activate(deps)

    await enter_asset_maintenance.bind(deps)(
        EnterAssetMaintenance(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", asset_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetActivated",
        "AssetMaintenanceEntered",
    ]
    entered = events[2]
    assert entered.event_id == _ENTER_EVENT_ID
    assert entered.metadata == {"command": "EnterAssetMaintenance"}


@pytest.mark.unit
async def test_handler_raises_asset_not_found_when_asset_does_not_exist() -> None:
    deps = _build_deps()
    handler = enter_asset_maintenance.bind(deps)

    with pytest.raises(AssetNotFoundError):
        await handler(
            EnterAssetMaintenance(asset_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_enter_asset_maintenance_from_commissioned() -> None:
    """Pre-service Commissioned assets cannot enter maintenance."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", tier=AssetTier.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    with pytest.raises(AssetCannotEnterMaintenanceError) as exc_info:
        await enter_asset_maintenance.bind(deps)(
            EnterAssetMaintenance(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.current_lifecycle is AssetLifecycle.COMMISSIONED


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_and_activate(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError) as exc_info:
        await enter_asset_maintenance.bind(deny_deps)(
            EnterAssetMaintenance(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_and_activate(deps)

    await enter_asset_maintenance.bind(deps)(
        EnterAssetMaintenance(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Asset", asset_id)
    assert events[2].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_includes_enter_asset_maintenance() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.enter_asset_maintenance)
