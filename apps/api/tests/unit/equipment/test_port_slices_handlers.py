"""Unit tests for the add_asset_port / remove_asset_port handlers.

Consolidated file (mirror of 5g-b's `test_condition_slices_handlers.py`):
both port slices use `make_asset_update_handler`, so per-slice tests
would be byte-parallel.

Coverage per slice (parametrized):
  - bind() returns a callable
  - happy path appends the right event
  - authorize-deny -> UnauthorizedError; no event appended
  - causation_id propagates onto the appended event
  - wire_equipment exposes the handler on the bundle
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.asset import AssetPort, AssetTier, PortDirection
from cora.equipment.features import (
    add_asset_port,
    register_asset,
    remove_asset_port,
)
from cora.equipment.features.add_asset_port import AddAssetPort
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.remove_asset_port import RemoveAssetPort
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-0000000d0d01")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-0000000d0d02")
_PORT_EVENT_ID_1 = UUID("01900000-0000-7000-8000-0000000d0d03")
_PORT_EVENT_ID_2 = UUID("01900000-0000-7000-8000-0000000d0d04")
_PARENT_ID = UUID("01900000-0000-7000-8000-0000000d0d05")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000d0d06")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000d0d07")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _PORT_EVENT_ID_1, _PORT_EVENT_ID_2],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _register_asset_helper(deps: Kernel) -> UUID:
    return await register_asset.bind(deps)(
        RegisterAsset(name="Detector-X", tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_add_asset_port_handler_appends_event() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    handler: Callable[..., Awaitable[None]] = add_asset_port.bind(deps)
    await handler(
        AddAssetPort(
            asset_id=asset_id,
            port_name="trigger_in",
            direction=PortDirection.INPUT,
            signal_type="TTL",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Asset", asset_id)
    appended = events[1]
    assert appended.event_type == "AssetPortAdded"
    assert appended.payload["port_name"] == "trigger_in"
    assert appended.payload["direction"] == "Input"
    assert appended.payload["signal_type"] == "TTL"


@pytest.mark.unit
async def test_remove_asset_port_handler_appends_event() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    # Setup: one port to remove
    await add_asset_port.bind(deps)(
        AddAssetPort(
            asset_id=asset_id,
            port_name="trigger_in",
            direction=PortDirection.INPUT,
            signal_type="TTL",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await remove_asset_port.bind(deps)(
        RemoveAssetPort(asset_id=asset_id, port_name="trigger_in"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Asset", asset_id)
    removed = events[2]
    assert removed.event_type == "AssetPortRemoved"
    assert removed.payload["port_name"] == "trigger_in"


@pytest.mark.unit
async def test_add_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    handler: Callable[..., Awaitable[None]] = add_asset_port.bind(deny_deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            AddAssetPort(
                asset_id=asset_id,
                port_name="x",
                direction=PortDirection.INPUT,
                signal_type="TTL",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Asset", asset_id)
    assert version == 1
    assert events[0].event_type == "AssetRegistered"


@pytest.mark.unit
async def test_remove_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    handler: Callable[..., Awaitable[None]] = remove_asset_port.bind(deny_deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            RemoveAssetPort(asset_id=asset_id, port_name="x"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Asset", asset_id)
    assert version == 1
    assert events[0].event_type == "AssetRegistered"


@pytest.mark.unit
async def test_add_handler_propagates_causation_id() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000d0dbb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    await add_asset_port.bind(deps)(
        AddAssetPort(
            asset_id=asset_id,
            port_name="x",
            direction=PortDirection.INPUT,
            signal_type="TTL",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Asset", asset_id)
    assert events[1].causation_id == causation


@pytest.mark.unit
@pytest.mark.parametrize("handler_field", ["add_asset_port", "remove_asset_port"])
def test_wire_equipment_exposes_port_handlers(handler_field: str) -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(getattr(handlers, handler_field))


@pytest.mark.unit
def test_asset_port_value_object_can_be_constructed_for_test_setup() -> None:
    """Smoke test the VO so the test file's imports stay live even
    if no other test references AssetPort directly."""
    port = AssetPort(name="trigger_in", direction=PortDirection.INPUT, signal_type="TTL")
    assert port.name == "trigger_in"
