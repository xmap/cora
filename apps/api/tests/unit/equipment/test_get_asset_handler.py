"""Unit tests for the `get_asset` query handler.

Mirrors `test_get_family_handler.py` / `test_get_subject_handler.py`.
Round-trips through the write side (register → get) verify that
fold-on-read correctly returns the registered Asset, and that
state mutations (activate, relocate) are reflected in the read.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.asset import (
    Asset,
    AssetLevel,
    AssetLifecycle,
    AssetName,
)
from cora.equipment.features import (
    activate_asset,
    get_asset,
    register_asset,
    relocate_asset,
)
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.get_asset import GetAsset
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.relocate_asset import RelocateAsset
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import DenyAllAuthorize as _DenyAllAuthorize
from tests.unit._helpers import RecordingAuthorize as _RecordingAuthorize
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000007fa1")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000007fe1")
_ACTIVATE_EVENT_ID = UUID("01900000-0000-7000-8000-000000007fe2")
_RELOCATE_EVENT_ID = UUID("01900000-0000-7000-8000-000000007fe3")
_PARENT_ID = UUID("01900000-0000-7000-8000-00000000a000")
_NEW_PARENT_ID = UUID("01900000-0000-7000-8000-00000000a001")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(event_store: InMemoryEventStore | None = None) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    return _build_deps_shared(
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _ACTIVATE_EVENT_ID, _RELOCATE_EVENT_ID],
        now=_NOW,
        event_store=event_store,
    )


@pytest.mark.unit
async def test_handler_returns_asset_for_known_id() -> None:
    """Round-trip: register + get."""
    deps = _build_deps()
    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_asset.bind(deps)
    asset = await handler(
        GetAsset(asset_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert asset == Asset(
        id=_NEW_ID,
        name=AssetName("APS-2BM"),
        level=AssetLevel.UNIT,
        parent_id=_PARENT_ID,
        lifecycle=AssetLifecycle.COMMISSIONED,
        commissioned_at=_NOW,
    )


@pytest.mark.unit
async def test_handler_returns_asset_with_null_parent_for_enterprise_root() -> None:
    """Pinned: Enterprise roots round-trip through fold-on-read with
    parent_id=None preserved (this is the only level where parent_id
    is null; payload null → Python None must survive the fold)."""
    deps = _build_deps()
    await register_asset.bind(deps)(
        RegisterAsset(name="ANL", level=AssetLevel.ENTERPRISE, parent_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_asset.bind(deps)
    asset = await handler(
        GetAsset(asset_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert asset is not None
    assert asset.level is AssetLevel.ENTERPRISE
    assert asset.parent_id is None


@pytest.mark.unit
async def test_handler_reflects_lifecycle_after_activate() -> None:
    """Pinned: get reads the FOLDED state, not just the genesis event.
    A change after register must surface in the next read."""
    deps = _build_deps()
    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_asset.bind(deps)
    asset = await handler(
        GetAsset(asset_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert asset is not None
    assert asset.lifecycle is AssetLifecycle.ACTIVE


@pytest.mark.unit
async def test_handler_reflects_parent_after_relocate() -> None:
    """Pinned: hierarchy mutations (5d) surface in the next get. The
    AssetRelocated evolver arm must be wired into the read path."""
    deps = _build_deps()
    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await relocate_asset.bind(deps)(
        RelocateAsset(
            asset_id=_NEW_ID,
            to_parent_id=_NEW_PARENT_ID,
            reason="moved",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_asset.bind(deps)
    asset = await handler(
        GetAsset(asset_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert asset is not None
    assert asset.parent_id == _NEW_PARENT_ID


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_id() -> None:
    deps = _build_deps()
    handler = get_asset.bind(deps)
    asset = await handler(
        GetAsset(asset_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert asset is None


@pytest.mark.unit
async def test_handler_authorizes_with_query_name_and_default_conduit() -> None:
    """Query handlers DO call authorize. Pinned because the
    eventual TrustAuthorize swap is mechanical per handler — the call
    site has to exist."""
    tracking = _RecordingAuthorize()
    deps = _build_deps_shared(
        ids=[_NEW_ID],
        now=_NOW,
        authz=tracking,
    )

    handler = get_asset.bind(deps)
    await handler(
        GetAsset(asset_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert tracking.calls == [(_PRINCIPAL_ID, "GetAsset", UUID(int=0), UUID(int=0))]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps_shared(
        ids=[_NEW_ID],
        now=_NOW,
        authz=_DenyAllAuthorize(),
    )

    handler = get_asset.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetAsset(asset_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
def test_wire_equipment_includes_get_asset() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.get_asset)
