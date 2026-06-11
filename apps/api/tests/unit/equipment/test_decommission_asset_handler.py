"""Unit tests for the `decommission_asset` application handler.

First handler exercising Equipment's multi-source-state guard
(`Commissioned | Active -> Decommissioned`); both source states are
tested explicitly so a future change that only handles one is
caught. Mirrors Subject's `remove_subject` handler tests.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.asset import (
    AssetCannotDecommissionError,
    AssetLifecycle,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import activate_asset, decommission_asset, register_asset
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.decommission_asset import DecommissionAsset
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000007ca1")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000007ce1")
_ACTIVATE_EVENT_ID = UUID("01900000-0000-7000-8000-000000007ce2")
_DECOMMISSION_EVENT_ID = UUID("01900000-0000-7000-8000-000000007ce3")
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
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _ACTIVATE_EVENT_ID, _DECOMMISSION_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _register_asset_helper(deps: Kernel) -> UUID:
    """Helper: register an asset (Commissioned) and return its id."""
    return await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", tier=AssetTier.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _register_and_activate(deps: Kernel) -> UUID:
    """Helper: register + activate an asset (Active) and return its id."""
    asset_id = await _register_asset_helper(deps)
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

    result = await decommission_asset.bind(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_asset_decommissioned_event_from_commissioned() -> None:
    """Commissioned -> Decommissioned (skipping activate). Operator-
    changed-mind path."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    await decommission_asset.bind(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", asset_id)
    assert version == 2  # AssetRegistered + AssetDecommissioned
    assert [e.event_type for e in events] == ["AssetRegistered", "AssetDecommissioned"]
    decommed = events[1]
    # Skipping activate means the third id from FixedIdGenerator
    # (intended for AssetActivated) is consumed by AssetDecommissioned.
    assert decommed.event_id == _ACTIVATE_EVENT_ID
    assert decommed.metadata == {"command": "DecommissionAsset"}


@pytest.mark.unit
async def test_handler_appends_asset_decommissioned_event_from_active() -> None:
    """Full happy path: register + activate + decommission. The other
    valid source state for decommission."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_and_activate(deps)

    await decommission_asset.bind(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", asset_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetActivated",
        "AssetDecommissioned",
    ]
    decommed = events[2]
    assert decommed.event_id == _DECOMMISSION_EVENT_ID


@pytest.mark.unit
async def test_handler_raises_asset_not_found_when_asset_does_not_exist() -> None:
    deps = _build_deps()
    handler = decommission_asset.bind(deps)

    with pytest.raises(AssetNotFoundError):
        await handler(
            DecommissionAsset(asset_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_decommission_when_already_decommissioned() -> None:
    """Strict semantics: re-decommissioning raises."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    handler = decommission_asset.bind(deps)
    await handler(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(AssetCannotDecommissionError) as exc_info:
        await handler(
            DecommissionAsset(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.current_lifecycle is AssetLifecycle.DECOMMISSIONED


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    handler = decommission_asset.bind(deny_deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            DecommissionAsset(asset_id=asset_id),
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
        await decommission_asset.bind(deny_deps)(
            DecommissionAsset(asset_id=asset_id),
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

    await decommission_asset.bind(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Asset", asset_id)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_includes_decommission_asset() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.decommission_asset)
    assert callable(handlers.activate_asset)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    handlers = wire_equipment(deps)
    await handlers.decommission_asset(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Asset", asset_id)
    assert events[1].causation_id == causation
