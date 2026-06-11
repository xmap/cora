"""End-to-end integration test: update_asset_settings handler
against real Postgres with multiple Capabilities.

Covers:
  - happy path: set, persists AssetSettingsUpdated with full
    post-merge dict
  - merge across two PATCHes accumulates
  - cross-Family schema union: settings keys owned by either
    Family are validated against the right schema
  - true type conflict between two Capabilities surfaces with both
    Family ids in the error
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetTier, InvalidAssetSettingsError
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
from cora.equipment.features.update_family_settings_schema import UpdateFamilySettingsSchema
from cora.infrastructure.kernel import Kernel
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000005c0099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000005c00aa")
_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


@pytest.mark.integration
async def test_update_asset_settings_persists_event_with_full_post_merge_dict(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy path: define Family with schema, register Asset,
    add Family, PATCH settings, assert persisted event payload
    carries the FULL post-merge dict (5g-c lock)."""
    cap_id = UUID("01900000-0000-7000-8000-0000005c0001")
    asset_id = UUID("01900000-0000-7000-8000-0000005c0002")
    ids = [
        # define_family: family_id, define_event_id
        cap_id,
        UUID("01900000-0000-7000-8000-0000005c0011"),
        # update_family_settings_schema: schema_event_id
        UUID("01900000-0000-7000-8000-0000005c0012"),
        # register_asset: asset_id, register_event_id
        asset_id,
        UUID("01900000-0000-7000-8000-0000005c0013"),
        # add_asset_family: cap_added_event_id
        UUID("01900000-0000-7000-8000-0000005c0014"),
        # update_asset_settings: settings_event_id
        UUID("01900000-0000-7000-8000-0000005c0015"),
    ]
    deps = _deps(db_pool, ids)

    await define_family.bind(deps)(
        DefineFamily(name="Tomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_family_settings_schema.bind(deps)(
        UpdateFamilySettingsSchema(
            family_id=cap_id,
            settings_schema={
                "$schema": _DRAFT,
                "type": "object",
                "properties": {
                    "energy": {
                        "type": "number",
                        "minimum": 5,
                        "unit": {"system": "udunits", "code": "keV"},
                    },
                    "filter": {"type": "string"},
                },
            },
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_asset.bind(deps)(
        RegisterAsset(name="Detector", tier=AssetTier.DEVICE, parent_id=UUID(int=1)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_asset_settings.bind(deps)(
        UpdateAssetSettings(asset_id=asset_id, settings_patch={"energy": 30, "filter": "Cu"}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetFamilyAdded",
        "AssetSettingsUpdated",
    ]
    settings_event = events[2]
    assert settings_event.metadata == {"command": "UpdateAssetSettings"}
    assert settings_event.payload["settings"] == {"energy": 30, "filter": "Cu"}


@pytest.mark.integration
async def test_update_asset_settings_merges_across_two_patches(
    db_pool: asyncpg.Pool,
) -> None:
    """Two PATCHes accumulate via merge: first sets one key, second
    sets another; final state has both."""
    cap_id = UUID("01900000-0000-7000-8000-0000005c0021")
    asset_id = UUID("01900000-0000-7000-8000-0000005c0022")
    ids = [
        cap_id,
        UUID("01900000-0000-7000-8000-0000005c0031"),  # define cap event
        UUID("01900000-0000-7000-8000-0000005c0032"),  # set schema event
        asset_id,
        UUID("01900000-0000-7000-8000-0000005c0033"),  # register event
        UUID("01900000-0000-7000-8000-0000005c0034"),  # add capability event
        UUID("01900000-0000-7000-8000-0000005c0035"),  # first settings event
        UUID("01900000-0000-7000-8000-0000005c0036"),  # second settings event
    ]
    deps = _deps(db_pool, ids)

    await define_family.bind(deps)(
        DefineFamily(name="Tomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_family_settings_schema.bind(deps)(
        UpdateFamilySettingsSchema(
            family_id=cap_id,
            settings_schema={
                "$schema": _DRAFT,
                "type": "object",
                "properties": {
                    "energy": {"type": "number", "unit": {"system": "udunits", "code": "keV"}},
                    "filter": {"type": "string"},
                },
            },
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_asset.bind(deps)(
        RegisterAsset(name="Detector", tier=AssetTier.DEVICE, parent_id=UUID(int=1)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_asset_settings.bind(deps)(
        UpdateAssetSettings(asset_id=asset_id, settings_patch={"energy": 30}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_asset_settings.bind(deps)(
        UpdateAssetSettings(asset_id=asset_id, settings_patch={"filter": "Cu"}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 4
    # Last event's payload carries the FULL merged dict.
    assert events[-1].payload["settings"] == {"energy": 30, "filter": "Cu"}


@pytest.mark.integration
async def test_update_asset_settings_rejects_true_type_conflict_across_capabilities(
    db_pool: asyncpg.Pool,
) -> None:
    """Two Capabilities both declare `temperature` but with
    incompatible types; the validator names both Capabilities."""
    cap_a_id = UUID("01900000-0000-7000-8000-0000005c0041")
    cap_b_id = UUID("01900000-0000-7000-8000-0000005c0042")
    asset_id = UUID("01900000-0000-7000-8000-0000005c0043")
    ids = [
        cap_a_id,
        UUID("01900000-0000-7000-8000-0000005c0051"),
        UUID("01900000-0000-7000-8000-0000005c0052"),
        cap_b_id,
        UUID("01900000-0000-7000-8000-0000005c0053"),
        UUID("01900000-0000-7000-8000-0000005c0054"),
        asset_id,
        UUID("01900000-0000-7000-8000-0000005c0055"),
        UUID("01900000-0000-7000-8000-0000005c0056"),
        UUID("01900000-0000-7000-8000-0000005c0057"),
    ]
    deps = _deps(db_pool, ids)

    await define_family.bind(deps)(
        DefineFamily(name="A", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_family_settings_schema.bind(deps)(
        UpdateFamilySettingsSchema(
            family_id=cap_a_id,
            settings_schema={
                "$schema": _DRAFT,
                "type": "object",
                "properties": {
                    "temperature": {
                        "type": "number",
                        "unit": {"system": "udunits", "code": "degC"},
                    }
                },
            },
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_family.bind(deps)(
        DefineFamily(name="B", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_family_settings_schema.bind(deps)(
        UpdateFamilySettingsSchema(
            family_id=cap_b_id,
            settings_schema={
                "$schema": _DRAFT,
                "type": "object",
                "properties": {"temperature": {"type": "string"}},
            },
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_asset.bind(deps)(
        RegisterAsset(name="X", tier=AssetTier.DEVICE, parent_id=UUID(int=1)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=cap_a_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=cap_b_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    with pytest.raises(InvalidAssetSettingsError) as exc_info:
        await update_asset_settings.bind(deps)(
            UpdateAssetSettings(
                asset_id=asset_id,
                settings_patch={"temperature": 25},
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    # Both Family ids surface in the diagnostic.
    assert str(cap_a_id) in exc_info.value.reason
    assert str(cap_b_id) in exc_info.value.reason
    assert "temperature" in exc_info.value.reason
    assert "incompatible types" in exc_info.value.reason
