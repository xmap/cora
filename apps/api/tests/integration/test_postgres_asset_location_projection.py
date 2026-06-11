"""End-to-end: install_asset / uninstall_asset slices land the
expected rows in proj_equipment_asset_location against real Postgres.

The Asset aggregate does NOT carry an installed_at MountId field per
the design anti-hook; the back-lookup ("where is Asset X right
now?") lives only in this projection. The pairing between
MountAssetInstalled / MountAssetUninstalled events and the projection
row is the load-bearing fitness for this entire branch's
install/uninstall slices.

Pins:
  - MountAssetInstalled  -> INSERT row (asset_id -> mount_id +
                            installed_at = event.occurred_at)
  - MountAssetUninstalled -> DELETE row by asset_id (no leftover)
  - Re-install of the same asset on a DIFFERENT mount upserts the
    row (the no-implicit-eviction anti-hook forces an uninstall
    between, but if for any reason the projection sees two installs
    in a row the UPSERT is replay-safe)
  - load_asset_location query helper returns the canonical mount_id
    for an installed asset, None for a vacated asset
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.activate_asset import bind as bind_activate_asset
from cora.equipment.features.install_asset import InstallAsset
from cora.equipment.features.install_asset import bind as bind_install_asset
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.equipment.features.register_frame import RegisterFrame
from cora.equipment.features.register_frame import bind as bind_register_frame
from cora.equipment.features.register_mount import RegisterMount
from cora.equipment.features.register_mount import bind as bind_register_mount
from cora.equipment.features.uninstall_asset import UninstallAsset
from cora.equipment.features.uninstall_asset import bind as bind_uninstall_asset
from cora.equipment.projections.asset_location import load_asset_location
from cora.infrastructure.kernel import Kernel
from tests.integration._equipment_helpers import drain_equipment_projections, placement
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 31, 9, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 31, 10, 30, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(pool: asyncpg.Pool, ids: list[UUID], now: datetime = _NOW) -> Kernel:
    return build_postgres_deps(pool, now=now, ids=ids)


async def _seed_frame_mount_and_asset(
    pool: asyncpg.Pool,
    *,
    frame_id: UUID,
    mount_id: UUID,
    asset_id: UUID,
    slot_code: str,
) -> None:
    """Register a Frame, a Mount referencing it, and an Asset; then
    activate the Asset (install_asset requires Active lifecycle).
    Drains projections so install_asset's projection preconditions
    (asset_lifecycle + asset_location back-lookup) succeed."""
    deps = _build_deps(pool, [frame_id, uuid4()])
    await bind_register_frame(deps)(
        RegisterFrame(
            name=f"frame-for-{slot_code}",
            parent_id=None,
            placement=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    deps = _build_deps(pool, [mount_id, uuid4()])
    await bind_register_mount(deps)(
        RegisterMount(
            slot_code=slot_code,
            parent_id=None,
            placement=placement(frame_id),
            drawing=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    deps = _build_deps(pool, [asset_id, uuid4()])
    await bind_register_asset(deps)(
        RegisterAsset(
            name=f"specimen-{slot_code}",
            tier=AssetTier.DEVICE,
            parent_id=uuid4(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    deps = _build_deps(pool, [uuid4()])
    await bind_activate_asset(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await drain_equipment_projections(pool)


@pytest.mark.integration
async def test_install_asset_inserts_row_with_mount_and_install_timestamp(
    db_pool: asyncpg.Pool,
) -> None:
    frame_id, mount_id, asset_id = uuid4(), uuid4(), uuid4()
    await _seed_frame_mount_and_asset(
        db_pool,
        frame_id=frame_id,
        mount_id=mount_id,
        asset_id=asset_id,
        slot_code="02-BM-A-K-01",
    )

    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_install_asset(deps)(
        InstallAsset(mount_id=mount_id, asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT mount_id, installed_at FROM proj_equipment_asset_location WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    assert row["mount_id"] == mount_id
    assert row["installed_at"] == _LATER

    located = await load_asset_location(db_pool, asset_id)
    assert located == mount_id


@pytest.mark.integration
async def test_uninstall_asset_deletes_row(db_pool: asyncpg.Pool) -> None:
    frame_id, mount_id, asset_id = uuid4(), uuid4(), uuid4()
    await _seed_frame_mount_and_asset(
        db_pool,
        frame_id=frame_id,
        mount_id=mount_id,
        asset_id=asset_id,
        slot_code="02-BM-A-K-02",
    )

    deps = _build_deps(db_pool, [uuid4()], now=_NOW)
    await bind_install_asset(deps)(
        InstallAsset(mount_id=mount_id, asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)
    assert await load_asset_location(db_pool, asset_id) == mount_id

    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_uninstall_asset(deps)(
        UninstallAsset(mount_id=mount_id, reason="end-of-beamtime pull"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT mount_id FROM proj_equipment_asset_location WHERE asset_id = $1",
            asset_id,
        )
    assert row is None
    assert await load_asset_location(db_pool, asset_id) is None


@pytest.mark.integration
async def test_uninstall_then_reinstall_on_same_mount_refreshes_timestamp(
    db_pool: asyncpg.Pool,
) -> None:
    """Production-realistic: specimen pulled for cleaning, re-mounted
    at the original slot. The row's mount_id is unchanged but the
    installed_at timestamp advances to the second install's
    occurred_at."""
    frame_id, mount_id, asset_id = uuid4(), uuid4(), uuid4()
    await _seed_frame_mount_and_asset(
        db_pool,
        frame_id=frame_id,
        mount_id=mount_id,
        asset_id=asset_id,
        slot_code="02-BM-A-K-recycle",
    )

    deps = _build_deps(db_pool, [uuid4()], now=_NOW)
    await bind_install_asset(deps)(
        InstallAsset(mount_id=mount_id, asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps = _build_deps(db_pool, [uuid4()], now=_NOW)
    await bind_uninstall_asset(deps)(
        UninstallAsset(mount_id=mount_id, reason="cleaning pull"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_install_asset(deps)(
        InstallAsset(mount_id=mount_id, asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT mount_id, installed_at FROM proj_equipment_asset_location WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    assert row["mount_id"] == mount_id
    assert row["installed_at"] == _LATER


@pytest.mark.integration
async def test_uninstall_then_reinstall_on_other_mount_relocates_row(
    db_pool: asyncpg.Pool,
) -> None:
    """The no-implicit-eviction anti-hook forces an uninstall between
    installs on different mounts. Verify the projection follows the
    relocation cleanly: row first points at mount_a, then is deleted,
    then is re-inserted at mount_b."""
    frame_id = uuid4()
    mount_a, mount_b, asset_id = uuid4(), uuid4(), uuid4()
    await _seed_frame_mount_and_asset(
        db_pool,
        frame_id=frame_id,
        mount_id=mount_a,
        asset_id=asset_id,
        slot_code="02-BM-A-K-03",
    )
    deps = _build_deps(db_pool, [mount_b, uuid4()])
    await bind_register_mount(deps)(
        RegisterMount(
            slot_code="02-BM-A-K-04",
            parent_id=None,
            placement=placement(frame_id),
            drawing=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    deps = _build_deps(db_pool, [uuid4()], now=_NOW)
    await bind_install_asset(deps)(
        InstallAsset(mount_id=mount_a, asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps = _build_deps(db_pool, [uuid4()], now=_NOW)
    await bind_uninstall_asset(deps)(
        UninstallAsset(mount_id=mount_a, reason="relocating to backup slot"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_install_asset(deps)(
        InstallAsset(mount_id=mount_b, asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT mount_id, installed_at FROM proj_equipment_asset_location WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    assert row["mount_id"] == mount_b
    assert row["installed_at"] == _LATER


@pytest.mark.integration
async def test_install_rejects_cross_mount_collision_via_back_lookup(
    db_pool: asyncpg.Pool,
) -> None:
    """Load-bearing fitness: an Asset installed in Mount A cannot be
    installed in Mount B without first being uninstalled from A. The
    handler reads the asset_location projection BEFORE deciding;
    AssetAlreadyInstalledElsewhereError carries the conflicting Mount
    so the operator can target an uninstall."""
    from cora.equipment.aggregates.mount import AssetAlreadyInstalledElsewhereError

    frame_id = uuid4()
    mount_a, mount_b, asset_id = uuid4(), uuid4(), uuid4()
    await _seed_frame_mount_and_asset(
        db_pool,
        frame_id=frame_id,
        mount_id=mount_a,
        asset_id=asset_id,
        slot_code="02-BM-X-K-uniq-a",
    )
    deps = _build_deps(db_pool, [mount_b, uuid4()])
    await bind_register_mount(deps)(
        RegisterMount(
            slot_code="02-BM-X-K-uniq-b",
            parent_id=None,
            placement=placement(frame_id),
            drawing=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    deps = _build_deps(db_pool, [uuid4()], now=_NOW)
    await bind_install_asset(deps)(
        InstallAsset(mount_id=mount_a, asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)
    assert await load_asset_location(db_pool, asset_id) == mount_a

    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    with pytest.raises(AssetAlreadyInstalledElsewhereError) as info:
        await bind_install_asset(deps)(
            InstallAsset(mount_id=mount_b, asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert info.value.asset_id == asset_id
    assert info.value.currently_at_mount_id == mount_a
    assert info.value.attempted_mount_id == mount_b

    # Asset still in Mount A; Mount B got no event.
    assert await load_asset_location(db_pool, asset_id) == mount_a
    stored, version = await deps.event_store.load("Mount", mount_b)
    assert [s.event_type for s in stored] == ["MountRegistered"]
    assert version == 1


@pytest.mark.integration
async def test_install_same_asset_in_same_mount_is_idempotent_no_op(
    db_pool: asyncpg.Pool,
) -> None:
    """PUT /mounts/{id}/installed-asset is idempotent per RFC 9110: a
    second call with the same asset_id against the same Mount returns
    success without emitting a duplicate event. Pin the end-to-end
    behavior; the decider returns [] and the handler appends no events."""
    frame_id, mount_id, asset_id = uuid4(), uuid4(), uuid4()
    await _seed_frame_mount_and_asset(
        db_pool,
        frame_id=frame_id,
        mount_id=mount_id,
        asset_id=asset_id,
        slot_code="02-BM-Y-K-idem",
    )

    deps = _build_deps(db_pool, [uuid4()], now=_NOW)
    await bind_install_asset(deps)(
        InstallAsset(mount_id=mount_id, asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_install_asset(deps)(
        InstallAsset(mount_id=mount_id, asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    # Mount stream got one MountAssetInstalled (the first call); the
    # second was a no-op.
    stored, _ = await deps.event_store.load("Mount", mount_id)
    install_events = [s for s in stored if s.event_type == "MountAssetInstalled"]
    assert len(install_events) == 1


@pytest.mark.integration
async def test_install_rejects_non_active_asset(
    db_pool: asyncpg.Pool,
) -> None:
    """Load-bearing fitness for Fix #2: an Asset not in Active
    lifecycle cannot be installed. Registers + decommissions an Asset,
    then attempts install; handler raises AssetNotInstallableError
    carrying the actual lifecycle."""
    from cora.equipment.aggregates.mount import AssetNotInstallableError
    from cora.equipment.features.decommission_asset import DecommissionAsset
    from cora.equipment.features.decommission_asset import bind as bind_decommission_asset

    frame_id, mount_id, asset_id = uuid4(), uuid4(), uuid4()
    await _seed_frame_mount_and_asset(
        db_pool,
        frame_id=frame_id,
        mount_id=mount_id,
        asset_id=asset_id,
        slot_code="02-BM-Z-K-lifecycle",
    )
    deps = _build_deps(db_pool, [uuid4()], now=_NOW)
    await bind_decommission_asset(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    with pytest.raises(AssetNotInstallableError) as info:
        await bind_install_asset(deps)(
            InstallAsset(mount_id=mount_id, asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert info.value.asset_id == asset_id
    assert info.value.current_lifecycle == "Decommissioned"
