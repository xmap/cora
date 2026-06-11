"""Unit tests for the `relocate_asset` application handler.

Mirror of the `decommission_asset` handler tests but exercising the
hierarchy-mutation slice. Three things differ structurally:

  - the appended event payload carries BOTH `from_parent_id` and
    `to_parent_id` (first event in the codebase to do so)
  - guard surface is broader (Enterprise / Decommissioned / self-loop /
    no-op) — exercised lightly here; the full matrix lives in the
    decider tests
  - lifecycle is preserved across the event, NOT changed (smoke-tested
    via fold + read on a wired path)
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.asset import (
    AssetCannotRelocateError,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import register_asset, relocate_asset
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.relocate_asset import RelocateAsset
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000007ca1")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000007ce1")
_RELOCATE_EVENT_ID = UUID("01900000-0000-7000-8000-000000007ce2")
_PARENT_ID = UUID("01900000-0000-7000-8000-00000000a000")
_NEW_PARENT_ID = UUID("01900000-0000-7000-8000-00000000a001")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    return _build_deps_shared(
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _RELOCATE_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _register_asset_helper(deps: Kernel) -> UUID:
    return await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", tier=AssetTier.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    result = await relocate_asset.bind(deps)(
        RelocateAsset(
            asset_id=asset_id,
            to_parent_id=_NEW_PARENT_ID,
            reason="site reorganization",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_asset_relocated_event_with_both_parents() -> None:
    """Pinned: payload must carry from_parent_id (read from prior state)
    AND to_parent_id (from command). First event in the codebase with
    both — easy to drop the from_ side in a refactor."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    await relocate_asset.bind(deps)(
        RelocateAsset(
            asset_id=asset_id,
            to_parent_id=_NEW_PARENT_ID,
            reason="site reorganization",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", asset_id)
    assert version == 2  # AssetRegistered + AssetRelocated
    assert [e.event_type for e in events] == ["AssetRegistered", "AssetRelocated"]
    relocated = events[1]
    assert relocated.event_id == _RELOCATE_EVENT_ID
    assert relocated.metadata == {"command": "RelocateAsset"}
    assert relocated.payload["from_parent_id"] == str(_PARENT_ID)
    assert relocated.payload["to_parent_id"] == str(_NEW_PARENT_ID)
    assert relocated.payload["reason"] == "site reorganization"


@pytest.mark.unit
async def test_handler_raises_asset_not_found_when_asset_does_not_exist() -> None:
    deps = _build_deps()
    handler = relocate_asset.bind(deps)

    with pytest.raises(AssetNotFoundError):
        await handler(
            RelocateAsset(
                asset_id=uuid4(),
                to_parent_id=_NEW_PARENT_ID,
                reason="moved",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_relocate_for_no_op() -> None:
    """Smoke test of one of the four CannotRelocate guards via the
    handler path (full matrix in the decider tests). No-op picked
    because it doesn't require special setup state."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    handler = relocate_asset.bind(deps)
    with pytest.raises(AssetCannotRelocateError) as exc_info:
        await handler(
            RelocateAsset(
                asset_id=asset_id,
                to_parent_id=_PARENT_ID,  # same as current parent
                reason="moved",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.asset_id == asset_id
    assert "no-op" in exc_info.value.reason


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    handler = relocate_asset.bind(deny_deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            RelocateAsset(
                asset_id=asset_id,
                to_parent_id=_NEW_PARENT_ID,
                reason="moved",
            ),
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
        await relocate_asset.bind(deny_deps)(
            RelocateAsset(
                asset_id=asset_id,
                to_parent_id=_NEW_PARENT_ID,
                reason="moved",
            ),
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

    await relocate_asset.bind(deps)(
        RelocateAsset(
            asset_id=asset_id,
            to_parent_id=_NEW_PARENT_ID,
            reason="moved",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Asset", asset_id)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_includes_relocate_asset() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.relocate_asset)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    handlers = wire_equipment(deps)
    await handlers.relocate_asset(
        RelocateAsset(
            asset_id=asset_id,
            to_parent_id=_NEW_PARENT_ID,
            reason="moved",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Asset", asset_id)
    assert events[1].causation_id == causation
