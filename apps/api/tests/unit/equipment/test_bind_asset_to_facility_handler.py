"""Application-handler tests for `bind_asset_to_facility` slice (8C).

Covers:
  - happy path appends AssetFacilityCodeAssigned with serialized payload
  - authorize-deny -> UnauthorizedError; no event appended
  - unknown facility_code -> AssetFacilityNotFoundError; no event appended
  - set-once: re-binding raises AssetFacilityCodeAlreadyAssignedError
  - wire_equipment exposes the handler on the bundle
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.asset import (
    AssetFacilityCodeAlreadyAssignedError,
    AssetFacilityNotFoundError,
    AssetTier,
)
from cora.equipment.features import bind_asset_to_facility, register_asset
from cora.equipment.features.bind_asset_to_facility import BindAssetToFacility
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.adapters.in_memory_facility_lookup import InMemoryFacilityLookup
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-0000000b1f01")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-0000000b1f02")
_BIND_EVENT_ID = UUID("01900000-0000-7000-8000-0000000b1f03")
_PARENT_ID = UUID("01900000-0000-7000-8000-0000000b1f05")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000b1f06")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000b1f07")

_FACILITY_CODE = "cora"


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
    facility_lookup: InMemoryFacilityLookup | None = None,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _BIND_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
        facility_lookup=facility_lookup,
    )


async def _register_asset_helper(deps: Kernel, *, facility_code: str | None = None) -> UUID:
    if facility_code is not None:
        command = RegisterAsset(
            name="Beamline 2-BM",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code=facility_code,
        )
    else:
        command = RegisterAsset(
            name="Beamline 2-BM",
            tier=AssetTier.UNIT,
            parent_id=_PARENT_ID,
        )
    return await register_asset.bind(deps)(
        command,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_appends_assigned_event_on_happy_path() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    await bind_asset_to_facility.bind(deps)(
        BindAssetToFacility(asset_id=asset_id, facility_code=_FACILITY_CODE),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Asset", asset_id)
    assert len(events) == 2
    bound = events[1]
    assert bound.event_type == "AssetFacilityCodeAssigned"
    assert bound.payload["facility_code"] == _FACILITY_CODE
    assert bound.payload["asset_id"] == str(asset_id)
    assert UUID(bound.payload["assigned_by"]) == _PRINCIPAL_ID


@pytest.mark.unit
async def test_handler_raises_unauthorized_when_deny_and_appends_nothing() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError):
        await bind_asset_to_facility.bind(deny_deps)(
            BindAssetToFacility(asset_id=asset_id, facility_code=_FACILITY_CODE),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, _ = await store.load("Asset", asset_id)
    assert len(events) == 1  # only the genesis event


@pytest.mark.unit
async def test_handler_raises_facility_not_found_for_unknown_slug() -> None:
    store = InMemoryEventStore()
    facility_lookup = InMemoryFacilityLookup()
    # NOT seeding the lookup so any code resolves to None.
    deps = _build_deps(event_store=store, facility_lookup=facility_lookup)
    asset_id = await _register_asset_helper(deps)

    with pytest.raises(AssetFacilityNotFoundError):
        await bind_asset_to_facility.bind(deps)(
            BindAssetToFacility(asset_id=asset_id, facility_code="ghost"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, _ = await store.load("Asset", asset_id)
    assert len(events) == 1


@pytest.mark.unit
async def test_handler_set_once_rejects_rebind() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps, facility_code=_FACILITY_CODE)

    with pytest.raises(AssetFacilityCodeAlreadyAssignedError):
        await bind_asset_to_facility.bind(deps)(
            BindAssetToFacility(asset_id=asset_id, facility_code=_FACILITY_CODE),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, _ = await store.load("Asset", asset_id)
    assert len(events) == 1  # only register, no bind event


@pytest.mark.unit
def test_wire_equipment_exposes_bind_asset_to_facility_handler() -> None:
    """Pin that the wiring bundle surfaces the new handler so route /
    MCP-tool registration can resolve it."""
    deps = _build_deps()
    handlers: EquipmentHandlers = wire_equipment(deps)
    assert handlers.bind_asset_to_facility is not None
