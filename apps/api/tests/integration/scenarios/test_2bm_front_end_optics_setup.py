"""Front-end optics registration at APS 2-BM (energy-work foundation).

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment

Registers the 2-BM front-end / beam-conditioning optics as CORA Assets so
the later energy-change work has real devices to coordinate. The five
optics (Mirror, Monochromator, two Slit instances, Filter) all sit on the
a-station OMS VME58 crate, so each carries a `controller_id` back-reference
to the `FrontEndDrive` MotionController, which until now shipped with no
modelled driven stages.

This is the optics-foundation step of the energy program. The
individual motor axes (mirror Y/pitch, mono crystal Z, slit gaps) and the
per-energy positioning are deferred to the energy-mapping stage; here each
optic is one device-level Asset, mirroring how the physical Hexapod was
registered before its DoF facets. The controller-plus-driven-stage shape
mirrors test_2bm_motor_homing.py.

## Asset stack

```
2-BM (Unit)
+-- FrontEndDrive (Device)        Family: MotionController   a-station OMS VME58
+-- MirrorTable (Device)          Family: Table              front-end support table
|   +-- Mirror (Device)           Family: Mirror             (controller_id -> FrontEndDrive)
+-- Monochromator (Device)        Family: Monochromator      (controller_id -> FrontEndDrive)
+-- ConditioningSlit (Device)     Family: Slit               (controller_id -> FrontEndDrive)
+-- SampleSlit (Device)           Family: Slit               (controller_id -> FrontEndDrive)
+-- Filter (Device)               Family: Filter             (controller_id -> FrontEndDrive)
```

Containment (`parent_id`) and drive (`controller_id`) are orthogonal: each optic
records `controller_id -> FrontEndDrive` for what moves it, while `parent_id`
records what it sits on. The Mirror sits on the `MirrorTable` (relocated there
after the facility install), the rest sit on the Unit; none of that changes the
controller back-reference, exactly as in the motor-homing scenario.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import bind as bind_add_asset_family
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.equipment.features.relocate_asset import RelocateAsset
from cora.equipment.features.relocate_asset import bind as bind_relocate_asset
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._facility_fixture import (
    DeviceSpec,
    facility_id_prefix,
    install_aps_unit,
    operator_for,
)

_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000004a0cc1")

# Scenario tag: 4a0 (front-end optics registration).

_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-0000004a0a01")

# Family ids (deterministic uuid5 from the name). MotionController already
# exists facility-wide; Mirror / Monochromator / Slit / Filter are defined
# by this install (the optics-foundation slice declares them in the catalog).
_CAP_MOTION_CONTROLLER_ID = family_stream_id(FamilyName("MotionController"))
_CAP_MIRROR_ID = family_stream_id(FamilyName("Mirror"))
_CAP_MONOCHROMATOR_ID = family_stream_id(FamilyName("Monochromator"))
_CAP_SLIT_ID = family_stream_id(FamilyName("Slit"))
_CAP_FILTER_ID = family_stream_id(FamilyName("Filter"))
_CAP_TABLE_ID = family_stream_id(FamilyName("Table"))

# Controller registered first so each optic's controller_id back-reference
# targets an already-registered Asset stream.
_FRONTENDDRIVE_ID = UUID("01900000-0000-7000-8000-0000004a0a31")
_MIRROR_ID = UUID("01900000-0000-7000-8000-0000004a0a11")
_MONOCHROMATOR_ID = UUID("01900000-0000-7000-8000-0000004a0a12")
_CONDITIONING_SLIT_ID = UUID("01900000-0000-7000-8000-0000004a0a13")
_SAMPLE_SLIT_ID = UUID("01900000-0000-7000-8000-0000004a0a14")
_FILTER_ID = UUID("01900000-0000-7000-8000-0000004a0a15")

# ConditioningSlit + SampleSlit share the one Slit Family (one product class,
# two physical instances), like the two SampleTop_* stages share LinearStage.
_DEVICES = (
    DeviceSpec("FrontEndDrive", _FRONTENDDRIVE_ID, "MotionController", _CAP_MOTION_CONTROLLER_ID),
    DeviceSpec("Mirror", _MIRROR_ID, "Mirror", _CAP_MIRROR_ID, controller_id=_FRONTENDDRIVE_ID),
    DeviceSpec(
        "Monochromator",
        _MONOCHROMATOR_ID,
        "Monochromator",
        _CAP_MONOCHROMATOR_ID,
        controller_id=_FRONTENDDRIVE_ID,
    ),
    DeviceSpec(
        "ConditioningSlit",
        _CONDITIONING_SLIT_ID,
        "Slit",
        _CAP_SLIT_ID,
        controller_id=_FRONTENDDRIVE_ID,
    ),
    DeviceSpec(
        "SampleSlit", _SAMPLE_SLIT_ID, "Slit", _CAP_SLIT_ID, controller_id=_FRONTENDDRIVE_ID
    ),
    DeviceSpec("Filter", _FILTER_ID, "Filter", _CAP_FILTER_ID, controller_id=_FRONTENDDRIVE_ID),
)

_OPTICS: tuple[tuple[str, UUID, UUID], ...] = (
    ("Mirror", _MIRROR_ID, _CAP_MIRROR_ID),
    ("Monochromator", _MONOCHROMATOR_ID, _CAP_MONOCHROMATOR_ID),
    ("ConditioningSlit", _CONDITIONING_SLIT_ID, _CAP_SLIT_ID),
    ("SampleSlit", _SAMPLE_SLIT_ID, _CAP_SLIT_ID),
    ("Filter", _FILTER_ID, _CAP_FILTER_ID),
)


def _id_queue() -> list[UUID]:
    """FixedIdGenerator queue: the facility prefix (which covers the install
    of the controller + five optics + their Families) plus a small slack tail."""
    return [
        *facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=_DEVICES),
        *[uuid4() for _ in range(20)],
    ]


@pytest.mark.integration
async def test_front_end_optics_register_under_frontenddrive(db_pool: asyncpg.Pool) -> None:
    """Register the five front-end optics + the FrontEndDrive controller.
    Assert each optic's genesis + Family, its controller_id back-reference to
    FrontEndDrive, and that FrontEndDrive itself carries no controller_id."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    # ----- MirrorTable + relocate the Mirror onto it. The Mirror is registered
    #       by the facility install (genesis parent = Unit, via DeviceSpec), so
    #       its containment is corrected with a relocate, exactly as the
    #       microscope scenario relocates its facility-installed leaves onto the
    #       Housing. Genesis stays Unit; the relocate records the true support. -----
    await bind_define_family(deps)(
        DefineFamily(name="Table", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    mirror_table_id = await bind_register_asset(deps)(
        RegisterAsset(name="MirrorTable", tier=AssetTier.DEVICE, parent_id=_2BM_UNIT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_asset_family(deps)(
        AddAssetFamily(asset_id=mirror_table_id, family_id=_CAP_TABLE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_relocate_asset(deps)(
        RelocateAsset(
            asset_id=_MIRROR_ID,
            to_parent_id=mirror_table_id,
            reason="Mirror sits on the front-end optical table (MirrorTable)",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Each optic: genesis + Family, genesis-parented to the Unit, with a
    #       controller_id back-reference to FrontEndDrive. The Mirror additionally
    #       carries an AssetRelocated onto MirrorTable (asserted below). -----
    for name, asset_id, cap_id in _OPTICS:
        events, _ = await deps.event_store.load("Asset", asset_id)
        expected_types = ["AssetRegistered", "AssetFamilyAdded"]
        if name == "Mirror":
            expected_types.append("AssetRelocated")
        assert [e.event_type for e in events] == expected_types, (
            f"{name}: unexpected event sequence {[e.event_type for e in events]}"
        )
        genesis = events[0].payload
        assert genesis["parent_id"] == str(_2BM_UNIT_ID), f"{name}: expected Unit genesis parent"
        assert genesis["controller_id"] == str(_FRONTENDDRIVE_ID), (
            f"{name}: expected controller_id back-reference to FrontEndDrive"
        )
        assert events[1].payload["family_id"] == str(cap_id), f"{name}: wrong Family bound"

    # ----- MirrorTable parents the Unit; the Mirror is relocated onto it
    #       (2-BM -> MirrorTable -> Mirror), matching the assets.md containment. -----
    mirror_table_events, _ = await deps.event_store.load("Asset", mirror_table_id)
    assert mirror_table_events[0].payload["name"] == "MirrorTable"
    assert mirror_table_events[0].payload["parent_id"] == str(_2BM_UNIT_ID)
    mirror_events, _ = await deps.event_store.load("Asset", _MIRROR_ID)
    relocated = [e for e in mirror_events if e.event_type == "AssetRelocated"]
    assert len(relocated) == 1, "Mirror should be relocated onto MirrorTable"
    assert relocated[0].payload["to_parent_id"] == str(mirror_table_id)

    # ----- FrontEndDrive: a controller, so it carries no controller_id. -----
    controller_events, _ = await deps.event_store.load("Asset", _FRONTENDDRIVE_ID)
    assert [e.event_type for e in controller_events] == ["AssetRegistered", "AssetFamilyAdded"]
    assert "controller_id" not in controller_events[0].payload

    # ----- The four optics Families were defined by the install ceremony. -----
    for cap_id in (_CAP_MIRROR_ID, _CAP_MONOCHROMATOR_ID, _CAP_SLIT_ID, _CAP_FILTER_ID):
        fam_events, _ = await deps.event_store.load("Family", cap_id)
        assert [e.event_type for e in fam_events] == ["FamilyDefined"], (
            f"Family {cap_id}: expected a single FamilyDefined"
        )
