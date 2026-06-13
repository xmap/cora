"""MCTOptics composition deployment at APS 2-BM.

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment, Calibration, Recipe

Scenario test for the MCTOptics (Optique Peter detector) composition
deployment at 2-BM micro-CT. Materializes the 7-Asset composition
locked in [[mctoptics-2bm-assets-design]] against the actual 2-BM
facility: 4 NEW Asset registrations (MCTOptics presenter + 3
Objective children) plus 2 NEW sibling Devices under 2-BM (the lens
turret RotaryStage + the lens_select PseudoAxis), 2 RelocateAsset
commands to re-parent the existing `Oryx_5MP_camera` and
`Scintillator_LuAG` under MCTOptics, 4 Calibration revisions (3 lens
magnification + 1 scintillator effective_thickness), 1 LookupTable
partition rule on the lens_select PseudoAxis, 13 typed ports, and 6
Plan wires connecting the presenter to its motor siblings, camera
child, and PseudoAxis constituent feedback.

Aligned with the current Family catalog at docs/catalog/families.md:
MCTOptics presents as `Imager` (the presenter Family was previously
`ImagingDetector`, retired in the role-aggregate-design rename;
even earlier it was the inline `Microscope` Family) and the
lens_select PseudoAxis carries a LookupTable partition rule that the
runtime evaluator decomposes into a turret rotation setpoint.

The deployment doc at docs/deployments/2-bm/equipment/mctoptics.md
prescribes MCTOptics as an Assembly + Fixture pair (not an Asset row
in its own right); the Assembly + Fixture conversion is the next
follow-on for this test and requires the Frame + Mount + install_asset
choreography for every constituent Asset, which is deferred to a
dedicated PR.

The whole ceremony, end-to-end, against Postgres.

See [[mctoptics-2bm-deployment-design]] for the deployment plan this
scenario executes. See [[project-plan-wiring-design]] for the Wire
4-tuple shape + direction + signal_type vocabulary rules.

## Why this scenario exists

Validates the 4-NEW + 2-RE-PARENT composition shape end-to-end:
each Asset gets the right Family attached, settings populate without
schema violations, RelocateAsset preserves existing Family
attachments + settings + event-stream history, Plan.wiring 4-tuples
resolve against the locked signal_type vocabulary. The 4 Calibration
revisions exercise the `magnification` + `effective_thickness`
CalibrationQuantity values added in the prior commit.

## Four hard unknowns still requiring 2-BM operator confirmation

These markers reflect the deferred decisions from the deployment memo
and represent placeholder assumptions until 2-BM staff verify:

  - **Pending(2-BM operator confirmation)**: `MCTOptics_lens_turret` Family. Assumed
    `RotaryStage` based on the Optique Peter motor positions
    121.5942 / 61.9841 / 2.3006 observation naturally as degrees. If the
    turret is actually a translating slide (positions in mm), flip
    the Family to `LinearStage` and update `lens_turret_setpoint` /
    `lens_turret_feedback` signal_type strings to the `_linear_mm`
    variants.
  - **Pending(2-BM operator confirmation)**: `Optique_Peter_focus_Z` control-path
    confirmation. The 5-Wire Plan assumes MCTOptics is the writer for
    this motor's `position_setpoint_in`. If the MCTOptics IOC drives
    the motor through an EPICS channel that bypasses CORA's command
    surface, the focus_setpoint wire is wrong.
  - **Pending(2-BM operator confirmation)**: `camera_select` motor existence. v1 assumes
    none (single camera bay, IOC-internal routing only). If a hidden
    translation stage exists, register `MCTOptics_camera_select`
    LinearStage as a sibling under 2-BM.
  - **Pending(2-BM operator confirmation)**: `camera_rotation` motor usage. v1 assumes the
    Optique Peter camera bay is fixed-rotation. If 2-BM rotates the
    camera, register `Oryx_5MP_camera_rotation` (RotaryStage) and add
    2 wires.

## Asset stack post-deployment

```
2-BM (Unit)
+-- MCTOptics (Component, NEW)                     Family: Imager
|   +-- MCTOptics_objective_0 (Device, NEW)        Family: Objective    10x
|   +-- MCTOptics_objective_1 (Device, NEW)        Family: Objective     5x
|   +-- MCTOptics_objective_2 (Device, NEW)        Family: Objective    1.1x
|   +-- Oryx_5MP_camera (Device, RE-PARENTED)      Family: Camera
|   +-- Scintillator_LuAG (Device, RE-PARENTED)    Family: Scintillator
+-- MCTOptics_lens_turret (Device, NEW sibling)    Family: RotaryStage (pending)
+-- MCTOptics_lens_select (Device, NEW sibling)    Family: PseudoAxis
+-- Optique_Peter_focus_Z (Device, pre-existing)   Family: LinearStage
```

## Calibration cardinality (4 revisions downstream)

  - 3 magnification calibrations, one per objective:
    `{objective_designation: "10x_Mitutoyo", energy: 25}` -> 9.83
    `{objective_designation: "5x_Mitutoyo",  energy: 25}` -> 4.93
    `{objective_designation: "1.1x_Mitutoyo", energy: 25}` -> 1.10
    Values derived from Optique Peter doc measured pixel sizes
    (0.351 / 0.699 / 3.126 micrometer) divided by Oryx sensor pitch
    (3.45 micrometer).
  - 1 scintillator effective_thickness calibration:
    `{scintillator_material: "LuAG", energy: 25}` -> 100 micrometer
    Sourced from the existing Scintillator_LuAG.settings.thickness.

All 4 revisions are AssertedSource (operator-attested from vendor
datasheet + Optique Peter doc), status Provisional. Measured-source
revisions land later via dedicated calibration Procedures.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.calibration.aggregates.calibration import (
    AssertedSource,
    CalibrationStatus,
)
from cora.calibration.features.append_calibration_revision import AppendCalibrationRevision
from cora.calibration.features.append_calibration_revision import (
    bind as bind_append_calibration_revision,
)
from cora.calibration.features.define_calibration import DefineCalibration
from cora.calibration.features.define_calibration import bind as bind_define_calibration
from cora.calibration.quantities import CalibrationQuantity
from cora.equipment.aggregates._partition_rule import LookupTable, ReadbackAggregatorKind
from cora.equipment.aggregates.asset import AssetTier, PortDirection
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.activate_asset import bind as bind_activate_asset
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import bind as bind_add_asset_family
from cora.equipment.features.add_asset_port import AddAssetPort
from cora.equipment.features.add_asset_port import bind as bind_add_asset_port
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.equipment.features.relocate_asset import RelocateAsset
from cora.equipment.features.relocate_asset import bind as bind_relocate_asset
from cora.equipment.features.update_asset_partition_rule import UpdateAssetPartitionRule
from cora.equipment.features.update_asset_partition_rule import (
    bind as bind_update_asset_partition_rule,
)
from cora.equipment.features.update_asset_settings import UpdateAssetSettings
from cora.equipment.features.update_asset_settings import bind as bind_update_asset_settings
from cora.equipment.features.update_family_settings_schema import UpdateFamilySettingsSchema
from cora.equipment.features.update_family_settings_schema import (
    bind as bind_update_family_settings_schema,
)
from cora.recipe.features.add_plan_wire import AddPlanWire
from cora.recipe.features.add_plan_wire import bind as bind_add_plan_wire
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_plan import bind as bind_define_plan
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.define_practice import bind as bind_define_practice
from cora.shared.identity import ActorId
from tests.integration._helpers import (
    build_postgres_deps,
    make_pg_profile_store,
    seed_capability_postgres,
)
from tests.integration.scenarios._facility_fixture import (
    DeviceSpec,
    facility_id_prefix,
    install_aps_unit,
    operator_for,
)

_NOW = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000420bb")

# Scenario tag: 420 (MCTOptics deployment ceremony).

# Facility hierarchy
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000420501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000420a01")

# Family ids are derived from the name (deterministic uuid5), so they
# converge with what install_aps_unit defines and with the NEW Families
# this scenario declares.
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))

# Family ids (NEW for MCTOptics composition)
_CAP_IMAGER_ID = family_stream_id(FamilyName("Imager"))
_CAP_OBJECTIVE_ID = family_stream_id(FamilyName("Objective"))
# Pending(2-BM operator confirmation): confirm lens turret Family (RotaryStage vs LinearStage).
# Assumed RotaryStage based on Optique Peter doc motor positions observation
# as degrees. Flip to LinearStage if the turret is linear.
_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
# PseudoAxis Family for the lens_select virtual axis. A LookupTable
# partition rule decomposes the operator-issued lens index (0/1/2)
# into the corresponding turret-rotation setpoint at runtime; the
# mctoptics_image_acquisition Method declares this Family in
# needed_family_ids alongside Imager + Camera.
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))

# Asset ids (facility-install Devices, sibling under 2-BM)
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000420a11")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000420a21")
_ASSET_OPTIQUE_PETER_FOCUS_Z_ID = UUID("01900000-0000-7000-8000-000000420a31")

# Asset ids (NEW MCTOptics composition)
_ASSET_MCTOPTICS_ID = UUID("01900000-0000-7000-8000-000000420a41")
_ASSET_MCTOPTICS_OBJECTIVE_0_ID = UUID("01900000-0000-7000-8000-000000420a51")
_ASSET_MCTOPTICS_OBJECTIVE_1_ID = UUID("01900000-0000-7000-8000-000000420a52")
_ASSET_MCTOPTICS_OBJECTIVE_2_ID = UUID("01900000-0000-7000-8000-000000420a53")
_ASSET_MCTOPTICS_LENS_TURRET_ID = UUID("01900000-0000-7000-8000-000000420a61")
_ASSET_MCTOPTICS_LENS_SELECT_ID = UUID("01900000-0000-7000-8000-000000420a62")

# Calibration ids (3 magnification + 1 effective_thickness)
_CAL_MAG_OBJ_0_ID = UUID("01900000-0000-7000-8000-000000420b01")
_CAL_MAG_OBJ_1_ID = UUID("01900000-0000-7000-8000-000000420b02")
_CAL_MAG_OBJ_2_ID = UUID("01900000-0000-7000-8000-000000420b03")
_CAL_SCINT_EFF_THICK_ID = UUID("01900000-0000-7000-8000-000000420b04")
_REV_MAG_OBJ_0_ID = UUID("01900000-0000-7000-8000-000000420b11")
_REV_MAG_OBJ_1_ID = UUID("01900000-0000-7000-8000-000000420b12")
_REV_MAG_OBJ_2_ID = UUID("01900000-0000-7000-8000-000000420b13")
_REV_SCINT_EFF_THICK_ID = UUID("01900000-0000-7000-8000-000000420b14")

# Recipe ladder
_CAPABILITY_RECIPE_ID = UUID("01900000-0000-7000-8000-000000c0420e")
_METHOD_ID = UUID("01900000-0000-7000-8000-000000420d01")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-000000420d11")
_PLAN_ID = UUID("01900000-0000-7000-8000-000000420d21")

_DRAFT = "https://json-schema.org/draft/2020-12/schema"

# Facility-install Family schemas (re-inlined per the schema-author
# anti-hook "DO NOT extract schemas before rule-of-three" from
# [[pilot-settings-schemas-design]]). Camera + Scintillator + LinearStage
# match test_2bm_alignment_center verbatim.
_SCHEMA_CAMERA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "sensor_width": {
            "type": "integer",
            "minimum": 1,
            "unit": {"system": "udunits", "code": "pixel"},
        },
        "sensor_height": {
            "type": "integer",
            "minimum": 1,
            "unit": {"system": "udunits", "code": "pixel"},
        },
        "pixel_size": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "um"},
        },
        "bit_depth": {
            "type": "integer",
            "minimum": 1,
            "unit": {"system": "udunits", "code": "bit"},
        },
    },
    "required": ["sensor_width", "sensor_height", "pixel_size", "bit_depth"],
}

_SCHEMA_SCINTILLATOR: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "thickness": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "um"},
        },
        "decay_time": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "us"},
        },
    },
    "required": ["thickness", "decay_time"],
}

_SCHEMA_LINEAR_STAGE: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "min_position": {
            "type": "number",
            "unit": {"system": "udunits", "code": "mm"},
        },
        "max_position": {
            "type": "number",
            "unit": {"system": "udunits", "code": "mm"},
        },
        "max_speed": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "mm/s"},
        },
        "encoder_resolution": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "mm"},
        },
    },
    "required": ["min_position", "max_position", "max_speed", "encoder_resolution"],
}

# NEW Family schemas: Imager (presenter Family for the MCTOptics
# presenter Asset; was ImagingDetector before the role-aggregate-design
# rename) + Objective (per-lens identity inside MCTOptics). Match the
# [[mctoptics-2bm-assets-design]] locked shapes, adapted for the Family
# settings_schema validator subset (exclusiveMinimum
# is not in the allow-list; using minimum: 0 instead. Watch item: loosen
# the subset to support exclusiveMinimum so Family schemas can match the
# design lock verbatim). The detector-shaped settings (camera_objective,
# camera_tube_length) survive here as the operational-knob carrier while
# MCTOptics remains an Asset; the eventual Assembly + Fixture migration
# will move these onto the Assembly's parameter_overrides_schema and the
# constituent Asset settings respectively.
_SCHEMA_IMAGER: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "camera_objective": {"type": "string"},
        "camera_tube_length": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "mm"},
        },
    },
    "required": ["camera_objective", "camera_tube_length"],
}

_SCHEMA_OBJECTIVE: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "magnification": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "1"},
        },
        "numerical_aperture": {
            "type": "number",
            "minimum": 0,
            "maximum": 0.95,
            "unit": {"system": "udunits", "code": "1"},
        },
        "focal_length": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "mm"},
        },
        "working_distance": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "mm"},
        },
    },
    "required": ["magnification", "numerical_aperture", "focal_length", "working_distance"],
}

# Pending(2-BM operator confirmation): swap this for _SCHEMA_LINEAR_STAGE if the lens turret
# is a translating slide rather than a rotation stage. The signal_type
# strings below also flip from rotation_deg -> linear_mm.
_SCHEMA_ROTARY_STAGE: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "min_position": {
            "type": "number",
            "unit": {"system": "udunits", "code": "deg"},
        },
        "max_position": {
            "type": "number",
            "unit": {"system": "udunits", "code": "deg"},
        },
        "max_speed": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "deg/s"},
        },
        "encoder_resolution": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "deg"},
        },
    },
    "required": ["min_position", "max_position", "max_speed", "encoder_resolution"],
}

# PseudoAxis carries no operator-tunable settings. The behaviour lives
# in the partition_rule (set out-of-band via update_asset_partition_rule)
# and in the Asset.ports topology, not in settings. The empty schema
# accepts the empty settings dict the test supplies.
_SCHEMA_PSEUDO_AXIS: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {},
    "required": [],
}

# Per-Asset settings (vendor datasheet + Optique Peter doc figures)

_SETTINGS_ORYX_5MP: dict[str, Any] = {
    "sensor_width": 2448,
    "sensor_height": 2048,
    "pixel_size": 3.45,
    "bit_depth": 12,
}

_SETTINGS_SCINTILLATOR_LUAG: dict[str, Any] = {
    "thickness": 100.0,
    "decay_time": 0.07,
}

_SETTINGS_OPTIQUE_PETER_FOCUS_Z: dict[str, Any] = {
    "min_position": -5.0,
    "max_position": 5.0,
    "max_speed": 0.5,
    "encoder_resolution": 0.0005,
}

_SETTINGS_MCTOPTICS: dict[str, Any] = {
    "camera_objective": "Mitutoyo Plan Apo",
    "camera_tube_length": 200.0,
}

_SETTINGS_OBJECTIVE_0: dict[str, Any] = {
    "magnification": 10.0,
    "numerical_aperture": 0.28,
    "focal_length": 20.0,
    "working_distance": 33.5,
}

_SETTINGS_OBJECTIVE_1: dict[str, Any] = {
    "magnification": 5.0,
    "numerical_aperture": 0.14,
    "focal_length": 40.0,
    "working_distance": 34.0,
}

_SETTINGS_OBJECTIVE_2: dict[str, Any] = {
    "magnification": 1.1,
    "numerical_aperture": 0.03,
    "focal_length": 200.0,
    "working_distance": 50.0,
}

# Pending(2-BM operator confirmation): confirm the turret motor type + adjust position bounds
# + max_speed + encoder_resolution to the actual vendor spec.
_SETTINGS_MCTOPTICS_LENS_TURRET: dict[str, Any] = {
    "min_position": 0.0,
    "max_position": 360.0,
    "max_speed": 30.0,
    "encoder_resolution": 0.01,
}

# Locked signal_type vocabulary (per [[mctoptics-2bm-deployment-design]]).
_SIG_POS_SET_ROT = "position_setpoint_rotation_deg"
_SIG_POS_FB_ROT = "position_feedback_rotation_deg"
_SIG_POS_SET_LIN = "position_setpoint_linear_mm"
_SIG_POS_FB_LIN = "position_feedback_linear_mm"
_SIG_TRIGGER = "trigger_pulse"
_SIG_IMAGE = "image_frame_uri"
# Discrete-index signal carried on the lens_select OUTPUT port (the
# operator-addressable virtual axis). Pseudoaxis runtime evaluation
# reads this address and writes the resolved turret rotation; no Plan
# wire carries this signal_type today (no other Asset consumes it).
_SIG_DISCRETE_INDEX = "discrete_index_count"

_DEVICES = (
    DeviceSpec("Oryx_5MP_camera", _ASSET_ORYX_5MP_ID, "Camera", _CAP_CAMERA_ID),
    DeviceSpec(
        "Scintillator_LuAG", _ASSET_SCINTILLATOR_LUAG_ID, "Scintillator", _CAP_SCINTILLATOR_ID
    ),
    DeviceSpec(
        "Optique_Peter_focus_Z",
        _ASSET_OPTIQUE_PETER_FOCUS_Z_ID,
        "LinearStage",
        _CAP_LINEAR_STAGE_ID,
    ),
)


def _id_queue() -> list[UUID]:
    """Build the FixedIdGenerator queue. Anonymous event ids are uuid4()."""
    e = uuid4
    return [
        *facility_id_prefix(
            unit_id=_2BM_UNIT_ID,
            devices=_DEVICES,
        ),
        # update_family_settings_schema x 3 (facility Families): event_id
        e(),
        e(),
        e(),
        # update_asset_settings x 3 (facility Assets): event_id
        e(),
        e(),
        e(),
        # define_family x 4 (Imager + Objective + RotaryStage + PseudoAxis):
        # event_id only (stream id derived from the name, not popped)
        e(),
        e(),
        e(),
        e(),
        # update_family_settings_schema x 4 (NEW Families): event_id
        e(),
        e(),
        e(),
        e(),
        # register_asset x 6 (MCTOptics + 3 objectives + lens_turret + lens_select):
        # asset_id, event_id
        _ASSET_MCTOPTICS_ID,
        e(),
        _ASSET_MCTOPTICS_OBJECTIVE_0_ID,
        e(),
        _ASSET_MCTOPTICS_OBJECTIVE_1_ID,
        e(),
        _ASSET_MCTOPTICS_OBJECTIVE_2_ID,
        e(),
        _ASSET_MCTOPTICS_LENS_TURRET_ID,
        e(),
        _ASSET_MCTOPTICS_LENS_SELECT_ID,
        e(),
        # relocate_asset x 2 (Oryx + Scintillator -> MCTOptics): event_id
        e(),
        e(),
        # add_asset_family x 6 (NEW Assets only): event_id
        e(),
        e(),
        e(),
        e(),
        e(),
        e(),
        # update_asset_settings x 5 (NEW Assets only; lens_select has no
        # operator-tunable settings and is skipped, see _NEW_ASSET_SETTINGS):
        # event_id
        e(),
        e(),
        e(),
        e(),
        e(),
        # activate_asset x 6 (NEW Assets only): event_id
        e(),
        e(),
        e(),
        e(),
        e(),
        e(),
        # add_asset_port x 13: event_id each (11 on the 4 prior wire-endpoint
        # Assets + 2 on lens_select)
        e(),
        e(),
        e(),
        e(),
        e(),
        e(),
        e(),
        e(),
        e(),
        e(),
        e(),
        e(),
        e(),
        # define_calibration + append_calibration_revision x 4: per Calibration the
        # ceremony is (cal_id, def_event_id, rev_id, rev_event_id).
        _CAL_MAG_OBJ_0_ID,
        e(),
        _REV_MAG_OBJ_0_ID,
        e(),
        _CAL_MAG_OBJ_1_ID,
        e(),
        _REV_MAG_OBJ_1_ID,
        e(),
        _CAL_MAG_OBJ_2_ID,
        e(),
        _REV_MAG_OBJ_2_ID,
        e(),
        _CAL_SCINT_EFF_THICK_ID,
        e(),
        _REV_SCINT_EFF_THICK_ID,
        e(),
        # update_asset_partition_rule x 1 (lens_select LookupTable): event_id
        e(),
        # define_method: method_id, event_id
        _METHOD_ID,
        e(),
        # define_practice: practice_id, event_id
        _PRACTICE_ID,
        e(),
        # define_plan: plan_id, event_id
        _PLAN_ID,
        e(),
        # add_plan_wire x 6: event_id each (5 motor/camera wires + 1
        # lens_turret feedback -> lens_select constituent)
        e(),
        e(),
        e(),
        e(),
        e(),
        e(),
    ]


_FACILITY_SCHEMA_SPECS: tuple[tuple[UUID, dict[str, Any]], ...] = (
    (_CAP_CAMERA_ID, _SCHEMA_CAMERA),
    (_CAP_SCINTILLATOR_ID, _SCHEMA_SCINTILLATOR),
    (_CAP_LINEAR_STAGE_ID, _SCHEMA_LINEAR_STAGE),
)

_FACILITY_SETTINGS_SPECS: tuple[tuple[UUID, dict[str, Any]], ...] = (
    (_ASSET_ORYX_5MP_ID, _SETTINGS_ORYX_5MP),
    (_ASSET_SCINTILLATOR_LUAG_ID, _SETTINGS_SCINTILLATOR_LUAG),
    (_ASSET_OPTIQUE_PETER_FOCUS_Z_ID, _SETTINGS_OPTIQUE_PETER_FOCUS_Z),
)

_NEW_FAMILY_DEFS: tuple[tuple[UUID, str], ...] = (
    (_CAP_IMAGER_ID, "Imager"),
    (_CAP_OBJECTIVE_ID, "Objective"),
    (_CAP_ROTARY_STAGE_ID, "RotaryStage"),
    (_CAP_PSEUDO_AXIS_ID, "PseudoAxis"),
)

_NEW_FAMILY_SCHEMAS: tuple[tuple[UUID, dict[str, Any]], ...] = (
    (_CAP_IMAGER_ID, _SCHEMA_IMAGER),
    (_CAP_OBJECTIVE_ID, _SCHEMA_OBJECTIVE),
    (_CAP_ROTARY_STAGE_ID, _SCHEMA_ROTARY_STAGE),
    (_CAP_PSEUDO_AXIS_ID, _SCHEMA_PSEUDO_AXIS),
)

# (asset_id, parent_id, asset_name, tier)
_NEW_ASSET_REGISTRATIONS: tuple[tuple[UUID, UUID, str, AssetTier], ...] = (
    (_ASSET_MCTOPTICS_ID, _2BM_UNIT_ID, "MCTOptics", AssetTier.COMPONENT),
    (
        _ASSET_MCTOPTICS_OBJECTIVE_0_ID,
        _ASSET_MCTOPTICS_ID,
        "MCTOptics_objective_0",
        AssetTier.DEVICE,
    ),
    (
        _ASSET_MCTOPTICS_OBJECTIVE_1_ID,
        _ASSET_MCTOPTICS_ID,
        "MCTOptics_objective_1",
        AssetTier.DEVICE,
    ),
    (
        _ASSET_MCTOPTICS_OBJECTIVE_2_ID,
        _ASSET_MCTOPTICS_ID,
        "MCTOptics_objective_2",
        AssetTier.DEVICE,
    ),
    (_ASSET_MCTOPTICS_LENS_TURRET_ID, _2BM_UNIT_ID, "MCTOptics_lens_turret", AssetTier.DEVICE),
    (_ASSET_MCTOPTICS_LENS_SELECT_ID, _2BM_UNIT_ID, "MCTOptics_lens_select", AssetTier.DEVICE),
)

_NEW_ASSET_FAMILY_LINKS: tuple[tuple[UUID, UUID], ...] = (
    (_ASSET_MCTOPTICS_ID, _CAP_IMAGER_ID),
    (_ASSET_MCTOPTICS_OBJECTIVE_0_ID, _CAP_OBJECTIVE_ID),
    (_ASSET_MCTOPTICS_OBJECTIVE_1_ID, _CAP_OBJECTIVE_ID),
    (_ASSET_MCTOPTICS_OBJECTIVE_2_ID, _CAP_OBJECTIVE_ID),
    (_ASSET_MCTOPTICS_LENS_TURRET_ID, _CAP_ROTARY_STAGE_ID),
    (_ASSET_MCTOPTICS_LENS_SELECT_ID, _CAP_PSEUDO_AXIS_ID),
)

# lens_select is intentionally absent: PseudoAxis Assets carry no
# operator-tunable settings (the partition_rule + ports are the
# behaviour surface). update_asset_settings with an empty patch is a
# no-op at the decider tier (no AssetSettingsUpdated event emitted),
# so skipping the call keeps the id-queue budget honest.
_NEW_ASSET_SETTINGS: tuple[tuple[UUID, dict[str, Any]], ...] = (
    (_ASSET_MCTOPTICS_ID, _SETTINGS_MCTOPTICS),
    (_ASSET_MCTOPTICS_OBJECTIVE_0_ID, _SETTINGS_OBJECTIVE_0),
    (_ASSET_MCTOPTICS_OBJECTIVE_1_ID, _SETTINGS_OBJECTIVE_1),
    (_ASSET_MCTOPTICS_OBJECTIVE_2_ID, _SETTINGS_OBJECTIVE_2),
    (_ASSET_MCTOPTICS_LENS_TURRET_ID, _SETTINGS_MCTOPTICS_LENS_TURRET),
)

# 13 typed ports across 5 Assets (per the Plan.wiring topology in
# [[mctoptics-2bm-deployment-design]] plus the lens_select PseudoAxis
# fan-in port + operator-addressable virtual OUTPUT).
# (asset_id, port_name, direction, signal_type)
_PORT_SPECS: tuple[tuple[UUID, str, PortDirection, str], ...] = (
    # MCTOptics: 3 OUT + 2 IN
    (_ASSET_MCTOPTICS_ID, "lens_turret_setpoint", PortDirection.OUTPUT, _SIG_POS_SET_ROT),
    (_ASSET_MCTOPTICS_ID, "lens_turret_feedback", PortDirection.INPUT, _SIG_POS_FB_ROT),
    (_ASSET_MCTOPTICS_ID, "focus_setpoint", PortDirection.OUTPUT, _SIG_POS_SET_LIN),
    (_ASSET_MCTOPTICS_ID, "focus_feedback", PortDirection.INPUT, _SIG_POS_FB_LIN),
    (_ASSET_MCTOPTICS_ID, "camera_trigger", PortDirection.OUTPUT, _SIG_TRIGGER),
    # MCTOptics_lens_turret: setpoint in + feedback out
    (
        _ASSET_MCTOPTICS_LENS_TURRET_ID,
        "position_setpoint_in",
        PortDirection.INPUT,
        _SIG_POS_SET_ROT,
    ),
    (
        _ASSET_MCTOPTICS_LENS_TURRET_ID,
        "position_feedback_out",
        PortDirection.OUTPUT,
        _SIG_POS_FB_ROT,
    ),
    # Optique_Peter_focus_Z: setpoint in + feedback out
    (
        _ASSET_OPTIQUE_PETER_FOCUS_Z_ID,
        "position_setpoint_in",
        PortDirection.INPUT,
        _SIG_POS_SET_LIN,
    ),
    (
        _ASSET_OPTIQUE_PETER_FOCUS_Z_ID,
        "position_feedback_out",
        PortDirection.OUTPUT,
        _SIG_POS_FB_LIN,
    ),
    # Oryx_5MP_camera: trigger in + image out
    (_ASSET_ORYX_5MP_ID, "trigger_in", PortDirection.INPUT, _SIG_TRIGGER),
    (_ASSET_ORYX_5MP_ID, "image_out", PortDirection.OUTPUT, _SIG_IMAGE),
    # MCTOptics_lens_select (PseudoAxis): 1 constituent INPUT (receives
    # the lens_turret feedback per validate_pseudoaxis_fanout) + 1
    # operator-addressable OUTPUT (the virtual lens-index port the
    # runtime expander addresses via pseudoaxis://<asset_id>/<port>).
    (
        _ASSET_MCTOPTICS_LENS_SELECT_ID,
        "constituent_in",
        PortDirection.INPUT,
        _SIG_POS_FB_ROT,
    ),
    (
        _ASSET_MCTOPTICS_LENS_SELECT_ID,
        "lens_select_out",
        PortDirection.OUTPUT,
        _SIG_DISCRETE_INDEX,
    ),
)

# 4 Calibration revisions. Magnification values derived per Optique Peter
# doc measured pixel sizes (0.351 / 0.699 / 3.126 um) divided by Oryx
# sensor pitch (3.45 um), giving 9.83 / 4.93 / 1.10 effective.
#
# Each spec carries a 7th element: a per-Calibration description string
# embedding the vendor citation (URL + revision/date) required by
# [[calibration-design]] anti-hook 13 (no synthesis-by-omission) for
# every AssertedSource revision. The description is the only free
# provenance field on Calibration today; promoting to a structured
# `provenance` field on AssertedSource is a deferred Calibration BC
# extension per [[mctoptics-2bm-deployment-design]] Watch item 10.
_CALIBRATION_SPECS: tuple[
    tuple[UUID, UUID, UUID, CalibrationQuantity, dict[str, Any], dict[str, Any], str], ...
] = (
    (
        _CAL_MAG_OBJ_0_ID,
        _REV_MAG_OBJ_0_ID,
        _ASSET_MCTOPTICS_OBJECTIVE_0_ID,
        CalibrationQuantity.MAGNIFICATION,
        {"objective_designation": "10x_Mitutoyo", "energy": 25.0},
        {"magnification": 9.83},
        (
            "Initial AssertedSource revision. Vendor: Mitutoyo Plan Apo 10x "
            "(datasheet https://www.mitutoyo.com/products/optical-instruments/objective-lenses/ "
            "as accessed 2026-05-28). Effective magnification 9.83x derived "
            "from Optique Peter doc measured pixel size 0.351 um divided by "
            "Oryx 3.45 um sensor pitch "
            "(https://docs2bm.readthedocs.io/en/latest/source/pre_apsu/ops/item_070.html "
            "as accessed 2026-05-28). Supersede with MeasuredSource once a "
            "calibration Procedure runs."
        ),
    ),
    (
        _CAL_MAG_OBJ_1_ID,
        _REV_MAG_OBJ_1_ID,
        _ASSET_MCTOPTICS_OBJECTIVE_1_ID,
        CalibrationQuantity.MAGNIFICATION,
        {"objective_designation": "5x_Mitutoyo", "energy": 25.0},
        {"magnification": 4.93},
        (
            "Initial AssertedSource revision. Vendor: Mitutoyo Plan Apo 5x "
            "(datasheet https://www.mitutoyo.com/products/optical-instruments/objective-lenses/ "
            "as accessed 2026-05-28). Effective magnification 4.93x derived "
            "from Optique Peter doc measured pixel size 0.699 um divided by "
            "Oryx 3.45 um sensor pitch "
            "(https://docs2bm.readthedocs.io/en/latest/source/pre_apsu/ops/item_070.html "
            "as accessed 2026-05-28)."
        ),
    ),
    (
        _CAL_MAG_OBJ_2_ID,
        _REV_MAG_OBJ_2_ID,
        _ASSET_MCTOPTICS_OBJECTIVE_2_ID,
        CalibrationQuantity.MAGNIFICATION,
        {"objective_designation": "1.1x_Mitutoyo", "energy": 25.0},
        {"magnification": 1.10},
        (
            "Initial AssertedSource revision. Vendor: Mitutoyo Plan Apo 1.1x "
            "(datasheet https://www.mitutoyo.com/products/optical-instruments/objective-lenses/ "
            "as accessed 2026-05-28). Effective magnification 1.10x derived "
            "from Optique Peter doc measured pixel size 3.126 um divided by "
            "Oryx 3.45 um sensor pitch "
            "(https://docs2bm.readthedocs.io/en/latest/source/pre_apsu/ops/item_070.html "
            "as accessed 2026-05-28)."
        ),
    ),
    (
        _CAL_SCINT_EFF_THICK_ID,
        _REV_SCINT_EFF_THICK_ID,
        _ASSET_SCINTILLATOR_LUAG_ID,
        CalibrationQuantity.EFFECTIVE_THICKNESS,
        {"scintillator_material": "LuAG", "energy": 25.0},
        {"effective_thickness": 100.0},
        (
            "Initial AssertedSource revision. Source: existing "
            "Scintillator_LuAG.settings.thickness = 100 um, registered "
            "in 2-BM inventory pre-deployment "
            "(see apps/api/docs/deployments/2-bm/assets.md). Supersede with "
            "MeasuredSource once a beam-on attenuation-length measurement runs."
        ),
    ),
)

# 6 Plan wires per the Plan.wiring topology in [[mctoptics-2bm-deployment-design]]:
# 5 motor / camera wires from the original topology plus 1 lens_turret
# feedback fan-in to the lens_select PseudoAxis constituent INPUT.
# (source_asset_id, source_port_name, target_asset_id, target_port_name)
_WIRE_SPECS: tuple[tuple[UUID, str, UUID, str], ...] = (
    (
        _ASSET_MCTOPTICS_ID,
        "lens_turret_setpoint",
        _ASSET_MCTOPTICS_LENS_TURRET_ID,
        "position_setpoint_in",
    ),
    (
        _ASSET_MCTOPTICS_LENS_TURRET_ID,
        "position_feedback_out",
        _ASSET_MCTOPTICS_ID,
        "lens_turret_feedback",
    ),
    (
        _ASSET_MCTOPTICS_ID,
        "focus_setpoint",
        _ASSET_OPTIQUE_PETER_FOCUS_Z_ID,
        "position_setpoint_in",
    ),
    (
        _ASSET_OPTIQUE_PETER_FOCUS_Z_ID,
        "position_feedback_out",
        _ASSET_MCTOPTICS_ID,
        "focus_feedback",
    ),
    (_ASSET_MCTOPTICS_ID, "camera_trigger", _ASSET_ORYX_5MP_ID, "trigger_in"),
    # PseudoAxis fan-in: lens_turret feedback drives the lens_select
    # constituent so the runtime evaluator can reconstruct the virtual
    # axis readback. The lens_select OUTPUT (lens_select_out) is
    # addressed via the pseudoaxis:// URL scheme directly and carries
    # no Plan-level wire.
    (
        _ASSET_MCTOPTICS_LENS_TURRET_ID,
        "position_feedback_out",
        _ASSET_MCTOPTICS_LENS_SELECT_ID,
        "constituent_in",
    ),
)


@pytest.mark.integration
async def test_mctoptics_deployment_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Materialize the 6-Asset MCTOptics composition end-to-end:
    facility install + 3 facility-Family settings + 5 NEW Asset
    registrations + 2 RelocateAsset re-parents + ports + 4 Calibrations
    + Method/Practice/Plan + 5 Wires. Assert event streams + projection
    rows + relocation events emitted."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Facility install (Argonne -> APS -> 2-BM + 3 Devices) -----

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    # ----- Facility-Family schemas + Asset settings -----

    for cap_id, schema in _FACILITY_SCHEMA_SPECS:
        await bind_update_family_settings_schema(deps)(
            UpdateFamilySettingsSchema(family_id=cap_id, settings_schema=schema),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    for asset_id, settings in _FACILITY_SETTINGS_SPECS:
        await bind_update_asset_settings(deps)(
            UpdateAssetSettings(asset_id=asset_id, settings_patch=settings),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- NEW Families (Microscope, Objective, RotaryStage) -----

    for _cap_id, name in _NEW_FAMILY_DEFS:
        await bind_define_family(deps)(
            DefineFamily(name=name, affordances=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    for cap_id, schema in _NEW_FAMILY_SCHEMAS:
        await bind_update_family_settings_schema(deps)(
            UpdateFamilySettingsSchema(family_id=cap_id, settings_schema=schema),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- 5 NEW Asset registrations (MCTOptics + children + turret) -----

    for _asset_id, parent_id, name, tier in _NEW_ASSET_REGISTRATIONS:
        await bind_register_asset(deps)(
            RegisterAsset(name=name, tier=tier, parent_id=parent_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Re-parent the existing camera + scintillator under MCTOptics -----

    await bind_relocate_asset(deps)(
        RelocateAsset(
            asset_id=_ASSET_ORYX_5MP_ID,
            to_parent_id=_ASSET_MCTOPTICS_ID,
            reason="MCTOptics composition lock landed",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_relocate_asset(deps)(
        RelocateAsset(
            asset_id=_ASSET_SCINTILLATOR_LUAG_ID,
            to_parent_id=_ASSET_MCTOPTICS_ID,
            reason="MCTOptics composition lock landed",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Attach Families + populate settings on NEW Assets -----

    for asset_id, cap_id in _NEW_ASSET_FAMILY_LINKS:
        await bind_add_asset_family(deps)(
            AddAssetFamily(asset_id=asset_id, family_id=cap_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    for asset_id, settings in _NEW_ASSET_SETTINGS:
        await bind_update_asset_settings(deps)(
            UpdateAssetSettings(asset_id=asset_id, settings_patch=settings),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Activate the 5 NEW Assets -----

    for asset_id, _cap_id in _NEW_ASSET_FAMILY_LINKS:
        await bind_activate_asset(deps)(
            ActivateAsset(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- 11 typed ports on the 4 wire-endpoint Assets -----

    for asset_id, port_name, direction, signal_type in _PORT_SPECS:
        await bind_add_asset_port(deps)(
            AddAssetPort(
                asset_id=asset_id,
                port_name=port_name,
                direction=direction,
                signal_type=signal_type,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- 4 Calibrations + 4 AssertedSource revisions -----

    # Each Calibration is defined + has its initial revision appended in
    # one iteration so the per-Calibration unit reads as a self-contained
    # registration. AssertedSource.actor_id IS the envelope principal
    # here because the operator both reads the vendor citation AND pushes
    # the command; in the general case the field captures the attesting
    # author (which may differ from the pushing operator, e.g., an
    # automated agent pushes on behalf of a human).
    for cal_id, _rev_id, target_id, quantity, op_point, value, description in _CALIBRATION_SPECS:
        await bind_define_calibration(deps)(
            DefineCalibration(
                target_id=target_id,
                quantity=quantity,
                operating_point=op_point,
                description=description,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        await bind_append_calibration_revision(deps)(
            AppendCalibrationRevision(
                calibration_id=cal_id,
                value=value,
                status=CalibrationStatus.PROVISIONAL,
                source=AssertedSource(asserted_by=ActorId(_PRINCIPAL_ID)),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- LookupTable partition rule on the lens_select PseudoAxis -----

    # Operator-issued lens index -> turret rotation in degrees. The
    # calibration_revision_id references one of the magnification
    # revisions registered above. This is a deliberate placeholder for
    # the test scope: the runtime evaluator would expect a revision
    # whose value carries the index-to-angle table (a calibration
    # quantity that does not exist yet in the closed catalog), and the
    # handler does not load the revision, so any non-sentinel UUID
    # satisfies construction + Family-membership gate. `invertible=False`
    # with `readback_aggregator_kind=IDENTITY` skips the monotonicity
    # check and uses the single constituent's feedback as the virtual
    # readback. Replace with a real lens-turret-position calibration
    # when the Calibration BC grows a table-shaped CalibrationQuantity.
    await bind_update_asset_partition_rule(deps)(
        UpdateAssetPartitionRule(
            asset_id=_ASSET_MCTOPTICS_LENS_SELECT_ID,
            partition_rule=LookupTable(
                calibration_revision_id=_REV_MAG_OBJ_0_ID,
                invertible=False,
                readback_aggregator_kind=ReadbackAggregatorKind.IDENTITY,
                unit_in="index",
                unit_out="deg",
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Minimal Recipe ladder + 6 Plan wires -----

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_RECIPE_ID,
        code="cora.capability.mctoptics_acquisition",
        name="MCTOpticsAcquisition",
    )

    await bind_define_method(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_RECIPE_ID,
            name="mctoptics_image_acquisition",
            needed_family_ids=frozenset({_CAP_IMAGER_ID, _CAP_CAMERA_ID, _CAP_PSEUDO_AXIS_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="2BM_mctoptics_practice",
            method_id=_METHOD_ID,
            site_id=_APS_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_mctoptics_plan",
            practice_id=_PRACTICE_ID,
            asset_ids=frozenset(
                {
                    _ASSET_MCTOPTICS_ID,
                    _ASSET_MCTOPTICS_LENS_TURRET_ID,
                    _ASSET_MCTOPTICS_LENS_SELECT_ID,
                    _ASSET_OPTIQUE_PETER_FOCUS_Z_ID,
                    _ASSET_ORYX_5MP_ID,
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    for source_id, source_port, target_id, target_port in _WIRE_SPECS:
        await bind_add_plan_wire(deps)(
            AddPlanWire(
                plan_id=_PLAN_ID,
                source_asset_id=source_id,
                source_port_name=source_port,
                target_asset_id=target_id,
                target_port_name=target_port,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Assertions -----

    # Each of the 5 settings-carrying NEW Asset streams has the expected
    # event sequence. lens_select is checked separately below since it
    # carries no settings.
    for asset_id in (
        _ASSET_MCTOPTICS_ID,
        _ASSET_MCTOPTICS_OBJECTIVE_0_ID,
        _ASSET_MCTOPTICS_OBJECTIVE_1_ID,
        _ASSET_MCTOPTICS_OBJECTIVE_2_ID,
        _ASSET_MCTOPTICS_LENS_TURRET_ID,
    ):
        events, _version = await deps.event_store.load("Asset", asset_id)
        types = [e.event_type for e in events]
        assert types[0] == "AssetRegistered", f"{asset_id}: expected genesis"
        assert "AssetFamilyAdded" in types, f"{asset_id}: expected Family attachment"
        assert "AssetSettingsUpdated" in types, f"{asset_id}: expected settings populated"
        assert "AssetActivated" in types, f"{asset_id}: expected activation"

    # The lens_select PseudoAxis carries genesis + Family + activation +
    # 2 ports + AssetPartitionRuleUpdated from the LookupTable rule set
    # above; it has no settings (PseudoAxis is partition_rule + ports
    # only).
    lens_select_events, _ = await deps.event_store.load("Asset", _ASSET_MCTOPTICS_LENS_SELECT_ID)
    lens_select_types = [e.event_type for e in lens_select_events]
    assert lens_select_types[0] == "AssetRegistered", "lens_select: expected genesis"
    assert "AssetFamilyAdded" in lens_select_types, (
        "lens_select: expected PseudoAxis Family attached"
    )
    assert "AssetActivated" in lens_select_types, "lens_select: expected activation"
    assert "AssetPartitionRuleUpdated" in lens_select_types, (
        "lens_select: expected AssetPartitionRuleUpdated event"
    )
    assert "AssetSettingsUpdated" not in lens_select_types, (
        "lens_select: no settings update expected (PseudoAxis carries no settings)"
    )

    # Re-parent events emitted on the 2 EXISTING Asset streams.
    for asset_id in (_ASSET_ORYX_5MP_ID, _ASSET_SCINTILLATOR_LUAG_ID):
        events, _version = await deps.event_store.load("Asset", asset_id)
        types = [e.event_type for e in events]
        assert "AssetRelocated" in types, f"{asset_id}: expected AssetRelocated event"

    # 4 Calibration aggregates registered with exactly 1 revision each.
    for cal_id in (
        _CAL_MAG_OBJ_0_ID,
        _CAL_MAG_OBJ_1_ID,
        _CAL_MAG_OBJ_2_ID,
        _CAL_SCINT_EFF_THICK_ID,
    ):
        events, _version = await deps.event_store.load("Calibration", cal_id)
        types = [e.event_type for e in events]
        assert types == ["CalibrationDefined", "CalibrationRevisionAppended"], (
            f"{cal_id}: expected define + 1 revision, got {types}"
        )

    # Plan stream carries the 5 PlanWireAdded events. Assert the 4-tuple
    # identities (not just the count) to catch silent direction-swap or
    # signal_type-coerce regressions in AddPlanWire.
    plan_events, _plan_version = await deps.event_store.load("Plan", _PLAN_ID)
    plan_wire_added = [e for e in plan_events if e.event_type == "PlanWireAdded"]
    assert len(plan_wire_added) == len(_WIRE_SPECS), (
        f"expected {len(_WIRE_SPECS)} PlanWireAdded events, got {len(plan_wire_added)}"
    )
    actual_wires = frozenset(
        (
            UUID(e.payload["source_asset_id"]),
            e.payload["source_port_name"],
            UUID(e.payload["target_asset_id"]),
            e.payload["target_port_name"],
        )
        for e in plan_wire_added
    )
    expected_wires = frozenset(_WIRE_SPECS)
    assert actual_wires == expected_wires, (
        f"wire 4-tuples diverge.\n  missing: {expected_wires - actual_wires}\n  "
        f"unexpected: {actual_wires - expected_wires}"
    )
