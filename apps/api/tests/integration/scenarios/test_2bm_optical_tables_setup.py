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

This is the register-only slice: schemaless, matching the SampleTable
precedent. Deferred to separate slices are (a) enforcing the Table
settings schema across all three tables, and (b) modelling each table's
virtual axes as PseudoAxis facets (DetectorTable gets six; MirrorTable is
X-surface-only pending upstream bug 2bm-docs#171). Containment is shallow:
both tables parent the 2-BM Unit. Re-parenting the microscope Housing onto
DetectorTable and the Mirror onto MirrorTable moves with those scenarios.
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

# Family id (deterministic uuid5 from the name).
_FAM_TABLE = family_stream_id(FamilyName("Table"))

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
        *[uuid4() for _ in range(50)],
    ]


@pytest.mark.integration
async def test_optical_tables_registered_as_standalone_assets(db_pool: asyncpg.Pool) -> None:
    """Register DetectorTable + MirrorTable as standalone Table-family
    Assets under the 2-BM Unit. Assert each AssetRegistered (name, tier,
    parent), the single Table-family binding, and that the two ids are
    distinct."""
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
