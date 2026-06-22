"""Energy -> position curves for the 2-BM energy-driven axes.

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment, Calibration

Models HOW the 2-BM axes that move with beam energy depend on it. The
staff-authored docs2bm "Energy-change IOC" page is the ground truth: a
change of energy is a DISCRETE coordinated move (saved per-energy
positions, store_0, driven together to a configured set of energies). The
per-energy axes are the DMM Bragg arms (dmm_us_arm/dmm_ds_arm) plus the M2
vertical offset compensator (dmm_m2_y), the B-station sample-slit vertical
pair (b_slit_top/b_slit_bot) tracking the resulting beam walk, the diagnostic
flag (energy_move_flag) raised to an energy-dependent height in Mono, and the
mirror coating-stripe reach (m1_horizontal / 2bma:m3) - the one axis whose
ACTIVE sweep is in Pink, held at one stripe in Mono (MIRROR-1, MODE-3).
crystal2_z (M2 Z, 2bma:m8) is a setup translation the IOC does NOT drive, so
it carries no curve.

CORA models each per-axis relationship as a curve (a LookupTable backed by
an energy_position_curve Calibration) interpolating the discrete saved
points. The values are the real saved store_0 positions (ENERGY-1/2,
FLAG-1); each axis carries a Mono curve (operating_point beam_mode=mono)
and a separate Pink curve (beam_mode=pink), where in Pink the axes are
parked at constants (the DMM is bypassed, so there is no beam-walk to
track). The Pink curves are recorded here as calibration data; the
mode-switch operation that selects between them is the Pink-mode work
(MODE-2/3).

invertibility is per-axis and honest: the Bragg arms and M2Y are
monotonic in energy (invertible=True); the slit blades are NOT (the
aperture is held constant at 20 mm and the centre walks non-monotonically,
a step pattern), the flag Y is flat at the top of its range, and the mirror
stripe reach is constant in Mono (held at stripe a), so all three are
invertible=False; every parked Pink curve is constant, so it is data
only and carries no rule.

The constant slit aperture (20 mm) and the centre-tracks-the-beam-walk view
are also modelled as derived axes: SampleSlit_VerticalCenter =
MidRange(top, bot) and SampleSlit_VerticalAperture = Difference(top, bot),
each an Aggregation rule over the two blades. Aggregation is one-way
(computed from constituents), so these are read-only views, not drivers. The
rules declare the relationship here; the constituent port wiring that binds
the two specific blades (the hexapod-pose pattern) is deferred with the rest
of the per-facet conduct wiring.

## What this proves (and what it does not)

It proves the per-axis chain holds together across heterogeneous axes (arm
angles in deg, slit / offset / flag positions in mm): a PseudoAxis facet
parented to the physical device, backed by a real energy_position_curve
revision, carrying a keV -> position LookupTable, with per-axis invertible
honesty and a sibling Pink curve.

It also records the DMM insert/bypass state (MODE-2): in Mono the DMM is
inserted, in Pink retracted. Because that state is two-state and MODE-keyed
(not per-energy), it is NOT a curve but a closed-enum Monochromator setting
(dmm_insertion: inserted|retracted), modelled with the Table.axis_layout
pattern (Family settings_schema + Asset.settings). The three DMM Y motors and
their 0 / -10 mm targets are documentary in beamline.yaml.

It does NOT drive motion: it sets up the per-axis curves but does not conduct
them. The interpolation kernel (eval_lookup_table) is wired and proven in
test_pseudoaxis_roundtrip.py, but a beamline move additionally needs the
per-facet constituent wiring and live EPICS dispatch. This scenario records the
DMM insert/bypass STATE but does NOT model the coordinating energy-setting
operation (test_2bm_energy_setting.py) or the coordinated Mono<->Pink mode-switch
MOVE that drives it (the deferred beam_mode_change, MODE-3/MIRROR-1). This is an
intentional-completeness shape model of the per-device mapping.

## Asset stack

```
2-BM (Unit)
+-- FrontEndDrive (Device)               MotionController
    +-- Monochromator (Device)           Monochromator  (driven by FrontEndDrive)
    |   +-- Monochromator_BraggArmUpstream     PseudoAxis  (energy -> dmm_us_arm deg)
    |   +-- Monochromator_BraggArmDownstream   PseudoAxis  (energy -> dmm_ds_arm deg)
    |   +-- Monochromator_M2Y                  PseudoAxis  (energy -> dmm_m2_y mm)
    +-- SampleSlit (Device)              Slit           (driven by FrontEndDrive)
    |   +-- SampleSlit_VerticalTop             PseudoAxis  (energy -> b_slit_top mm)
    |   +-- SampleSlit_VerticalBottom          PseudoAxis  (energy -> b_slit_bot mm)
    |   +-- SampleSlit_VerticalCenter          PseudoAxis  (MidRange(top, bot), derived)
    |   +-- SampleSlit_VerticalAperture        PseudoAxis  (Difference(top, bot), derived)
    +-- DiagnosticFlag (Device)          Screen         (driven by FrontEndDrive)
    |   +-- DiagnosticFlag_Y                   PseudoAxis  (energy -> flag Y mm)
    +-- Mirror (Device)                  Mirror         (driven by FrontEndDrive)
        +-- Mirror_StripeReachX                PseudoAxis  (Pink swept, Mono held)
```
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.calibration.aggregates.calibration import AssertedSource, CalibrationStatus
from cora.calibration.features.append_calibration_revision import AppendCalibrationRevision
from cora.calibration.features.append_calibration_revision import (
    bind as bind_append_calibration_revision,
)
from cora.calibration.features.define_calibration import DefineCalibration
from cora.calibration.features.define_calibration import bind as bind_define_calibration
from cora.calibration.quantities import CalibrationQuantity
from cora.equipment.aggregates._partition_rule import (
    Aggregation,
    AggregatorKind,
    ExtrapolationKind,
    InterpolationKind,
    LookupTable,
    ReadbackAggregatorKind,
)
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import bind as bind_add_asset_family
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
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
from cora.shared.identity import ActorId
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._facility_fixture import (
    DeviceSpec,
    facility_id_prefix,
    install_aps_unit,
    operator_for,
)

_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000004b0cc1")

# Scenario tag: 4b0 (energy -> position curves).

_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-0000004b0a01")

# Family ids (deterministic uuid5 from the name). MotionController +
# Monochromator + Slit + Screen + Mirror are defined by the install;
# PseudoAxis by this scenario.
_CAP_MOTION_CONTROLLER_ID = family_stream_id(FamilyName("MotionController"))
_CAP_MONOCHROMATOR_ID = family_stream_id(FamilyName("Monochromator"))
_CAP_SLIT_ID = family_stream_id(FamilyName("Slit"))
_CAP_SCREEN_ID = family_stream_id(FamilyName("Screen"))
_CAP_MIRROR_ID = family_stream_id(FamilyName("Mirror"))
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))

# Controller registered first so each device's controller_id back-reference
# targets an already-registered Asset stream.
_FRONTENDDRIVE_ID = UUID("01900000-0000-7000-8000-0000004b0a31")
_MONOCHROMATOR_ID = UUID("01900000-0000-7000-8000-0000004b0a12")
_SAMPLE_SLIT_ID = UUID("01900000-0000-7000-8000-0000004b0a14")
_DIAGNOSTIC_FLAG_ID = UUID("01900000-0000-7000-8000-0000004b0a16")
_MIRROR_ID = UUID("01900000-0000-7000-8000-0000004b0a18")

_DEVICES = (
    DeviceSpec("FrontEndDrive", _FRONTENDDRIVE_ID, "MotionController", _CAP_MOTION_CONTROLLER_ID),
    DeviceSpec(
        "Monochromator",
        _MONOCHROMATOR_ID,
        "Monochromator",
        _CAP_MONOCHROMATOR_ID,
        controller_id=_FRONTENDDRIVE_ID,
    ),
    DeviceSpec(
        "SampleSlit", _SAMPLE_SLIT_ID, "Slit", _CAP_SLIT_ID, controller_id=_FRONTENDDRIVE_ID
    ),
    DeviceSpec(
        "DiagnosticFlag",
        _DIAGNOSTIC_FLAG_ID,
        "Screen",
        _CAP_SCREEN_ID,
        controller_id=_FRONTENDDRIVE_ID,
    ),
    DeviceSpec(
        "Mirror",
        _MIRROR_ID,
        "Mirror",
        _CAP_MIRROR_ID,
        controller_id=_FRONTENDDRIVE_ID,
    ),
)


# Real saved store_0 positions (energy2bm.json, ENERGY-1/2/FLAG-1). Each axis
# carries a Mono curve (6 configured energies) and a Pink curve (4 configured
# energies, parked constant). invertible is the Mono-curve property: monotonic
# arms / M2Y are invertible; the non-monotonic slit blades and the flat-topped
# flag are not. Pink curves are constant data and carry no rule.
# (facet_name, parent_id, axis_designation, unit_out, mono_points, pink_points, invertible)
_P = list[dict[str, float]]
_AXES: tuple[tuple[str, UUID, str, str, _P, _P, bool], ...] = (
    (
        "Monochromator_BraggArmUpstream",
        _MONOCHROMATOR_ID,
        "dmm_us_arm",
        "deg",
        [
            {"energy": 13.374, "position": 1.131},
            {"energy": 13.574, "position": 1.081},
            {"energy": 18.0, "position": 0.822},
            {"energy": 20.0, "position": 0.726},
            {"energy": 25.0, "position": 0.57725},
            {"energy": 25.584, "position": 0.561},
        ],
        [
            {"energy": 30.0, "position": 0.740},
            {"energy": 40.0, "position": 0.740},
            {"energy": 50.0, "position": 0.740},
            {"energy": 60.0, "position": 0.740},
        ],
        True,
    ),
    (
        "Monochromator_BraggArmDownstream",
        _MONOCHROMATOR_ID,
        "dmm_ds_arm",
        "deg",
        [
            {"energy": 13.374, "position": 1.133},
            {"energy": 13.574, "position": 1.083},
            {"energy": 18.0, "position": 0.824},
            {"energy": 20.0, "position": 0.737},
            {"energy": 25.0, "position": 0.58825},
            {"energy": 25.584, "position": 0.572},
        ],
        [
            {"energy": 30.0, "position": 0.751},
            {"energy": 40.0, "position": 0.751},
            {"energy": 50.0, "position": 0.751},
            {"energy": 60.0, "position": 0.751},
        ],
        True,
    ),
    (
        "Monochromator_M2Y",
        _MONOCHROMATOR_ID,
        "dmm_m2_y",
        "mm",
        [
            {"energy": 13.374, "position": 25.1201075},
            {"energy": 13.574, "position": 24.3201075},
            {"energy": 18.0, "position": 18.820045},
            {"energy": 20.0, "position": 17.020045},
            {"energy": 25.0, "position": 14.220045},
            {"energy": 25.584, "position": 13.920045},
        ],
        [
            {"energy": 30.0, "position": 17.020045},
            {"energy": 40.0, "position": 17.020045},
            {"energy": 50.0, "position": 17.020045},
            {"energy": 60.0, "position": 17.020045},
        ],
        True,
    ),
    (
        "SampleSlit_VerticalTop",
        _SAMPLE_SLIT_ID,
        "b_slit_top",
        "mm",
        [
            {"energy": 13.374, "position": 28.804575},
            {"energy": 13.574, "position": 28.804575},
            {"energy": 18.0, "position": 28.804575},
            {"energy": 20.0, "position": 31.144575},
            {"energy": 25.0, "position": 26.23},
            {"energy": 25.584, "position": 26.28},
        ],
        [
            {"energy": 30.0, "position": 10.0},
            {"energy": 40.0, "position": 10.0},
            {"energy": 50.0, "position": 10.0},
            {"energy": 60.0, "position": 10.0},
        ],
        False,
    ),
    (
        "SampleSlit_VerticalBottom",
        _SAMPLE_SLIT_ID,
        "b_slit_bot",
        "mm",
        [
            {"energy": 13.374, "position": 8.804575},
            {"energy": 13.574, "position": 8.804575},
            {"energy": 18.0, "position": 8.804575},
            {"energy": 20.0, "position": 11.144575},
            {"energy": 25.0, "position": 6.23},
            {"energy": 25.584, "position": 6.28},
        ],
        [
            {"energy": 30.0, "position": -10.0},
            {"energy": 40.0, "position": -10.0},
            {"energy": 50.0, "position": -10.0},
            {"energy": 60.0, "position": -10.0},
        ],
        False,
    ),
    (
        "DiagnosticFlag_Y",
        _DIAGNOSTIC_FLAG_ID,
        "energy_move_flag",
        "mm",
        [
            {"energy": 13.374, "position": 23.0},
            {"energy": 13.574, "position": 22.0},
            {"energy": 18.0, "position": 17.0},
            {"energy": 20.0, "position": 15.0},
            {"energy": 25.0, "position": 12.0},
            {"energy": 25.584, "position": 12.0},
        ],
        [
            {"energy": 30.0, "position": 0.0},
            {"energy": 40.0, "position": 0.0},
            {"energy": 50.0, "position": 0.0},
            {"energy": 60.0, "position": 0.0},
        ],
        False,
    ),
    (
        # Mirror coating-stripe reach (m1_horizontal / 2bma:m3): the one
        # energy-driven axis whose ACTIVE behaviour is in Pink, not Mono. In Mono
        # the mirror is held at one stripe (a, Pt), so the Mono curve is constant
        # (m3 = 1.0); in Pink the IOC sweeps m3 per energy to reach the stripe
        # whose multilayer cutoff matches (a/b/c/d at 3.039/13/39/49). Same
        # Mono-active / Pink-sibling convention as the other axes; the named
        # stripe-to-position map is documentary in beamline.yaml (MIRROR-1, MODE-3).
        # invertible=False: the active Mono curve is constant (no energy to
        # recover), so it reconstructs readback from the single motor (Identity).
        "Mirror_StripeReachX",
        _MIRROR_ID,
        "m1_horizontal",
        "mm",
        [
            {"energy": 13.374, "position": 1.0},
            {"energy": 13.574, "position": 1.0},
            {"energy": 18.0, "position": 1.0},
            {"energy": 20.0, "position": 1.0},
            {"energy": 25.0, "position": 1.0},
            {"energy": 25.584, "position": 1.0},
        ],
        [
            {"energy": 30.0, "position": 3.039},
            {"energy": 40.0, "position": 13.0},
            {"energy": 50.0, "position": 39.0},
            {"energy": 60.0, "position": 49.0},
        ],
        False,
    ),
)

# The Monochromator settings schema (the JSON-Schema subset; strictness is
# injected at validation, mirroring Table.axis_layout). dmm_insertion is the
# two-state mode primitive: in Mono the DMM is inserted (Bragg-selecting), in
# Pink it is retracted (the beam passes straight through). The three DMM Y motors
# (2bma:m26/m27/m29) drive together to 0 (in) or -10 mm (out) within the one
# coordinated energy-change move (MODE-2). Their numeric targets are documentary
# in beamline.yaml (an array-of-objects motor map is outside CORA's settings
# subset, which has no `items`); the operator-facing state is this closed enum.
_SCHEMA_MONOCHROMATOR: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "dmm_insertion": {"type": "string", "enum": ["inserted", "retracted"]},
    },
    "required": ["dmm_insertion"],
}


def _id_queue() -> list[UUID]:
    """FixedIdGenerator queue: the facility prefix (Unit + 4 devices + their
    Families) plus a generous anonymous tail. Facet / calibration / revision
    ids are captured from handler return values, so the tail just needs to be
    long enough for the per-axis Mono + Pink calibration setup."""
    return [
        *facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=_DEVICES),
        *[uuid4() for _ in range(100)],
    ]


@pytest.mark.integration
async def test_energy_driven_axes_carry_energy_curves(db_pool: asyncpg.Pool) -> None:
    """Give each energy-driven axis a PseudoAxis facet backed by a real Mono
    energy_position_curve (the active LookupTable, per-axis invertible) plus a
    sibling Pink curve (parked-constant calibration data). Assert each facet
    stream, the Mono rule payload, and that both Mono and Pink calibrations
    exist keyed by beam_mode."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())
    actor = ActorId(_PRINCIPAL_ID)

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    # ----- PseudoAxis Family (the facets' Family) -----
    await bind_define_family(deps)(
        DefineFamily(name="PseudoAxis", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    facet_ids: dict[str, UUID] = {}
    mono_cal_ids: dict[str, UUID] = {}
    mono_rev_ids: dict[str, UUID] = {}
    pink_cal_ids: dict[str, UUID] = {}

    async def _curve(
        facet_id: UUID, axis_designation: str, unit_out: str, beam_mode: str, points: _P
    ) -> tuple[UUID, UUID]:
        cal_id = await bind_define_calibration(deps)(
            DefineCalibration(
                target_id=facet_id,
                quantity=CalibrationQuantity.ENERGY_POSITION_CURVE,
                operating_point={"axis_designation": axis_designation, "beam_mode": beam_mode},
                description=(
                    f"Saved store_0 energy -> position curve for {axis_designation} "
                    f"({beam_mode} mode), from energy2bm.json (ENERGY-1/2/FLAG-1)."
                ),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        rev_id = await bind_append_calibration_revision(deps)(
            AppendCalibrationRevision(
                calibration_id=cal_id,
                value={"points": points, "position_unit": unit_out},
                status=CalibrationStatus.VERIFIED,
                source=AssertedSource(asserted_by=actor),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        return cal_id, rev_id

    for facet_name, parent_id, axis_designation, unit_out, mono, pink, invertible in _AXES:
        facet_id = await bind_register_asset(deps)(
            RegisterAsset(name=facet_name, tier=AssetTier.DEVICE, parent_id=parent_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        facet_ids[facet_name] = facet_id
        await bind_add_asset_family(deps)(
            AddAssetFamily(asset_id=facet_id, family_id=_CAP_PSEUDO_AXIS_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        # Mono curve: the active partition rule (per-axis invertible honesty).
        mono_cal_id, mono_rev_id = await _curve(facet_id, axis_designation, unit_out, "mono", mono)
        mono_cal_ids[facet_name] = mono_cal_id
        mono_rev_ids[facet_name] = mono_rev_id
        await bind_update_asset_partition_rule(deps)(
            UpdateAssetPartitionRule(
                asset_id=facet_id,
                partition_rule=LookupTable(
                    calibration_id=mono_cal_id,
                    calibration_revision_id=mono_rev_id,
                    interpolation_kind=InterpolationKind.LINEAR,
                    # ERROR, not CLAMP: an energy past the lowest / highest
                    # calibrated point is refused, not silently driven to the
                    # endpoint position. Staff-confirmed (ENERGY-4): the IOC
                    # refuses any energy outside the mode's calibrated range,
                    # and the inter-mode band (25.584, 30.0) keV is not
                    # bridgeable by interpolation.
                    extrapolation_kind=ExtrapolationKind.ERROR,
                    # Per-axis honesty: the Bragg arms + M2Y are monotonic in
                    # energy (invertible); the non-monotonic slit blades and the
                    # flat-topped flag are not, so they reconstruct readback from
                    # the single constituent motor (Identity).
                    invertible=invertible,
                    readback_aggregator_kind=(
                        None if invertible else ReadbackAggregatorKind.IDENTITY
                    ),
                    unit_in="keV",
                    unit_out=unit_out,
                ),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        # Pink curve: parked-constant calibration data, keyed beam_mode=pink.
        # Not wired as a rule (the facet's rule is the Mono curve); the Mono<->Pink
        # mode switch that selects between them is the Pink-mode work (MODE-2/3).
        pink_cal_id, _pink_rev_id = await _curve(facet_id, axis_designation, unit_out, "pink", pink)
        pink_cal_ids[facet_name] = pink_cal_id

    # ----- Derived slit centre + aperture (Aggregation readback views) -----
    #
    # The two blade curves are the energy drivers; the slit's centre and
    # aperture are derived from them: centre = MidRange(top, bot) is the
    # beam-walk trajectory, aperture = Difference(top, bot) reads the constant
    # 20 mm gap. Aggregation is one-way (computed from constituents), so these
    # are read-only views, not drivers. The rule declares the relationship; the
    # constituent port wiring binding the two specific blades (the hexapod-pose
    # pattern) is deferred with the rest of the per-facet conduct wiring.
    derived: dict[str, AggregatorKind] = {
        "SampleSlit_VerticalCenter": AggregatorKind.MID_RANGE,
        "SampleSlit_VerticalAperture": AggregatorKind.DIFFERENCE,
    }
    for facet_name, aggregator_kind in derived.items():
        facet_id = await bind_register_asset(deps)(
            RegisterAsset(name=facet_name, tier=AssetTier.DEVICE, parent_id=_SAMPLE_SLIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        facet_ids[facet_name] = facet_id
        await bind_add_asset_family(deps)(
            AddAssetFamily(asset_id=facet_id, family_id=_CAP_PSEUDO_AXIS_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        await bind_update_asset_partition_rule(deps)(
            UpdateAssetPartitionRule(
                asset_id=facet_id,
                partition_rule=Aggregation(aggregator_kind=aggregator_kind, constituent_count=2),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- DMM insert/bypass state (MODE-2) -----
    #
    # Mono <-> Pink is realized physically by the DMM moving in or out of the
    # beam: the three DMM Y motors drive together to 0 (in, Mono) or -10 mm (out,
    # Pink) inside the one coordinated energy-change move, with no sequencing and
    # no interlock (MODE-2). This is a two-state, MODE-keyed value, NOT a
    # per-energy curve, so it is modeled as a closed-enum Monochromator setting
    # (the Table.axis_layout pattern), not a PseudoAxis facet. The coordinated
    # move that drives it is the deferred beam_mode_change operation.
    await bind_update_family_settings_schema(deps)(
        UpdateFamilySettingsSchema(
            family_id=_CAP_MONOCHROMATOR_ID, settings_schema=_SCHEMA_MONOCHROMATOR
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_update_asset_settings(deps)(
        UpdateAssetSettings(
            asset_id=_MONOCHROMATOR_ID, settings_patch={"dmm_insertion": "inserted"}
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ===== Assertions =====

    for facet_name, parent_id, axis_designation, unit_out, _mono, _pink, invertible in _AXES:
        facet_id = facet_ids[facet_name]
        facet_events, _ = await deps.event_store.load("Asset", facet_id)
        assert [e.event_type for e in facet_events] == [
            "AssetRegistered",
            "AssetFamilyAdded",
            "AssetPartitionRuleUpdated",
        ], f"{facet_name}: unexpected event sequence"
        assert facet_events[0].payload["parent_id"] == str(parent_id), f"{facet_name}: wrong parent"
        assert facet_events[1].payload["family_id"] == str(_CAP_PSEUDO_AXIS_ID)

        rule = facet_events[2].payload["partition_rule"]
        assert rule["kind"] == "LookupTable", f"{facet_name}: wrong rule kind"
        assert rule["calibration_id"] == str(mono_cal_ids[facet_name])
        assert rule["calibration_revision_id"] == str(mono_rev_ids[facet_name])
        assert rule["unit_in"] == "keV"
        assert rule["unit_out"] == unit_out
        assert rule["invertible"] is invertible, f"{facet_name}: wrong invertible"
        assert rule["extrapolation_kind"] == "Error"

        # Mono calibration: the active curve, keyed beam_mode=mono.
        mono_events, _ = await deps.event_store.load("Calibration", mono_cal_ids[facet_name])
        assert [e.event_type for e in mono_events] == [
            "CalibrationDefined",
            "CalibrationRevisionAppended",
        ], f"{facet_name}: unexpected Mono calibration sequence"
        assert mono_events[0].payload["quantity"] == CalibrationQuantity.ENERGY_POSITION_CURVE.value
        assert mono_events[0].payload["target_id"] == str(facet_id)
        assert mono_events[0].payload["operating_point"] == {
            "axis_designation": axis_designation,
            "beam_mode": "mono",
        }

        # Pink calibration: the parked-constant sibling, keyed beam_mode=pink.
        pink_events, _ = await deps.event_store.load("Calibration", pink_cal_ids[facet_name])
        assert [e.event_type for e in pink_events] == [
            "CalibrationDefined",
            "CalibrationRevisionAppended",
        ], f"{facet_name}: unexpected Pink calibration sequence"
        assert pink_events[0].payload["operating_point"] == {
            "axis_designation": axis_designation,
            "beam_mode": "pink",
        }

    # Derived slit centre + aperture: Aggregation readback views over the blades.
    for facet_name, aggregator_kind in derived.items():
        facet_id = facet_ids[facet_name]
        facet_events, _ = await deps.event_store.load("Asset", facet_id)
        assert [e.event_type for e in facet_events] == [
            "AssetRegistered",
            "AssetFamilyAdded",
            "AssetPartitionRuleUpdated",
        ], f"{facet_name}: unexpected event sequence"
        assert facet_events[0].payload["parent_id"] == str(_SAMPLE_SLIT_ID)
        rule = facet_events[2].payload["partition_rule"]
        assert rule["kind"] == "Aggregation", f"{facet_name}: wrong rule kind"
        assert rule["aggregator_kind"] == aggregator_kind.value
        assert rule["constituent_count"] == 2

    # DMM insert/bypass (MODE-2): the Monochromator Family carries the
    # dmm_insertion enum schema, and the Monochromator Asset carries the
    # mode-keyed two-state setting (currently inserted, the Mono state).
    mono_family_events, _ = await deps.event_store.load("Family", _CAP_MONOCHROMATOR_ID)
    schema_events = [e for e in mono_family_events if e.event_type == "FamilySettingsSchemaUpdated"]
    assert schema_events, "Monochromator Family missing settings-schema update"
    assert schema_events[-1].payload["settings_schema"]["properties"]["dmm_insertion"]["enum"] == [
        "inserted",
        "retracted",
    ]
    mono_asset_events, _ = await deps.event_store.load("Asset", _MONOCHROMATOR_ID)
    settings_events = [e for e in mono_asset_events if e.event_type == "AssetSettingsUpdated"]
    assert settings_events, "Monochromator missing dmm_insertion setting"
    assert settings_events[-1].payload["settings"]["dmm_insertion"] == "inserted"
