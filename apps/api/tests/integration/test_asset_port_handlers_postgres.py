"""End-to-end integration test: add/remove_asset_port handlers
against real Postgres.

Single consolidated file for the two slices (mirror of the 5g-b
condition-handler integration consolidation).
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetTier, PortDirection
from cora.equipment.features import (
    add_asset_port,
    register_asset,
    remove_asset_port,
)
from cora.equipment.features.add_asset_port import AddAssetPort
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.remove_asset_port import RemoveAssetPort
from cora.infrastructure.kernel import Kernel
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000005d0099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000005d00aa")


def _deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


@pytest.mark.integration
async def test_add_then_remove_port_round_trip(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end: register Asset, add port, remove port. Persisted
    events carry the right shapes."""
    asset_id = UUID("01900000-0000-7000-8000-0000005d0001")
    ids = [
        asset_id,
        UUID("01900000-0000-7000-8000-0000005d0011"),  # register event
        UUID("01900000-0000-7000-8000-0000005d0012"),  # add port event
        UUID("01900000-0000-7000-8000-0000005d0013"),  # remove port event
    ]
    deps = _deps(db_pool, ids)

    await register_asset.bind(deps)(
        RegisterAsset(name="Detector-X", tier=AssetTier.DEVICE, parent_id=UUID(int=1)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_port.bind(deps)(
        AddAssetPort(
            asset_id=asset_id,
            port_name="trigger_in",
            direction=PortDirection.INPUT,
            signal_type="TTL",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await remove_asset_port.bind(deps)(
        RemoveAssetPort(asset_id=asset_id, port_name="trigger_in"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetPortAdded",
        "AssetPortRemoved",
    ]

    added = events[1]
    assert added.metadata == {"command": "AddAssetPort"}
    assert added.payload["port_name"] == "trigger_in"
    assert added.payload["direction"] == "Input"
    assert added.payload["signal_type"] == "TTL"

    removed = events[2]
    assert removed.metadata == {"command": "RemoveAssetPort"}
    assert removed.payload["port_name"] == "trigger_in"
