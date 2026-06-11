"""End-to-end integration test: relocate_asset handler against real Postgres.

Two scenarios cover the hierarchy mutation against the real event
store:

  - relocate from Commissioned (the typical pre-service move)
  - relocate from Active (the in-service move; lifecycle preserved)

The first event in the codebase whose payload carries source AND
target state — both `from_parent_id` and `to_parent_id` are
asserted on the persisted payload to guarantee the round-trip is
correct under jsonb storage.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features import activate_asset, register_asset, relocate_asset
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.relocate_asset import RelocateAsset
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-00000054ef00")
_NEW_PARENT_ID = UUID("01900000-0000-7000-8000-00000054ef01")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_relocate_asset_persists_event_from_commissioned_state(
    db_pool: asyncpg.Pool,
) -> None:
    """Relocate while still Commissioned (not yet in service). Source
    parent comes from the loaded state, target from the command."""
    asset_id = UUID("01900000-0000-7000-8000-00000054ef02")
    register_event_id = UUID("01900000-0000-7000-8000-00000054ef0e")
    relocate_event_id = UUID("01900000-0000-7000-8000-00000054ef0f")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[asset_id, register_event_id, relocate_event_id],
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", tier=AssetTier.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await relocate_asset.bind(deps)(
        RelocateAsset(
            asset_id=asset_id,
            to_parent_id=_NEW_PARENT_ID,
            reason="commissioning move",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 2
    assert [e.event_type for e in events] == ["AssetRegistered", "AssetRelocated"]
    relocated = events[1]
    assert relocated.event_id == relocate_event_id
    assert relocated.metadata == {"command": "RelocateAsset"}
    assert relocated.payload["from_parent_id"] == str(_PARENT_ID)
    assert relocated.payload["to_parent_id"] == str(_NEW_PARENT_ID)
    assert relocated.payload["reason"] == "commissioning move"


@pytest.mark.integration
async def test_relocate_asset_persists_event_from_active_state(
    db_pool: asyncpg.Pool,
) -> None:
    """Relocate while Active (in-service hierarchy move). Lifecycle
    preserved on the event-stream side; the relocation itself does
    not change lifecycle."""
    asset_id = UUID("01900000-0000-7000-8000-00000054f001")
    register_event_id = UUID("01900000-0000-7000-8000-00000054f00e")
    activate_event_id = UUID("01900000-0000-7000-8000-00000054f00f")
    relocate_event_id = UUID("01900000-0000-7000-8000-00000054f010")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[asset_id, register_event_id, activate_event_id, relocate_event_id],
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-32-ID", tier=AssetTier.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await relocate_asset.bind(deps)(
        RelocateAsset(
            asset_id=asset_id,
            to_parent_id=_NEW_PARENT_ID,
            reason="moved while in service",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetActivated",
        "AssetRelocated",
    ]
    relocated = events[2]
    assert relocated.event_id == relocate_event_id
    assert relocated.payload["from_parent_id"] == str(_PARENT_ID)
    assert relocated.payload["to_parent_id"] == str(_NEW_PARENT_ID)
