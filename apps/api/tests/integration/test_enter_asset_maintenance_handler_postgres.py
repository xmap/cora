"""End-to-end integration test: enter_asset_maintenance handler against real Postgres.

Drives an asset through the full path register + activate +
enter_asset_maintenance against the real event store, then verifies the
final stream has the three expected event types in order with the
expected event_ids.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features import activate_asset, enter_asset_maintenance, register_asset
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.enter_asset_maintenance import EnterAssetMaintenance
from cora.equipment.features.register_asset import RegisterAsset
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-00000055ed00")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_enter_asset_maintenance_persists_event_from_active_state(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = UUID("01900000-0000-7000-8000-00000055ed01")
    register_event_id = UUID("01900000-0000-7000-8000-00000055ed0e")
    activate_event_id = UUID("01900000-0000-7000-8000-00000055ed0f")
    enter_event_id = UUID("01900000-0000-7000-8000-00000055ed10")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[asset_id, register_event_id, activate_event_id, enter_event_id],
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", tier=AssetTier.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await enter_asset_maintenance.bind(deps)(
        EnterAssetMaintenance(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetActivated",
        "AssetMaintenanceEntered",
    ]
    entered = events[2]
    assert entered.event_id == enter_event_id
    assert entered.metadata == {"command": "EnterAssetMaintenance"}
