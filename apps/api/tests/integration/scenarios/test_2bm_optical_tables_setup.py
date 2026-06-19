"""Optical support tables at APS 2-BM (DetectorTable + MirrorTable).

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment

Registers the two remaining 2-BM optical support tables as standalone
`Table`-family Assets under the 2-BM Unit, completing the three-table set
(`SampleTable` is already modeled by test_2bm_sample_tower_setup.py).

Each table earns its Asset because a real consumer needs it:
  - DetectorTable (2bmb:table3): the detector_z_rail_alignment Procedure
    targets its angular axes, so it has a live consumer.
  - MirrorTable (2bma:table1): in operational use, the energy-change IOC
    drives its X axes for stripe selection (confirmed STAGE-7, #138).

Both tables carry their schema-validated `Table` settings (axis_layout:
virtual_pose), and DetectorTable's six virtual axes are modeled as
PseudoAxis sub-Assets (DetectorTable_X/_Y/_Z/_Roll/_Pitch/_Yaw, the
hexapod-aligned axis vocabulary). Those axes carry NO partition rule:
the EPICS `table3` record computes the pose from the six support motors,
so the geometry is owned by the IOC, not CORA; addressing an axis is a
direct ControlPort write to its `table3.*` PV.

Containment is shallow here: both tables parent the 2-BM Unit. The
Housing-onto-DetectorTable and Mirror-onto-MirrorTable re-parents have
since landed in their own scenarios (the microscope and front-end-optics
setups), and the microscope scenario further nests the PropagationDistance
rail between DetectorTable and Housing (DET-12). Still deferred:
MirrorTable's axes (X-surface-only pending upstream bug 2bm-docs#171).
Per-device location is descriptor-owned and not asserted here.
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
from cora.equipment.features.update_asset_settings import UpdateAssetSettings
from cora.equipment.features.update_asset_settings import bind as bind_update_asset_settings
from cora.equipment.features.update_family_settings_schema import UpdateFamilySettingsSchema
from cora.equipment.features.update_family_settings_schema import (
    bind as bind_update_family_settings_schema,
)
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._facility_fixture import (
    facility_id_prefix,
    install_aps_unit,
    operator_for,
)

_NOW = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000431bb")

# Facility hierarchy (scenario tag 431).
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000431a01")

# Family ids (deterministic uuid5 from the name).
_FAM_TABLE = family_stream_id(FamilyName("Table"))
_FAM_PSEUDO_AXIS = family_stream_id(FamilyName("PseudoAxis"))

# The Table settings schema (the JSON-Schema subset; strictness is injected at
# validation, so no additionalProperties here). axis_layout is the discriminator
# between the sample table's direct motors and the detector/mirror virtual records.
# Defined inline per scenario (rule-of-three not fired: only two scenarios use it).
_SCHEMA_TABLE = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "axis_layout": {"type": "string", "enum": ["translation_xyz", "virtual_pose"]},
        "virtual_record": {"type": "string"},
        "geometry": {"type": "string"},
    },
    "required": ["axis_layout"],
}

# Per-table settings. Both new tables are virtual_pose (composite EPICS records);
# the sample table's translation_xyz is set in the sample-tower scenario.
_TABLE_SETTINGS: dict[str, dict[str, object]] = {
    "DetectorTable": {
        "axis_layout": "virtual_pose",
        "virtual_record": "2bmb:table3",
        "geometry": "SRI: 3 Y-supports, 2 X-supports, 1 Z-support",
    },
    "MirrorTable": {
        "axis_layout": "virtual_pose",
        "virtual_record": "2bma:table1",
        "geometry": "SRI support table",
    },
}


def _id_queue() -> list[UUID]:
    """FixedIdGenerator queue: the facility prefix for a device-less Unit
    install, then a block of anonymous ids. The two table Assets are
    registered fresh (ids captured from the handler returns), so the tail
    only needs to be long enough."""
    return [
        *facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=()),
        *[uuid4() for _ in range(80)],
    ]


@pytest.mark.integration
async def test_optical_tables_registered_as_standalone_assets(db_pool: asyncpg.Pool) -> None:
    """Register DetectorTable + MirrorTable as standalone Table-family
    Assets under the 2-BM Unit with schema-validated settings, and model
    DetectorTable's six virtual axes as PseudoAxis sub-Assets. Assert each
    table's AssetRegistered + Family + settings, and each axis's
    registration, parent, Family, and absence of a partition rule."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Facility install: just the 2-BM Unit (no devices; the tables are
    #       registered fresh below). -----
    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=(),
    )

    # ----- Table Family (empty affordances) + its settings schema, so the
    #       per-table axis_layout is enforced, not just documented. -----
    await bind_define_family(deps)(
        DefineFamily(name="Table", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_update_family_settings_schema(deps)(
        UpdateFamilySettingsSchema(family_id=_FAM_TABLE, settings_schema=_SCHEMA_TABLE),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- The two support tables, registered standalone under the Unit, each
    #       with its schema-validated settings (both virtual_pose). -----
    tables: dict[str, UUID] = {}
    for asset_name in ("DetectorTable", "MirrorTable"):
        aid = await bind_register_asset(deps)(
            RegisterAsset(name=asset_name, tier=AssetTier.DEVICE, parent_id=_2BM_UNIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        tables[asset_name] = aid
        await bind_add_asset_family(deps)(
            AddAssetFamily(asset_id=aid, family_id=_FAM_TABLE),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        await bind_update_asset_settings(deps)(
            UpdateAssetSettings(asset_id=aid, settings_patch=_TABLE_SETTINGS[asset_name]),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- The detector table's six virtual axes, as PseudoAxis sub-Assets
    #       under DetectorTable. The table3 IOC record computes the pose from the
    #       six support motors (geometry owned by EPICS), so these carry NO
    #       partition rule and no wiring -- CORA just names and addresses them.
    #       Names follow the hexapod axis convention (one unified CORA axis
    #       vocabulary); each axis's table3.* PV + raw AX/AY/AZ label live in the
    #       descriptor / inventory.md, mirroring the hexapod DoF facets. -----
    await bind_define_family(deps)(
        DefineFamily(name="PseudoAxis", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    detector_table_id = tables["DetectorTable"]
    detector_axes: dict[str, UUID] = {}
    for axis_name in (
        "DetectorTable_X",
        "DetectorTable_Y",
        "DetectorTable_Z",
        "DetectorTable_Roll",
        "DetectorTable_Pitch",
        "DetectorTable_Yaw",
    ):
        axis_id = await bind_register_asset(deps)(
            RegisterAsset(name=axis_name, tier=AssetTier.DEVICE, parent_id=detector_table_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        detector_axes[axis_name] = axis_id
        await bind_add_asset_family(deps)(
            AddAssetFamily(asset_id=axis_id, family_id=_FAM_PSEUDO_AXIS),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Distinct Assets (one product per physical table, not collapsed).
    assert tables["DetectorTable"] != tables["MirrorTable"]

    for asset_name, aid in tables.items():
        events, _ = await deps.event_store.load("Asset", aid)

        assert events[0].event_type == "AssetRegistered"
        assert events[0].payload["name"] == asset_name
        assert AssetTier(events[0].payload["tier"]) == AssetTier.DEVICE
        assert events[0].payload["parent_id"] == str(_2BM_UNIT_ID), (
            f"{asset_name} should parent the 2-BM Unit (shallow containment this slice)"
        )

        family_added = [e for e in events if e.event_type == "AssetFamilyAdded"]
        assert len(family_added) == 1, f"{asset_name} should carry exactly one Family binding"
        assert family_added[0].payload["family_id"] == str(_FAM_TABLE)

        # Schema-validated settings landed (the event carries the full post-merge dict).
        settings_updated = [e for e in events if e.event_type == "AssetSettingsUpdated"]
        assert len(settings_updated) == 1, f"{asset_name} should have one settings update"
        assert settings_updated[0].payload["settings"] == _TABLE_SETTINGS[asset_name]

    # The six detector-table axes: PseudoAxis sub-Assets parented to DetectorTable,
    # carrying NO partition rule (the table3 IOC owns the 6-support -> 6-axis geometry).
    assert len(detector_axes) == 6
    for axis_name, axis_id in detector_axes.items():
        events, _ = await deps.event_store.load("Asset", axis_id)
        assert events[0].event_type == "AssetRegistered"
        assert events[0].payload["name"] == axis_name
        assert events[0].payload["parent_id"] == str(detector_table_id), (
            f"{axis_name} should parent DetectorTable (Device-in-Device facet)"
        )
        family_added = [e for e in events if e.event_type == "AssetFamilyAdded"]
        assert len(family_added) == 1, f"{axis_name} should carry exactly one Family binding"
        assert family_added[0].payload["family_id"] == str(_FAM_PSEUDO_AXIS)
        # EPICS owns the table geometry: these axes carry no CORA partition rule.
        assert not [e for e in events if "PartitionRule" in e.event_type], (
            f"{axis_name} must carry no partition rule (the table3 IOC owns the geometry)"
        )
