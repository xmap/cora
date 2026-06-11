"""End-to-end integration test: degrade / fault / restore handlers
against real Postgres.

Covers the three condition-transition slices in one
file (mirror of the relocate test shape, but consolidated since the
three slices have identical handler shape).

Scenarios:
  - degrade an Active asset (typical path; condition flips Nominal -> Degraded)
  - fault a Degraded asset (worsening; Degraded -> Faulted)
  - restore a Faulted asset (full repair; Faulted -> Nominal)
  - condition transition preserved across a subsequent lifecycle event
    (degrade then enter_asset_maintenance: condition stays Degraded)
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features import (
    activate_asset,
    degrade_asset,
    enter_asset_maintenance,
    fault_asset,
    register_asset,
    restore_asset,
)
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.degrade_asset import DegradeAsset
from cora.equipment.features.enter_asset_maintenance import EnterAssetMaintenance
from cora.equipment.features.fault_asset import FaultAsset
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.restore_asset import RestoreAsset
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-0000005f0b00")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000005f0b99")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000005f0baa")


@pytest.mark.integration
async def test_degrade_asset_persists_event_with_reason(
    db_pool: asyncpg.Pool,
) -> None:
    """Active asset degraded; reason captured on the event payload."""
    asset_id = UUID("01900000-0000-7000-8000-0000005f0b01")
    register_event_id = UUID("01900000-0000-7000-8000-0000005f0b1e")
    activate_event_id = UUID("01900000-0000-7000-8000-0000005f0b1f")
    degrade_event_id = UUID("01900000-0000-7000-8000-0000005f0b20")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[asset_id, register_event_id, activate_event_id, degrade_event_id],
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="Detector-FLIR-Oryx-001", tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await degrade_asset.bind(deps)(
        DegradeAsset(asset_id=asset_id, reason="hot pixel detected at (12, 42)"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetActivated",
        "AssetDegraded",
    ]
    degraded = events[2]
    assert degraded.event_id == degrade_event_id
    assert degraded.metadata == {"command": "DegradeAsset"}
    assert degraded.payload["asset_id"] == str(asset_id)
    assert degraded.payload["reason"] == "hot pixel detected at (12, 42)"


@pytest.mark.integration
async def test_fault_then_restore_round_trip(
    db_pool: asyncpg.Pool,
) -> None:
    """Fault an asset, then restore — both events persist, and the
    final fold yields condition=Nominal."""
    asset_id = UUID("01900000-0000-7000-8000-0000005f0b30")
    ids = [
        asset_id,
        UUID("01900000-0000-7000-8000-0000005f0b31"),  # register event
        UUID("01900000-0000-7000-8000-0000005f0b32"),  # activate event
        UUID("01900000-0000-7000-8000-0000005f0b33"),  # fault event
        UUID("01900000-0000-7000-8000-0000005f0b34"),  # restore event
    ]

    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)

    await register_asset.bind(deps)(
        RegisterAsset(name="Pump-XDS35i", tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await fault_asset.bind(deps)(
        FaultAsset(asset_id=asset_id, reason="vacuum pump seized"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await restore_asset.bind(deps)(
        RestoreAsset(asset_id=asset_id, reason="rebuilt and recommissioned"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 4
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetActivated",
        "AssetFaulted",
        "AssetRestored",
    ]
    assert events[2].payload["reason"] == "vacuum pump seized"
    assert events[3].payload["reason"] == "rebuilt and recommissioned"


@pytest.mark.integration
async def test_no_op_when_already_in_target_condition(
    db_pool: asyncpg.Pool,
) -> None:
    """Re-degrading an already-Degraded asset emits NO event (no-op-
    on-unchanged precedent). Pin against the real event store: stream
    version unchanged after the second call."""
    asset_id = UUID("01900000-0000-7000-8000-0000005f0b40")
    ids = [
        asset_id,
        UUID("01900000-0000-7000-8000-0000005f0b41"),  # register event
        UUID("01900000-0000-7000-8000-0000005f0b42"),  # activate event
        UUID("01900000-0000-7000-8000-0000005f0b43"),  # first degrade event
    ]

    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)

    await register_asset.bind(deps)(
        RegisterAsset(name="Stage-A3200", tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await degrade_asset.bind(deps)(
        DegradeAsset(asset_id=asset_id, reason="first reason"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Second call with a DIFFERENT reason — still a no-op because
    # condition is already Degraded.
    await degrade_asset.bind(deps)(
        DegradeAsset(asset_id=asset_id, reason="second reason should not be persisted"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 3
    assert len(events) == 3
    # Only the FIRST reason was persisted (the second call no-op'd).
    assert events[2].payload["reason"] == "first reason"


@pytest.mark.integration
async def test_condition_preserved_across_lifecycle_transition(
    db_pool: asyncpg.Pool,
) -> None:
    """Degrade an Active asset, then enter maintenance. The fold-
    side state must keep condition=Degraded after the lifecycle event
    (regression guard for the evolver-preservation invariant against
    the real event store)."""
    asset_id = UUID("01900000-0000-7000-8000-0000005f0b50")
    ids = [
        asset_id,
        UUID("01900000-0000-7000-8000-0000005f0b51"),
        UUID("01900000-0000-7000-8000-0000005f0b52"),
        UUID("01900000-0000-7000-8000-0000005f0b53"),
        UUID("01900000-0000-7000-8000-0000005f0b54"),
    ]

    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)

    await register_asset.bind(deps)(
        RegisterAsset(name="Pump-Y", tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await degrade_asset.bind(deps)(
        DegradeAsset(asset_id=asset_id, reason="check"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await enter_asset_maintenance.bind(deps)(
        EnterAssetMaintenance(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 4
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetActivated",
        "AssetDegraded",
        "AssetMaintenanceEntered",
    ]
