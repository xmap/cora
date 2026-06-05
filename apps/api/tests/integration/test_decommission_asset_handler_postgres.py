"""End-to-end integration test: decommission_asset handler against real Postgres.

Three scenarios cover the multi-source-state guard (Commissioned ->
Decommissioned, Active -> Decommissioned, and Maintenance ->
Decommissioned, the third source widened by the Maintenance state); all three are
exercised against real Postgres so the load+fold+decide+append
cycle is validated for every allowed source state with the real
event store.

Two additional scenarios cover the cross-aggregate guards added with
the longhand-handler lift: `AssetHasFixtureBindingError` fires when
the Asset still carries a Fixture back-reference, and
`AssetIsInstalledError` fires when the
`proj_equipment_asset_location` row points at a live Mount.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.assembly import SlotCardinality, SlotName, TemplateSlot
from cora.equipment.aggregates.asset import (
    AssetHasFixtureBindingError,
    AssetIsInstalledError,
    AssetLevel,
)
from cora.equipment.aggregates.fixture import SlotAssetBinding
from cora.equipment.features import (
    activate_asset,
    add_asset_family,
    attach_asset_to_fixture,
    decommission_asset,
    define_assembly,
    define_family,
    enter_asset_maintenance,
    install_asset,
    register_asset,
    register_fixture,
    register_frame,
    register_mount,
)
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.attach_asset_to_fixture import AttachAssetToFixture
from cora.equipment.features.decommission_asset import DecommissionAsset
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.enter_asset_maintenance import EnterAssetMaintenance
from cora.equipment.features.install_asset import InstallAsset
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_fixture import RegisterFixture
from cora.equipment.features.register_frame import RegisterFrame
from cora.equipment.features.register_mount import RegisterMount
from tests.integration._equipment_helpers import (
    drain_equipment_projections,
    placement,
    seed_installed_asset,
)
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-00000054ed00")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_decommission_asset_persists_event_from_commissioned_state(
    db_pool: asyncpg.Pool,
) -> None:
    """Commissioned -> Decommissioned (skipping activate). Operator-
    changed-mind path."""
    asset_id = UUID("01900000-0000-7000-8000-00000054ed01")
    register_event_id = UUID("01900000-0000-7000-8000-00000054ed0e")
    decommission_event_id = UUID("01900000-0000-7000-8000-00000054ed0f")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[asset_id, register_event_id, decommission_event_id],
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await decommission_asset.bind(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 2
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetDecommissioned",
    ]
    decommed = events[1]
    assert decommed.event_id == decommission_event_id
    assert decommed.metadata == {"command": "DecommissionAsset"}


@pytest.mark.integration
async def test_decommission_asset_persists_event_from_active_state(
    db_pool: asyncpg.Pool,
) -> None:
    """Full happy path: register + activate + decommission."""
    asset_id = UUID("01900000-0000-7000-8000-00000054ee01")
    register_event_id = UUID("01900000-0000-7000-8000-00000054ee0e")
    activate_event_id = UUID("01900000-0000-7000-8000-00000054ee0f")
    decommission_event_id = UUID("01900000-0000-7000-8000-00000054ee10")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[asset_id, register_event_id, activate_event_id, decommission_event_id],
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-32-ID", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await decommission_asset.bind(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetActivated",
        "AssetDecommissioned",
    ]
    decommed = events[2]
    assert decommed.event_id == decommission_event_id


@pytest.mark.integration
async def test_decommission_asset_persists_event_from_maintenance_state(
    db_pool: asyncpg.Pool,
) -> None:
    """5e widening: decommission accepts Maintenance as third source.
    Full path: register + activate + enter_asset_maintenance + decommission."""
    asset_id = UUID("01900000-0000-7000-8000-00000054ef01")
    register_event_id = UUID("01900000-0000-7000-8000-00000054ef0e")
    activate_event_id = UUID("01900000-0000-7000-8000-00000054ef0f")
    enter_event_id = UUID("01900000-0000-7000-8000-00000054ef10")
    decommission_event_id = UUID("01900000-0000-7000-8000-00000054ef11")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            asset_id,
            register_event_id,
            activate_event_id,
            enter_event_id,
            decommission_event_id,
        ],
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-7BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
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
    await decommission_asset.bind(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 4
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetActivated",
        "AssetMaintenanceEntered",
        "AssetDecommissioned",
    ]
    decommed = events[3]
    assert decommed.event_id == decommission_event_id


@pytest.mark.integration
async def test_decommission_asset_rejects_when_still_bound_to_fixture(
    db_pool: asyncpg.Pool,
) -> None:
    """Cross-aggregate guard (state-based): an Asset that still
    carries `fixture_id` cannot be decommissioned; operator must
    `detach_asset_from_fixture` first. Verifies the guard fires
    end-to-end against the real Asset stream fold.

    Setup chain (register_fixture requires every bound Asset to be
    currently installed): seed_installed_asset (Frame + Mount + Asset
    + activate + install) -> define_family + add_asset_family
    -> define_assembly + register_fixture -> attach_asset_to_fixture
    -> decommission_asset (rejected by AssetHasFixtureBindingError).
    """
    _, _, asset_id = await seed_installed_asset(
        db_pool, now=_NOW, slot_code="02-BM-decom-fix", asset_name="Cam-1"
    )

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(8)])
    family_id = await define_family.bind(deps)(
        DefineFamily(name="Camera", affordances=frozenset()),
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
            name="MCTOptics",
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

    with pytest.raises(AssetHasFixtureBindingError) as exc_info:
        await decommission_asset.bind(deps)(
            DecommissionAsset(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.fixture_id == fixture_id

    # The Asset stream is unchanged after the rejection (AssetActivated
    # comes from seed_installed_asset).
    events, _ = await deps.event_store.load("Asset", asset_id)
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetActivated",
        "AssetFamilyAdded",
        "AssetAttachedToFixture",
    ]


@pytest.mark.integration
async def test_decommission_asset_rejects_when_still_installed_in_mount(
    db_pool: asyncpg.Pool,
) -> None:
    """Cross-aggregate guard (projection-based): an Asset whose
    `proj_equipment_asset_location` row points at a live Mount cannot
    be decommissioned; operator must `uninstall_asset` first. Exercises
    the longhand handler's projection precondition end-to-end against
    real Postgres.
    """
    frame_id, mount_id, asset_id = uuid4(), uuid4(), uuid4()

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[frame_id, uuid4()])
    await register_frame.bind(deps)(
        RegisterFrame(name="frame-for-decom-check", parent_frame_id=None, placement=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[mount_id, uuid4()])
    await register_mount.bind(deps)(
        RegisterMount(
            slot_code="02-BM-A-K-decom",
            parent_mount_id=None,
            placement=placement(frame_id),
            drawing=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[asset_id, uuid4()])
    await register_asset.bind(deps)(
        RegisterAsset(name="specimen-decom", level=AssetLevel.DEVICE, parent_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    await install_asset.bind(deps)(
        InstallAsset(mount_id=mount_id, asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    with pytest.raises(AssetIsInstalledError) as exc_info:
        await decommission_asset.bind(deps)(
            DecommissionAsset(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.mount_id == mount_id

    events, _ = await deps.event_store.load("Asset", asset_id)
    assert [e.event_type for e in events] == ["AssetRegistered", "AssetActivated"]
