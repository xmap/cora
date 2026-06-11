"""End-to-end `list_assets` handler against the real Postgres projection table.

Stresses the framework against:

  - Multi-aggregate BC (Equipment has Asset + Family; we project
    only Asset events here)
  - Hierarchy: parent_id column + parent_id filter
  - Lifecycle FSM with maintenance round-trip
  - Combined filters (tier + lifecycle + parent_id)
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.activate_asset import bind as bind_activate
from cora.equipment.features.decommission_asset import DecommissionAsset
from cora.equipment.features.decommission_asset import bind as bind_decommission
from cora.equipment.features.enter_asset_maintenance import EnterAssetMaintenance
from cora.equipment.features.enter_asset_maintenance import bind as bind_enter_asset_maintenance
from cora.equipment.features.exit_asset_maintenance import ExitAssetMaintenance
from cora.equipment.features.exit_asset_maintenance import bind as bind_exit
from cora.equipment.features.list_assets import ListAssets
from cora.equipment.features.list_assets import bind as bind_list
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register
from cora.equipment.features.relocate_asset import RelocateAsset
from cora.equipment.features.relocate_asset import bind as bind_relocate
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _register_root(db_pool: asyncpg.Pool) -> tuple[UUID, Kernel]:
    """Register a Unit-tier root asset and return (root_id, deps)."""
    root_id = uuid4()
    deps = _build_deps(db_pool, [root_id, uuid4()])
    await bind_register(deps)(
        RegisterAsset(
            name="Argonne",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return root_id, deps


@pytest.mark.integration
async def test_register_emits_commissioned_lifecycle(
    db_pool: asyncpg.Pool,
) -> None:
    """Sanity: register lands as Commissioned + correct tier."""
    root_id, _ = await _register_root(db_pool)
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT name, tier, lifecycle, parent_id "
            "FROM proj_equipment_asset_summary WHERE asset_id = $1",
            root_id,
        )
    assert row is not None
    assert row["name"] == "Argonne"
    assert row["tier"] == "Unit"
    assert row["lifecycle"] == "Commissioned"
    assert row["parent_id"] is None


@pytest.mark.integration
async def test_lifecycle_round_trip_active_maintenance_active(
    db_pool: asyncpg.Pool,
) -> None:
    """Activate -> Active; enter_asset_maintenance -> Maintenance; exit
    -> Active. Pin: AssetMaintenanceExited writes 'Active'
    just like AssetActivated does (the projection collapses both
    paths to the same target state)."""
    asset_id = uuid4()
    deps = _build_deps(db_pool, [asset_id, uuid4(), uuid4(), uuid4(), uuid4()])
    await bind_register(deps)(
        RegisterAsset(name="EigerDetector", tier=AssetTier.DEVICE, parent_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_activate(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)
    await _assert_lifecycle(db_pool, asset_id, "Active")

    await bind_enter_asset_maintenance(deps)(
        EnterAssetMaintenance(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)
    await _assert_lifecycle(db_pool, asset_id, "Maintenance")

    await bind_exit(deps)(
        ExitAssetMaintenance(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)
    await _assert_lifecycle(db_pool, asset_id, "Active")


@pytest.mark.integration
async def test_decommission_terminal(db_pool: asyncpg.Pool) -> None:
    asset_id = uuid4()
    deps = _build_deps(db_pool, [asset_id, uuid4(), uuid4()])
    await bind_register(deps)(
        RegisterAsset(name="OldDevice", tier=AssetTier.DEVICE, parent_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_decommission(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)
    await _assert_lifecycle(db_pool, asset_id, "Decommissioned")


@pytest.mark.integration
async def test_relocate_updates_parent_id(db_pool: asyncpg.Pool) -> None:
    """Hierarchy mutation: parent_id moves to_parent_id."""
    asset_id = uuid4()
    parent_a = uuid4()
    parent_b = uuid4()
    deps = _build_deps(db_pool, [asset_id, uuid4(), uuid4()])
    await bind_register(deps)(
        RegisterAsset(name="MovingDevice", tier=AssetTier.DEVICE, parent_id=parent_a),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_relocate(deps)(
        RelocateAsset(asset_id=asset_id, to_parent_id=parent_b, reason="moved"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT parent_id FROM proj_equipment_asset_summary WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    assert row["parent_id"] == parent_b


async def _assert_lifecycle(db_pool: asyncpg.Pool, asset_id: UUID, expected: str) -> None:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT lifecycle FROM proj_equipment_asset_summary WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    assert row["lifecycle"] == expected, f"Expected {expected}, got {row['lifecycle']}"


@pytest.mark.integration
async def test_filter_by_parent_returns_direct_children_only(
    db_pool: asyncpg.Pool,
) -> None:
    """Pin: parent_id filter returns DIRECT children of the given
    parent (not transitive descendants — the flat projection doesn't
    support transitive yet)."""
    site_id = uuid4()
    site_event_id = uuid4()
    # Three devices under the site, one under a different parent
    dev_a = uuid4()
    dev_b = uuid4()
    dev_c = uuid4()
    other_parent = uuid4()
    other_dev = uuid4()
    deps = _build_deps(
        db_pool,
        [
            site_id,
            site_event_id,
            dev_a,
            uuid4(),
            dev_b,
            uuid4(),
            dev_c,
            uuid4(),
            other_dev,
            uuid4(),
        ],
    )
    register = bind_register(deps)
    await register(
        RegisterAsset(name="Site", tier=AssetTier.UNIT, parent_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    for name in ("DevA", "DevB", "DevC"):
        await register(
            RegisterAsset(name=name, tier=AssetTier.DEVICE, parent_id=site_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    await register(
        RegisterAsset(name="Outsider", tier=AssetTier.DEVICE, parent_id=other_parent),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)
    handler = bind_list(deps)
    page = await handler(
        ListAssets(parent_id=site_id, limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert {item.asset_id for item in page.items} == {dev_a, dev_b, dev_c}


@pytest.mark.integration
async def test_combined_filters_tier_and_lifecycle(
    db_pool: asyncpg.Pool,
) -> None:
    """Compound filter: only Active Devices (no Units, no Commissioned
    Devices). Tests the multi-condition WHERE shape."""
    parent = uuid4()
    site_id = uuid4()
    active_dev = uuid4()
    commissioned_dev = uuid4()
    deps = _build_deps(
        db_pool,
        [
            site_id,
            uuid4(),
            active_dev,
            uuid4(),
            uuid4(),  # register + activate
            commissioned_dev,
            uuid4(),
        ],
    )
    await bind_register(deps)(
        RegisterAsset(name="Site", tier=AssetTier.UNIT, parent_id=parent),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_register(deps)(
        RegisterAsset(name="ActiveDev", tier=AssetTier.DEVICE, parent_id=site_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_activate(deps)(
        ActivateAsset(asset_id=active_dev),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_register(deps)(
        RegisterAsset(name="CommissionedDev", tier=AssetTier.DEVICE, parent_id=site_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)
    handler = bind_list(deps)
    page = await handler(
        ListAssets(tier="Device", lifecycle="Active", limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].asset_id == active_dev
    assert page.items[0].tier == "Device"
    assert page.items[0].lifecycle == "Active"


@pytest.mark.integration
async def test_cursor_walks_pages_with_filter(db_pool: asyncpg.Pool) -> None:
    """5 devices under one parent; cursor walks 3 pages with limit=2
    while filtering by parent_id. Covers cursor + filter combination."""
    site_id = uuid4()
    devices: list[UUID] = []
    fixed_ids: list[UUID] = [site_id, uuid4()]
    for _ in range(5):
        dev = uuid4()
        devices.append(dev)
        fixed_ids.extend([dev, uuid4()])
    deps = _build_deps(db_pool, fixed_ids)
    await bind_register(deps)(
        RegisterAsset(name="Site", tier=AssetTier.UNIT, parent_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    register = bind_register(deps)
    for i in range(5):
        await register(
            RegisterAsset(name=f"Dev{i:02d}", tier=AssetTier.DEVICE, parent_id=site_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    await _drain(db_pool)
    handler = bind_list(deps)

    page1 = await handler(
        ListAssets(parent_id=site_id, limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    page2 = await handler(
        ListAssets(parent_id=site_id, cursor=page1.next_cursor, limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    page3 = await handler(
        ListAssets(parent_id=site_id, cursor=page2.next_cursor, limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page1.items) == 2 and page1.next_cursor is not None
    assert len(page2.items) == 2 and page2.next_cursor is not None
    assert len(page3.items) == 1 and page3.next_cursor is None
    seen = {item.asset_id for p in (page1, page2, page3) for item in p.items}
    assert seen == set(devices)


@pytest.mark.integration
async def test_empty_table_returns_empty_page(db_pool: asyncpg.Pool) -> None:
    deps = _build_deps(db_pool, [])
    handler = bind_list(deps)
    page = await handler(
        ListAssets(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None
