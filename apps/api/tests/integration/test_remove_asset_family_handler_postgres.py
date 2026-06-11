"""End-to-end integration test: remove_asset_family against real Postgres.

Round-trip: register + add + remove leaves the asset back at empty
capabilities (verified via load_asset fold-on-read).
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetTier, load_asset
from cora.equipment.features import (
    add_asset_family,
    register_asset,
    remove_asset_family,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.remove_asset_family import RemoveAssetFamily
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-00000056fb00")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_remove_asset_family_persists_event_and_drops_from_fold(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = UUID("01900000-0000-7000-8000-00000056fb01")
    register_event_id = UUID("01900000-0000-7000-8000-00000056fb0e")
    add_event_id = UUID("01900000-0000-7000-8000-00000056fb0f")
    remove_event_id = UUID("01900000-0000-7000-8000-00000056fb10")
    cap1 = UUID("01900000-0000-7000-8000-000000000222")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[asset_id, register_event_id, add_event_id, remove_event_id],
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", tier=AssetTier.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=cap1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await remove_asset_family.bind(deps)(
        RemoveAssetFamily(asset_id=asset_id, family_id=cap1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetFamilyAdded",
        "AssetFamilyRemoved",
    ]
    removed = events[2]
    assert removed.event_id == remove_event_id
    assert removed.metadata == {"command": "RemoveAssetFamily"}

    # Fold-on-read reconstructs the empty frozenset.
    state = await load_asset(deps.event_store, asset_id)
    assert state is not None
    assert state.family_ids == frozenset()
