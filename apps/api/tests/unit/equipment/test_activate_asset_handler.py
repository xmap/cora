"""Unit tests for the `activate_asset` application handler.

Exercises the load+fold+decide+append flow against InMemoryEventStore.
Mirrors Subject's `mount_subject` handler tests for the update-style
pattern.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.asset import (
    AssetCannotActivateError,
    AssetLifecycle,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import activate_asset, register_asset
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000007ca1")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000007ce1")
_ACTIVATE_EVENT_ID = UUID("01900000-0000-7000-8000-000000007ce2")
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
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _ACTIVATE_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _register_asset_helper(deps: Kernel) -> UUID:
    """Helper: register an asset and return its id."""
    handler = register_asset.bind(deps)
    return await handler(
        RegisterAsset(name="APS-2BM", tier=AssetTier.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    """Update-style handlers return None."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    result = await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_asset_activated_event() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", asset_id)
    assert version == 2  # AssetRegistered + AssetActivated
    assert len(events) == 2
    activated = events[1]
    assert activated.event_type == "AssetActivated"
    assert activated.payload == {
        "asset_id": str(asset_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert activated.event_id == _ACTIVATE_EVENT_ID
    assert activated.metadata == {"command": "ActivateAsset"}
    assert activated.causation_id is None


@pytest.mark.unit
async def test_handler_raises_asset_not_found_when_asset_does_not_exist() -> None:
    """The decider's AssetNotFoundError propagates unchanged through
    the handler — the route maps it to 404."""
    deps = _build_deps()
    handler = activate_asset.bind(deps)

    with pytest.raises(AssetNotFoundError):
        await handler(
            ActivateAsset(asset_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_activate_when_asset_already_active() -> None:
    """Strict semantics: re-activate raises rather than no-ops."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    handler = activate_asset.bind(deps)
    await handler(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(AssetCannotActivateError) as exc_info:
        await handler(
            ActivateAsset(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.current_lifecycle is AssetLifecycle.ACTIVE


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    """Authz check fires before the load+fold path runs."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    handler = activate_asset.bind(deny_deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            ActivateAsset(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError):
        await activate_asset.bind(deny_deps)(
            ActivateAsset(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Asset", asset_id)
    assert version == 1
    assert events[0].event_type == "AssetRegistered"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Asset", asset_id)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_includes_activate_asset() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.activate_asset)
    # earlier handlers still wired
    assert callable(handlers.register_asset)
    assert callable(handlers.define_family)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end check that causation_id survives the `with_tracing(bare)` chain in wire.py.

    No idempotency wrap on update-style commands.
    """
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    handlers = wire_equipment(deps)
    await handlers.activate_asset(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Asset", asset_id)
    assert events[1].causation_id == causation
