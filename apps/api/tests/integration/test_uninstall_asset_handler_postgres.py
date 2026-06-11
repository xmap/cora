# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

"""End-to-end integration test: uninstall_asset handler against real Postgres.

Two scenarios:
  - Happy path: a non-fixture-bound installed Asset uninstalls cleanly
    (`MountAssetUninstalled` lands and the `proj_equipment_asset_location`
    row goes away).
  - Cross-aggregate guard: an installed Asset that still carries a
    Fixture back-reference cannot be uninstalled
    (`MountHasFixtureBoundAssetError`); the Mount stream stays
    unchanged after the rejection.

The guard is the load-bearing pin from slice 2 of the alignment plan:
without it, popping a fixture-bound specimen off its Mount silently
strands the Fixture binding.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.assembly import SlotCardinality, SlotName, TemplateSlot
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.fixture import SlotAssetBinding
from cora.equipment.aggregates.mount import MountHasFixtureBoundAssetError
from cora.equipment.features import (
    activate_asset,
    add_asset_family,
    attach_asset_to_fixture,
    define_assembly,
    define_family,
    install_asset,
    register_asset,
    register_fixture,
    register_frame,
    register_mount,
    uninstall_asset,
)
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.attach_asset_to_fixture import AttachAssetToFixture
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.install_asset import InstallAsset
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_fixture import RegisterFixture
from cora.equipment.features.register_frame import RegisterFrame
from cora.equipment.features.register_mount import RegisterMount
from cora.equipment.features.uninstall_asset import UninstallAsset
from tests.integration._equipment_helpers import drain_equipment_projections, placement
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 4, 9, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_active_asset_in_mount(
    pool: asyncpg.Pool,
    *,
    slot_code: str,
) -> tuple[UUID, UUID, UUID]:
    """Register Frame + Mount + Active Asset, then install the Asset.
    Returns (frame_id, mount_id, asset_id). Drains projections so the
    happy and guard paths can rely on a populated asset_location row.
    """
    frame_id, mount_id, asset_id = uuid4(), uuid4(), uuid4()

    deps = build_postgres_deps(pool, now=_NOW, ids=[frame_id, uuid4()])
    await register_frame.bind(deps)(
        RegisterFrame(name=f"frame-{slot_code}", parent_id=None, placement=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    deps = build_postgres_deps(pool, now=_NOW, ids=[mount_id, uuid4()])
    await register_mount.bind(deps)(
        RegisterMount(
            slot_code=slot_code,
            parent_id=None,
            placement=placement(frame_id),
            drawing=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    deps = build_postgres_deps(pool, now=_NOW, ids=[asset_id, uuid4()])
    await register_asset.bind(deps)(
        RegisterAsset(name=f"specimen-{slot_code}", tier=AssetTier.DEVICE, parent_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps = build_postgres_deps(pool, now=_NOW, ids=[uuid4()])
    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(pool)

    deps = build_postgres_deps(pool, now=_NOW, ids=[uuid4()])
    await install_asset.bind(deps)(
        InstallAsset(mount_id=mount_id, asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(pool)

    return frame_id, mount_id, asset_id


@pytest.mark.integration
async def test_uninstall_asset_happy_path_emits_event_and_clears_location(
    db_pool: asyncpg.Pool,
) -> None:
    """Without a Fixture binding, uninstall_asset emits MountAssetUninstalled
    and proj_equipment_asset_location row is removed by the projection."""
    _, mount_id, asset_id = await _seed_active_asset_in_mount(
        db_pool, slot_code="02-BM-A-K-uninst-1"
    )

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    await uninstall_asset.bind(deps)(
        UninstallAsset(mount_id=mount_id, reason="end-of-run"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    events, _ = await deps.event_store.load("Mount", mount_id)
    assert [e.event_type for e in events] == [
        "MountRegistered",
        "MountAssetInstalled",
        "MountAssetUninstalled",
    ]
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT mount_id FROM proj_equipment_asset_location WHERE asset_id = $1",
            asset_id,
        )
    assert row is None


@pytest.mark.integration
async def test_uninstall_asset_rejects_when_installed_asset_is_fixture_bound(
    db_pool: asyncpg.Pool,
) -> None:
    """Cross-aggregate guard: when the installed Asset carries a
    Fixture back-reference, uninstall_asset rejects with the new
    MountHasFixtureBoundAssetError naming both Asset and Fixture.
    The Mount stream is unchanged after the rejection.
    """
    _, mount_id, asset_id = await _seed_active_asset_in_mount(
        db_pool, slot_code="02-BM-A-K-uninst-2"
    )

    # Build a Fixture binding the installed Asset and attach it.
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(8)])
    family_id = await define_family.bind(deps)(
        DefineFamily(name="CameraUninstall", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assembly_id = await define_assembly.bind(deps)(
        DefineAssembly(
            name="UninstallRig",
            presents_as_family_id=family_id,
            required_slots=frozenset(
                {
                    TemplateSlot(
                        slot_name=SlotName("camera"),
                        required_family_ids=frozenset({family_id}),
                        cardinality=SlotCardinality.EXACTLY_1,
                    )
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    fixture_id = await register_fixture.bind(deps)(
        RegisterFixture(
            assembly_id=assembly_id,
            slot_asset_bindings=frozenset(
                {SlotAssetBinding(slot_name="camera", asset_id=asset_id)}
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await attach_asset_to_fixture.bind(deps)(
        AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    with pytest.raises(MountHasFixtureBoundAssetError) as exc_info:
        await uninstall_asset.bind(deps)(
            UninstallAsset(mount_id=mount_id, reason="should-fail"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.mount_id == mount_id
    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.fixture_id == fixture_id

    events, _ = await deps.event_store.load("Mount", mount_id)
    assert [e.event_type for e in events] == [
        "MountRegistered",
        "MountAssetInstalled",
    ]
