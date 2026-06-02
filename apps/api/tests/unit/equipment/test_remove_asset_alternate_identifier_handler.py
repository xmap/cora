"""Application-handler tests for `remove_asset_alternate_identifier` slice.

Update-style handler via `make_asset_update_handler`; mirrors the
shape of `test_port_slices_handlers.py`. Coverage:

  - happy path appends the right event
  - authorize-deny -> UnauthorizedError; no event appended
  - causation_id propagates onto the appended event
  - wire_equipment exposes the handler on the bundle
  - strict-not-idempotent: removing a non-existent pair raises
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.asset import (
    AlternateIdentifier,
    AlternateIdentifierKind,
    AssetAlternateIdentifierNotPresentError,
    AssetLevel,
)
from cora.equipment.features import (
    add_asset_alternate_identifier,
    register_asset,
    remove_asset_alternate_identifier,
)
from cora.equipment.features.add_asset_alternate_identifier import (
    AddAssetAlternateIdentifier,
)
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.remove_asset_alternate_identifier import (
    RemoveAssetAlternateIdentifier,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-0000000a1d01")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-0000000a1d02")
_ADD_EVENT_ID = UUID("01900000-0000-7000-8000-0000000a1d03")
_REMOVE_EVENT_ID = UUID("01900000-0000-7000-8000-0000000a1d04")
_PARENT_ID = UUID("01900000-0000-7000-8000-0000000a1d05")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000a1d06")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000a1d07")

_IDENTIFIER = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="XYZ-001")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _ADD_EVENT_ID, _REMOVE_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _register_asset_helper(deps: Kernel) -> UUID:
    return await register_asset.bind(deps)(
        RegisterAsset(name="Detector-X", level=AssetLevel.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _add_identifier(deps: Kernel, asset_id: UUID) -> None:
    await add_asset_alternate_identifier.bind(deps)(
        AddAssetAlternateIdentifier(asset_id=asset_id, alternate_identifier=_IDENTIFIER),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_appends_removed_event_on_happy_path() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)
    await _add_identifier(deps, asset_id)

    await remove_asset_alternate_identifier.bind(deps)(
        RemoveAssetAlternateIdentifier(asset_id=asset_id, alternate_identifier=_IDENTIFIER),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Asset", asset_id)
    removed = events[2]
    assert removed.event_type == "AssetAlternateIdentifierRemoved"
    assert removed.payload["alternate_identifier"] == {
        "kind": "SerialNumber",
        "value": "XYZ-001",
    }


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)
    await _add_identifier(deps, asset_id)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError):
        await remove_asset_alternate_identifier.bind(deny_deps)(
            RemoveAssetAlternateIdentifier(asset_id=asset_id, alternate_identifier=_IDENTIFIER),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Asset", asset_id)
    # Only Registered + Added; no Removed appended on deny.
    assert version == 2
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetAlternateIdentifierAdded",
    ]


@pytest.mark.unit
async def test_handler_propagates_causation_id() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000a1dbb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)
    await _add_identifier(deps, asset_id)

    await remove_asset_alternate_identifier.bind(deps)(
        RemoveAssetAlternateIdentifier(asset_id=asset_id, alternate_identifier=_IDENTIFIER),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Asset", asset_id)
    assert events[2].causation_id == causation


@pytest.mark.unit
async def test_handler_raises_not_present_when_pair_missing() -> None:
    """Strict-not-idempotent: removing without a prior add raises."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    with pytest.raises(AssetAlternateIdentifierNotPresentError):
        await remove_asset_alternate_identifier.bind(deps)(
            RemoveAssetAlternateIdentifier(asset_id=asset_id, alternate_identifier=_IDENTIFIER),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Asset", asset_id)
    assert version == 1
    assert events[0].event_type == "AssetRegistered"


@pytest.mark.unit
def test_wire_equipment_exposes_remove_handler() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.remove_asset_alternate_identifier)
