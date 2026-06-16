"""Microscope detector deployment at APS 2-BM (Assembly + Optics + Fixture).

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment, Calibration, Recipe

Materializes the 2-BM Optique Peter detector as the Microscope model,
end-to-end against Postgres:

  - a reusable, content-hashed **Optics** sub-assembly (turret + 3
    objectives + objective_selector + focus),
  - a top **Microscope** Assembly that references Optics by a
    version-pinned sub-assembly link and adds camera + scintillator
    leaf slots, presenting as the Detector Role via presents_as,
  - one **Fixture** (microscope_at_2bm) that binds 8 concrete Assets across
    the union of leaf slots (the Microscope's 2 plus the Optics
    sub-assembly's 4; the three objectives share one OneOrMore slot),
  - one **Housing** Asset (Family Housing) that physically
    contains all 8 constituents (Asset.parent_id) and carries the Mount.

This is the Assembly + Fixture conversion that the flat-composition
predecessor of this scenario deferred. It is the first scenario to
exercise define_assembly (with a sub-assembly link) + register_fixture +
the Frame/Mount/install choreography end-to-end.

## register_fixture install precondition

register_fixture rejects a binding whose Asset is not currently installed
in some Mount. The conceptual model anchors the whole cluster on the
housing's Mount and lets the constituents inherit position; a pool-backed
deployment still gives each bound constituent a lightweight Mount so the
precondition passes. `install_existing_asset_into_fresh_mount` performs
that activate + Frame + Mount + install + drain on its own id pool.

## Naming

Constituents carry concise role names; vendor/spec identity (FLIR Oryx,
Crytur LuAG, Optique Peter, Mitutoyo) lives on the Model rows + settings
+ calibration operating points, not in the Asset names. The middle
objective is 2x (the physically-installed Mitutoyo M Plan Apo).

## Calibrations (4 revisions)

  - 3 magnification calibrations, one per objective:
    {objective_designation: "10x_Mitutoyo", energy: 25} -> 9.83 effective
    {objective_designation: "2x_Mitutoyo",  energy: 25} -> 2.0  nominal
    {objective_designation: "1.1x_Mitutoyo", energy: 25} -> 1.10 effective
  - 1 scintillator effective_thickness calibration:
    {scintillator_material: "LuAG", energy: 25} -> 100 micrometer

All AssertedSource (operator-attested from the vendor datasheet + Optique
Peter doc), status Provisional.
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
from cora.equipment.aggregates.assembly import (
    SlotCardinality,
    SlotName,
    SubAssemblyLink,
    TemplateSlot,
    load_assembly,
)
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.aggregates.fixture import SlotAssetBinding
from cora.equipment.aggregates.role import SEED_ROLE_DETECTOR_ID
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import bind as bind_add_asset_family
from cora.equipment.features.attach_asset_to_fixture import AttachAssetToFixture
from cora.equipment.features.attach_asset_to_fixture import bind as bind_attach_asset_to_fixture
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_assembly import bind as bind_define_assembly
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.equipment.features.register_fixture import RegisterFixture
from cora.equipment.features.register_fixture import bind as bind_register_fixture
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
from cora.infrastructure.adapters.in_memory_role_lookup import InMemoryRoleLookup
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_plan import bind as bind_define_plan
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.define_practice import bind as bind_define_practice
from cora.shared.identity import ActorId
from tests.integration._equipment_helpers import install_existing_asset_into_fresh_mount
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

# Facility hierarchy (scenario tag 420)
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000420501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000420a01")

# Family ids (deterministic uuid5 from the name).
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_OBJECTIVE_ID = family_stream_id(FamilyName("Objective"))
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))
_CAP_HOUSING_ID = family_stream_id(FamilyName("Housing"))

# Facility-install Device asset ids (scenario-supplied; the leaf detector
# parts that pre-exist under 2-BM before the microscope is composed).
_ASSET_CAMERA_ID = UUID("01900000-0000-7000-8000-000000420a11")
_ASSET_SCINTILLATOR_ID = UUID("01900000-0000-7000-8000-000000420a21")
_ASSET_FOCUS_ID = UUID("01900000-0000-7000-8000-000000420a31")

# Recipe ladder
_CAPABILITY_RECIPE_ID = UUID("01900000-0000-7000-8000-000000c0420e")

_DRAFT = "https://json-schema.org/draft/2020-12/schema"

_DEVICES = (
    DeviceSpec("Camera", _ASSET_CAMERA_ID, "Camera", _CAP_CAMERA_ID),
    DeviceSpec("Scintillator", _ASSET_SCINTILLATOR_ID, "Scintillator", _CAP_SCINTILLATOR_ID),
    DeviceSpec("Focus", _ASSET_FOCUS_ID, "LinearStage", _CAP_LINEAR_STAGE_ID),
)


def _id_queue() -> list[UUID]:
    """FixedIdGenerator queue: the exact facility prefix, then a generous
    block of anonymous ids. Scenario-specific aggregate ids are captured
    from handler return values (not hand-ordered), and the per-constituent
    Mount choreography runs on its own id pool inside the helper, so the
    tail just needs to be long enough."""
    return [
        *facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=_DEVICES),
        *[uuid4() for _ in range(400)],
    ]


# Facility-Family settings schemas (re-inlined per the schema-author
# anti-hook "DO NOT extract schemas before rule-of-three").
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
        "pixel_size": {"type": "number", "minimum": 0, "unit": {"system": "udunits", "code": "um"}},
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
        "thickness": {"type": "number", "minimum": 0, "unit": {"system": "udunits", "code": "um"}},
        "decay_time": {"type": "number", "minimum": 0, "unit": {"system": "udunits", "code": "us"}},
    },
    "required": ["thickness", "decay_time"],
}

_SCHEMA_LINEAR_STAGE: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "min_position": {"type": "number", "unit": {"system": "udunits", "code": "mm"}},
        "max_position": {"type": "number", "unit": {"system": "udunits", "code": "mm"}},
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

# PseudoAxis + Housing carry no operator-tunable settings.
_SCHEMA_EMPTY: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {},
    "required": [],
}

# Per-Asset settings (vendor datasheet + Optique Peter doc figures).
_SETTINGS_CAMERA: dict[str, Any] = {
    "sensor_width": 2448,
    "sensor_height": 2048,
    "pixel_size": 3.45,
    "bit_depth": 12,
}
_SETTINGS_SCINTILLATOR: dict[str, Any] = {"thickness": 100.0, "decay_time": 0.07}
_SETTINGS_FOCUS: dict[str, Any] = {
    "min_position": -5.0,
    "max_position": 5.0,
    "max_speed": 0.5,
    "encoder_resolution": 0.0005,
}
_SETTINGS_OBJECTIVE_10X: dict[str, Any] = {
    "magnification": 10.0,
    "numerical_aperture": 0.28,
    "focal_length": 20.0,
    "working_distance": 33.5,
}
_SETTINGS_OBJECTIVE_2X: dict[str, Any] = {
    "magnification": 2.0,
    "numerical_aperture": 0.055,
    "focal_length": 100.0,
    "working_distance": 34.0,
}
_SETTINGS_OBJECTIVE_1P1X: dict[str, Any] = {
    "magnification": 1.1,
    "numerical_aperture": 0.03,
    "focal_length": 200.0,
    "working_distance": 50.0,
}
# The objective selector is a sliding ball-screw stage (LinearStage), not a
# rotating turret: a Nanotec ST4118M1404-B over a 2 mm/rev ball screw with a
# Heidenhain ERO 1420 encoder, positions in mm (2-BM beamline components page).
# min/max span the outer objective positions (1.1x at -60.030, 10x at 58.640).
_SETTINGS_TURRET: dict[str, Any] = {
    "min_position": -60.030,
    "max_position": 58.640,
    "max_speed": 1.0,
    "encoder_resolution": 0.0016,
}


@pytest.mark.integration
async def test_microscope_deployment_plays_out_end_to_end(db_pool: asyncpg.Pool) -> None:
    """Compose the 2-BM detector as Microscope(Optics) + Fixture +
    Housing end-to-end: facility install, NEW Families, the Optics
    sub-assembly + Microscope assembly, the housing + constituent Assets,
    per-constituent Mount/install, the Fixture binding the 8-slot union +
    8 attaches, partition rule, 4 Calibrations, and a Method/Practice/Plan.
    Assert the Assembly/Fixture event streams, the containment tree, the
    fixture_id back-references, and the Calibrations."""
    role_lookup = InMemoryRoleLookup()
    role_lookup.register(SEED_ROLE_DETECTOR_ID, "Detector")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue(), role_lookup=role_lookup)
    actor = ActorId(_PRINCIPAL_ID)

    # ----- Facility install (APS -> 2-BM + camera/scintillator/focus) -----
    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    # ----- Facility-Family schemas + settings -----
    for cap_id, schema in (
        (_CAP_CAMERA_ID, _SCHEMA_CAMERA),
        (_CAP_SCINTILLATOR_ID, _SCHEMA_SCINTILLATOR),
        (_CAP_LINEAR_STAGE_ID, _SCHEMA_LINEAR_STAGE),
    ):
        await bind_update_family_settings_schema(deps)(
            UpdateFamilySettingsSchema(family_id=cap_id, settings_schema=schema),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    for asset_id, settings in (
        (_ASSET_CAMERA_ID, _SETTINGS_CAMERA),
        (_ASSET_SCINTILLATOR_ID, _SETTINGS_SCINTILLATOR),
        (_ASSET_FOCUS_ID, _SETTINGS_FOCUS),
    ):
        await bind_update_asset_settings(deps)(
            UpdateAssetSettings(asset_id=asset_id, settings_patch=settings),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- NEW Families (Objective, PseudoAxis, Housing) + schemas. The
    #       turret is a LinearStage (sliding ball-screw selector), so
    #       LinearStage (registered above) covers it and no RotaryStage
    #       Family is needed; the Detector Role is presented through the
    #       Microscope Assembly's presents_as, so no Imager presenter
    #       Family is defined either. -----
    for name in ("Objective", "PseudoAxis", "Housing"):
        await bind_define_family(deps)(
            DefineFamily(name=name, affordances=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    for cap_id, schema in (
        (_CAP_OBJECTIVE_ID, _SCHEMA_OBJECTIVE),
        (_CAP_PSEUDO_AXIS_ID, _SCHEMA_EMPTY),
    ):
        await bind_update_family_settings_schema(deps)(
            UpdateFamilySettingsSchema(family_id=cap_id, settings_schema=schema),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Optics sub-assembly (4 leaf slots; objectives is OneOrMore) -----
    def _slot(
        name: str, fam_id: UUID, cardinality: SlotCardinality = SlotCardinality.EXACTLY_1
    ) -> TemplateSlot:
        return TemplateSlot(
            slot_name=SlotName(name),
            required_family_ids=frozenset({fam_id}),
            cardinality=cardinality,
        )

    optics_id = await bind_define_assembly(deps)(
        DefineAssembly(
            name="Optics",
            presents_as=frozenset(),
            required_slots=frozenset(
                {
                    _slot("turret", _CAP_LINEAR_STAGE_ID),
                    # The three objectives differ only by magnification (a
                    # settings axis), so they share ONE OneOrMore slot rather
                    # than three Exactly1 slots. This keeps the Optics blueprint
                    # and its content_hash reusable across turret loadouts;
                    # per-magnification identity lives on the Asset (name +
                    # settings + calibration), not the slot.
                    _slot("objectives", _CAP_OBJECTIVE_ID, SlotCardinality.ONE_OR_MORE),
                    _slot("objective_selector", _CAP_PSEUDO_AXIS_ID),
                    _slot("focus", _CAP_LINEAR_STAGE_ID),
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    optics = await load_assembly(deps.event_store, optics_id)
    assert optics is not None
    assert optics.content_hash is not None

    # ----- Microscope assembly (sub-assembly link + camera/scintillator) -----
    microscope_id = await bind_define_assembly(deps)(
        DefineAssembly(
            name="Microscope",
            presents_as=frozenset({SEED_ROLE_DETECTOR_ID}),
            required_slots=frozenset(
                {
                    _slot("camera", _CAP_CAMERA_ID),
                    _slot("scintillator", _CAP_SCINTILLATOR_ID),
                }
            ),
            required_sub_assemblies=frozenset(
                {
                    SubAssemblyLink(
                        slot_name=SlotName("optics"),
                        sub_assembly_id=optics_id,
                        content_hash=optics.content_hash,
                    )
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Housing (Component, containment parent) -----
    housing_id = await bind_register_asset(deps)(
        RegisterAsset(name="Housing", tier=AssetTier.COMPONENT, parent_id=_2BM_UNIT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_asset_family(deps)(
        AddAssetFamily(asset_id=housing_id, family_id=_CAP_HOUSING_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Optics-cluster Assets (children of the housing) -----
    # The dict key is a local handle: turret/objective_selector equal their
    # blueprint slot name, while the three objectives all bind the single
    # OneOrMore `objectives` slot. The registered Asset carries a PascalCase
    # instance name per the facility Asset-instance-name convention.
    optics_assets: dict[str, UUID] = {}
    for key, asset_name, fam_id, settings in (
        ("turret", "Turret", _CAP_LINEAR_STAGE_ID, _SETTINGS_TURRET),
        ("objective_10x", "Objective_10x", _CAP_OBJECTIVE_ID, _SETTINGS_OBJECTIVE_10X),
        ("objective_2x", "Objective_2x", _CAP_OBJECTIVE_ID, _SETTINGS_OBJECTIVE_2X),
        ("objective_1.1x", "Objective_1.1x", _CAP_OBJECTIVE_ID, _SETTINGS_OBJECTIVE_1P1X),
        ("objective_selector", "Objective_Selector", _CAP_PSEUDO_AXIS_ID, None),
    ):
        aid = await bind_register_asset(deps)(
            RegisterAsset(name=asset_name, tier=AssetTier.DEVICE, parent_id=housing_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        optics_assets[key] = aid
        await bind_add_asset_family(deps)(
            AddAssetFamily(asset_id=aid, family_id=fam_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        if settings is not None:
            await bind_update_asset_settings(deps)(
                UpdateAssetSettings(asset_id=aid, settings_patch=settings),
                principal_id=_PRINCIPAL_ID,
                correlation_id=_CORRELATION_ID,
            )

    # ----- Re-parent the facility leaf Assets under the housing -----
    for asset_id in (_ASSET_CAMERA_ID, _ASSET_SCINTILLATOR_ID, _ASSET_FOCUS_ID):
        await bind_relocate_asset(deps)(
            RelocateAsset(
                asset_id=asset_id,
                to_parent_id=housing_id,
                reason="Microscope composition lock landed",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Install every bound constituent in a lightweight Mount so
    #       register_fixture's install precondition passes (the housing
    #       is the conceptual anchor; per-constituent Mounts are the
    #       pool-backed approximation). The helper runs on its own id
    #       pool: activate + Frame + Mount + install + drain. -----
    # slot_name -> asset_id pairs as a LIST (not a dict): the three objectives
    # all bind the single OneOrMore `objectives` slot, so that name repeats.
    bound: list[tuple[str, UUID]] = [
        ("camera", _ASSET_CAMERA_ID),
        ("scintillator", _ASSET_SCINTILLATOR_ID),
        ("turret", optics_assets["turret"]),
        ("objectives", optics_assets["objective_10x"]),
        ("objectives", optics_assets["objective_2x"]),
        ("objectives", optics_assets["objective_1.1x"]),
        ("objective_selector", optics_assets["objective_selector"]),
        ("focus", _ASSET_FOCUS_ID),
    ]
    for i, (slot_name, asset_id) in enumerate(bound):
        await install_existing_asset_into_fresh_mount(
            db_pool, now=_NOW, asset_id=asset_id, slot_code=f"microscope_{slot_name}_{i}"
        )

    # ----- Register the Microscope Fixture (binds the 8-slot union) -----
    fixture_id = await bind_register_fixture(deps)(
        RegisterFixture(
            assembly_id=microscope_id,
            slot_asset_bindings=frozenset(
                SlotAssetBinding(slot_name=slot_name, asset_id=asset_id)
                for slot_name, asset_id in bound
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Attach each bound Asset (sets its fixture_id back-reference) -----
    for _, asset_id in bound:
        await bind_attach_asset_to_fixture(deps)(
            AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- 4 Calibrations + AssertedSource revisions -----
    cal_ids: list[UUID] = []
    rev_ids: list[UUID] = []
    for target_id, quantity, op_point, value, description in (
        (
            optics_assets["objective_10x"],
            CalibrationQuantity.MAGNIFICATION,
            {"objective_designation": "10x_Mitutoyo", "energy": 25.0},
            {"magnification": 9.83},
            (
                "Initial AssertedSource revision. Mitutoyo M Plan Apo 10x; effective "
                "9.83x derived from Optique Peter doc pixel size 0.351 um / Oryx 3.45 um pitch."
            ),
        ),
        (
            optics_assets["objective_2x"],
            CalibrationQuantity.MAGNIFICATION,
            {"objective_designation": "2x_Mitutoyo", "energy": 25.0},
            {"magnification": 2.0},
            (
                "Initial AssertedSource revision. Mitutoyo M Plan Apo 2x; nominal 2.0x "
                "pending a measured re-calibration."
            ),
        ),
        (
            optics_assets["objective_1.1x"],
            CalibrationQuantity.MAGNIFICATION,
            {"objective_designation": "1.1x_Mitutoyo", "energy": 25.0},
            {"magnification": 1.10},
            (
                "Initial AssertedSource revision. Mitutoyo M Plan Apo 1.1x; effective "
                "1.10x derived from Optique Peter doc pixel size 3.126 um / Oryx 3.45 um pitch."
            ),
        ),
        (
            _ASSET_SCINTILLATOR_ID,
            CalibrationQuantity.EFFECTIVE_THICKNESS,
            {"scintillator_material": "LuAG", "energy": 25.0},
            {"effective_thickness": 100.0},
            (
                "Initial AssertedSource revision. Source: scintillator.settings.thickness = "
                "100 um (Crytur LuAG:Ce). Supersede with a measured attenuation-length run."
            ),
        ),
    ):
        cal_id = await bind_define_calibration(deps)(
            DefineCalibration(
                target_id=target_id,
                quantity=quantity,
                operating_point=op_point,
                description=description,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        cal_ids.append(cal_id)
        rev_id = await bind_append_calibration_revision(deps)(
            AppendCalibrationRevision(
                calibration_id=cal_id,
                value=value,
                status=CalibrationStatus.PROVISIONAL,
                source=AssertedSource(asserted_by=actor),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        rev_ids.append(rev_id)

    # ----- LookupTable partition rule on objective_selector -----
    # The calibration reference is a placeholder: the runtime evaluator
    # expects a revision carrying the index-to-angle table (a
    # CalibrationQuantity the closed catalog does not have yet), so a real
    # magnification calibration + revision id pair satisfies construction
    # without inventing a sentinel.
    await bind_update_asset_partition_rule(deps)(
        UpdateAssetPartitionRule(
            asset_id=optics_assets["objective_selector"],
            partition_rule=LookupTable(
                calibration_id=cal_ids[0],
                calibration_revision_id=rev_ids[0],
                invertible=False,
                readback_aggregator_kind=ReadbackAggregatorKind.IDENTITY,
                unit_in="index",
                unit_out="mm",
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Minimal Recipe ladder (Plan binds asset_ids, no wires) -----
    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_RECIPE_ID,
        code="cora.capability.microscope_acquisition",
        name="MicroscopeAcquisition",
    )
    method_id = await bind_define_method(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_RECIPE_ID,
            name="microscope_image_acquisition",
            # The imaging (Detector Role) capability comes from the
            # Microscope Assembly's presents_as, declared via
            # needed_assembly_ids; needed_family_ids names the asset-level
            # parts the bound constituents directly provide.
            needed_family_ids=frozenset(
                {_CAP_CAMERA_ID, _CAP_SCINTILLATOR_ID, _CAP_PSEUDO_AXIS_ID}
            ),
            needed_assembly_ids=frozenset({microscope_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await bind_define_practice(deps)(
        DefinePractice(name="2BM_microscope_practice", method_id=method_id, site_id=_APS_SITE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_id = await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_microscope_plan",
            practice_id=practice_id,
            asset_ids=frozenset(asset_id for _, asset_id in bound),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ===== Assertions =====

    # Optics sub-assembly stream: AssemblyDefined with 4 leaf slots
    # (turret, objectives [OneOrMore], objective_selector, focus).
    optics_events, _ = await deps.event_store.load("Assembly", optics_id)
    assert [e.event_type for e in optics_events] == ["AssemblyDefined"]
    assert len(optics_events[0].payload["required_slots"]) == 4
    assert optics_events[0].payload["presents_as"] == []

    # Microscope stream: AssemblyDefined with the sub-assembly link + 2 leaves.
    micro_events, _ = await deps.event_store.load("Assembly", microscope_id)
    assert [e.event_type for e in micro_events] == ["AssemblyDefined"]
    micro_payload = micro_events[0].payload
    assert len(micro_payload["required_slots"]) == 2
    assert len(micro_payload["required_sub_assemblies"]) == 1
    assert micro_payload["required_sub_assemblies"][0]["sub_assembly_id"] == str(optics_id)
    assert micro_payload["required_sub_assemblies"][0]["content_hash"] == optics.content_hash
    assert micro_payload["presents_as"] == [str(SEED_ROLE_DETECTOR_ID)]

    # Fixture stream: FixtureRegistered binding 8 Assets across 6 slot names
    # (the `objectives` OneOrMore slot carries 3 of the 8 bindings).
    fixture_events, _ = await deps.event_store.load("Fixture", fixture_id)
    assert [e.event_type for e in fixture_events] == ["FixtureRegistered"]
    bindings = fixture_events[0].payload["slot_asset_bindings"]
    assert len(bindings) == 8
    bound_slot_names = {b["slot_name"] for b in bindings}
    assert bound_slot_names == {slot for slot, _ in bound}
    assert sum(1 for b in bindings if b["slot_name"] == "objectives") == 3

    # Containment: every constituent's parent is the housing; the housing's
    # parent is the 2-BM Unit. Each bound Asset carries AssetAttachedToFixture.
    housing_events, _ = await deps.event_store.load("Asset", housing_id)
    assert housing_events[0].payload["parent_id"] == str(_2BM_UNIT_ID)
    # the 5 optics-cluster Assets are children of the housing (containment).
    for name, asset_id in optics_assets.items():
        events, _ = await deps.event_store.load("Asset", asset_id)
        assert events[0].payload["parent_id"] == str(housing_id), f"{name}: expected housing parent"
    for slot_name, asset_id in bound:
        events, _ = await deps.event_store.load("Asset", asset_id)
        types = [e.event_type for e in events]
        assert "AssetAttachedToFixture" in types, f"{slot_name}: expected fixture attach"
        # the relocated facility Assets carry AssetRelocated under the housing
        if slot_name in ("camera", "scintillator", "focus"):
            assert "AssetRelocated" in types, f"{slot_name}: expected re-parent"

    # objective_selector carries the partition rule + no settings.
    sel_events, _ = await deps.event_store.load("Asset", optics_assets["objective_selector"])
    sel_types = [e.event_type for e in sel_events]
    assert "AssetPartitionRuleUpdated" in sel_types
    assert "AssetSettingsUpdated" not in sel_types

    # 4 Calibrations, one revision each.
    for cal_id in cal_ids:
        events, _ = await deps.event_store.load("Calibration", cal_id)
        assert [e.event_type for e in events] == [
            "CalibrationDefined",
            "CalibrationRevisionAppended",
        ]

    # Plan carries no wires (the presenter-brokering is dissolved).
    plan_events, _ = await deps.event_store.load("Plan", plan_id)
    assert not [e for e in plan_events if e.event_type == "PlanWireAdded"]
