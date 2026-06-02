"""Application-handler tests for `add_asset_alternate_identifier` slice.

Update-style handler via `make_asset_update_handler`; mirrors the
shape of `test_remove_asset_alternate_identifier_handler.py`.
Coverage:

  - happy path appends the right event with serialized payload
  - authorize-deny -> UnauthorizedError; no event appended
  - strict-not-idempotent: re-adding raises AlreadyPresent and
    nothing is appended
  - wire_equipment exposes the handler on the bundle
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.asset import (
    AlternateIdentifier,
    AlternateIdentifierKind,
    AssetAlternateIdentifierAlreadyPresentError,
    AssetLevel,
)
from cora.equipment.features import (
    add_asset_alternate_identifier,
    register_asset,
)
from cora.equipment.features.add_asset_alternate_identifier import (
    AddAssetAlternateIdentifier,
)
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-0000000a1e01")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-0000000a1e02")
_ADD_EVENT_ID_1 = UUID("01900000-0000-7000-8000-0000000a1e03")
_ADD_EVENT_ID_2 = UUID("01900000-0000-7000-8000-0000000a1e04")
_PARENT_ID = UUID("01900000-0000-7000-8000-0000000a1e05")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000a1e06")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000a1e07")

_IDENTIFIER = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="XYZ-001")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _ADD_EVENT_ID_1, _ADD_EVENT_ID_2],
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


@pytest.mark.unit
async def test_handler_appends_added_event_on_happy_path() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    await add_asset_alternate_identifier.bind(deps)(
        AddAssetAlternateIdentifier(asset_id=asset_id, alternate_identifier=_IDENTIFIER),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Asset", asset_id)
    added = events[1]
    assert added.event_type == "AssetAlternateIdentifierAdded"
    assert added.payload["alternate_identifier"] == {
        "kind": "SerialNumber",
        "value": "XYZ-001",
    }


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError):
        await add_asset_alternate_identifier.bind(deny_deps)(
            AddAssetAlternateIdentifier(asset_id=asset_id, alternate_identifier=_IDENTIFIER),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Asset", asset_id)
    # Only AssetRegistered survives; no Added appended on deny.
    assert version == 1
    assert events[0].event_type == "AssetRegistered"


@pytest.mark.unit
async def test_handler_raises_not_found_when_asset_missing() -> None:
    from cora.equipment.aggregates.asset import AssetNotFoundError

    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    missing_id = UUID("01900000-0000-7000-8000-0000000a1e99")

    with pytest.raises(AssetNotFoundError):
        await add_asset_alternate_identifier.bind(deps)(
            AddAssetAlternateIdentifier(asset_id=missing_id, alternate_identifier=_IDENTIFIER),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_already_present_on_second_add() -> None:
    """Strict-not-idempotent: re-adding the same identifier raises and
    appends no second event."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    await add_asset_alternate_identifier.bind(deps)(
        AddAssetAlternateIdentifier(asset_id=asset_id, alternate_identifier=_IDENTIFIER),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    with pytest.raises(AssetAlternateIdentifierAlreadyPresentError):
        await add_asset_alternate_identifier.bind(deps)(
            AddAssetAlternateIdentifier(asset_id=asset_id, alternate_identifier=_IDENTIFIER),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Asset", asset_id)
    # Register + one Added; the second Add raised before append.
    assert version == 2
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetAlternateIdentifierAdded",
    ]


@pytest.mark.unit
def test_wire_equipment_exposes_add_handler() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.add_asset_alternate_identifier)
