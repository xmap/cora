"""Unit tests for the `update_asset_settings` application handler.

Longhand handler (loads concurrent Family streams to
union settings_schemas). Tests cover happy path with one Family,
RFC 7396 merge accumulation, no-op on unchanged dict,
AssetNotFoundError, InvalidAssetSettingsError on schema violation,
auth deny, causation_id propagation, and wire smoke. Multi-Family
cross-schema scenarios are covered by
`tests/integration/test_update_asset_settings_handler_postgres.py`.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.asset import (
    AssetNotFoundError,
    AssetTier,
    InvalidAssetSettingsError,
)
from cora.equipment.features import (
    add_asset_family,
    define_family,
    register_asset,
    update_asset_settings,
    update_family_settings_schema,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.update_asset_settings import UpdateAssetSettings
from cora.equipment.features.update_family_settings_schema import (
    UpdateFamilySettingsSchema,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_CAP_ID = UUID("01900000-0000-7000-8000-00000000a501")
_CAP_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000a502")
_CAP_SCHEMA_EVENT_ID = UUID("01900000-0000-7000-8000-00000000a503")
_ASSET_ID = UUID("01900000-0000-7000-8000-00000000a504")
_ASSET_REGISTERED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000a505")
_CAP_ADDED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000a506")
_SETTINGS_EVENT_ID = UUID("01900000-0000-7000-8000-00000000a507")
_SETTINGS_EVENT_ID_2 = UUID("01900000-0000-7000-8000-00000000a508")
_PARENT_ID = UUID("01900000-0000-7000-8000-00000000a000")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _schema(min_val: int = 5) -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "minimum": min_val,
                "unit": {"system": "udunits", "code": "keV"},
            },
            "filter": {"type": "string"},
        },
    }


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock.

    Order matches the canonical setup: define_family,
    update_family_settings_schema, register_asset,
    add_asset_family, then two update_asset_settings event ids
    for tests that emit twice.
    """
    return _build_deps_shared(
        ids=[
            _CAP_ID,
            _CAP_DEFINED_EVENT_ID,
            _CAP_SCHEMA_EVENT_ID,
            _ASSET_ID,
            _ASSET_REGISTERED_EVENT_ID,
            _CAP_ADDED_EVENT_ID,
            _SETTINGS_EVENT_ID,
            _SETTINGS_EVENT_ID_2,
        ],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _setup_asset_with_schemaful_capability(deps: Kernel) -> UUID:
    """Define a Family with a settings_schema, register an Asset,
    and add the Family to it. Returns the Asset id."""
    cap_id = await define_family.bind(deps)(
        DefineFamily(name="Tomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_family_settings_schema.bind(deps)(
        UpdateFamilySettingsSchema(family_id=cap_id, settings_schema=_schema()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="Detector", tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return asset_id


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _setup_asset_with_schemaful_capability(deps)

    result = await update_asset_settings.bind(deps)(
        UpdateAssetSettings(asset_id=asset_id, settings_patch={"energy": 30}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_settings_updated_event_with_full_post_merge_dict() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _setup_asset_with_schemaful_capability(deps)

    await update_asset_settings.bind(deps)(
        UpdateAssetSettings(asset_id=asset_id, settings_patch={"energy": 30, "filter": "Cu"}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", asset_id)
    assert version == 3  # AssetRegistered + AssetFamilyAdded + AssetSettingsUpdated
    assert events[-1].event_type == "AssetSettingsUpdated"
    settings_event = events[-1]
    assert settings_event.event_id == _SETTINGS_EVENT_ID
    assert settings_event.metadata == {"command": "UpdateAssetSettings"}
    # Payload carries the FULL post-merge dict, not the patch (5g-c lock).
    assert settings_event.payload["settings"] == {"energy": 30, "filter": "Cu"}


@pytest.mark.unit
async def test_handler_merges_patches_across_two_calls() -> None:
    """RFC 7396: second patch keeps the first's keys and adds its own."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _setup_asset_with_schemaful_capability(deps)
    handler = update_asset_settings.bind(deps)

    await handler(
        UpdateAssetSettings(asset_id=asset_id, settings_patch={"energy": 30}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await handler(
        UpdateAssetSettings(asset_id=asset_id, settings_patch={"filter": "Cu"}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", asset_id)
    assert version == 4
    assert events[-2].payload["settings"] == {"energy": 30}
    assert events[-1].payload["settings"] == {"energy": 30, "filter": "Cu"}


@pytest.mark.unit
async def test_handler_no_op_on_unchanged_merge_does_not_append() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _setup_asset_with_schemaful_capability(deps)
    handler = update_asset_settings.bind(deps)

    await handler(
        UpdateAssetSettings(asset_id=asset_id, settings_patch={"energy": 30}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Re-applying the same key/value merges to an identical dict -> no event.
    await handler(
        UpdateAssetSettings(asset_id=asset_id, settings_patch={"energy": 30}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", asset_id)
    assert version == 3  # register + add_cap + 1 settings-update; second call no-op
    assert sum(1 for e in events if e.event_type == "AssetSettingsUpdated") == 1


@pytest.mark.unit
async def test_handler_raises_asset_not_found_when_asset_does_not_exist() -> None:
    deps = _build_deps()

    with pytest.raises(AssetNotFoundError):
        await update_asset_settings.bind(deps)(
            UpdateAssetSettings(asset_id=_ASSET_ID, settings_patch={"energy": 30}),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_settings_on_schema_violation() -> None:
    """Schema requires minimum=5; pass 1 and it fails validation."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _setup_asset_with_schemaful_capability(deps)

    with pytest.raises(InvalidAssetSettingsError):
        await update_asset_settings.bind(deps)(
            UpdateAssetSettings(asset_id=asset_id, settings_patch={"energy": 1}),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _setup_asset_with_schemaful_capability(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError) as exc_info:
        await update_asset_settings.bind(deny_deps)(
            UpdateAssetSettings(asset_id=asset_id, settings_patch={"energy": 30}),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _setup_asset_with_schemaful_capability(deps)

    await update_asset_settings.bind(deps)(
        UpdateAssetSettings(asset_id=asset_id, settings_patch={"energy": 30}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Asset", asset_id)
    assert events[-1].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_includes_update_asset_settings() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.update_asset_settings)
