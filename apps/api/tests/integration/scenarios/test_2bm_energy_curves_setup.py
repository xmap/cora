"""Energy -> position curves for the 2-BM energy-driven optic axes.

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment, Calibration

Models HOW the 2-BM optics that move with beam energy depend on it. The
staff-authored docs2bm "Energy-change IOC" page is the ground truth: a
change of energy is a DISCRETE coordinated move (saved per-energy
positions, store_0, driven together to a configured set of energies), and
the per-energy DMM axes are the Bragg arms (dmm_us_arm/dmm_ds_arm) plus the
M2 vertical offset compensator (dmm_m2_y), with the B-station sample-slit
vertical pair (b_slit_top/b_slit_bot) tracking the resulting beam walk.
crystal2_z (M2 Z, 2bma:m8) is a setup translation the IOC does NOT drive,
and the mirror is held constant (deflection geometry) - so neither carries
an energy curve.

CORA models each per-axis relationship as a continuous curve (a
LookupTable backed by an energy_position_curve Calibration) that
interpolates the discrete saved points. The underlying physics is
continuous (Bragg geometry), so this is a faithful generalization of the
beamline's discrete store and can answer for an off-list energy too; the
saved store_0 list is the calibration data the curve is anchored to.

The curve x-points are three of the six real configured Mono energies
(13.374, 18.0, 25.0 keV; the full set is in beamline.yaml), a representative
subset to keep the placeholder fixture small; the positions are PROVISIONAL
placeholders pending the real saved store_0 values from 2-BM staff (open
questions ENERGY-1/2).

## What this proves (and what it does not)

It proves the per-axis chain holds together across heterogeneous axes
(arm angles in deg, slit / offset positions in mm): a PseudoAxis facet
parented to the physical optic, backed by a real energy_position_curve
revision, carrying a keV -> position LookupTable. invertible=True is honest
(the underlying Bragg geometry is monotonic in energy); confirm against the
real saved points.

It does NOT execute motion (eval_lookup_table is deferred), and it does NOT
model the coordinating "set energy" operation that drives all the axes
together as one discrete move - that heterogeneous fan-out is a later step.
This is an intentional-completeness shape model of the per-device mapping.

## Asset stack

```
2-BM (Unit)
+-- FrontEndDrive (Device)               MotionController
    +-- Monochromator (Device)           Monochromator  (driven by FrontEndDrive)
    |   +-- Monochromator_BraggArmUpstream     PseudoAxis  (energy -> dmm_us_arm deg)
    |   +-- Monochromator_BraggArmDownstream   PseudoAxis  (energy -> dmm_ds_arm deg)
    |   +-- Monochromator_M2Y                  PseudoAxis  (energy -> dmm_m2_y mm)
    +-- SampleSlit (Device)              Slit           (driven by FrontEndDrive)
        +-- SampleSlit_VerticalTop             PseudoAxis  (energy -> b_slit_top mm)
        +-- SampleSlit_VerticalBottom          PseudoAxis  (energy -> b_slit_bot mm)
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
    ExtrapolationKind,
    InterpolationKind,
    LookupTable,
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
# Monochromator + Slit are defined by the install; PseudoAxis by this scenario.
_CAP_MOTION_CONTROLLER_ID = family_stream_id(FamilyName("MotionController"))
_CAP_MONOCHROMATOR_ID = family_stream_id(FamilyName("Monochromator"))
_CAP_SLIT_ID = family_stream_id(FamilyName("Slit"))
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))

# Controller registered first so each optic's controller_id back-reference
# targets an already-registered Asset stream.
_FRONTENDDRIVE_ID = UUID("01900000-0000-7000-8000-0000004b0a31")
_MONOCHROMATOR_ID = UUID("01900000-0000-7000-8000-0000004b0a12")
_SAMPLE_SLIT_ID = UUID("01900000-0000-7000-8000-0000004b0a14")

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
)

# The five energy-driven optic axes. The x-points reuse the real configured
# Mono energies (docs2bm); the positions are PROVISIONAL placeholders. The two
# Bragg-arm curves are intentionally seeded identical (the arms move to near-
# identical angles) pending the real per-arm saved points (ENERGY-1).
# (facet_name, parent_id, axis_designation, unit_out, points)
_AXES: tuple[tuple[str, UUID, str, str, list[dict[str, float]]], ...] = (
    (
        "Monochromator_BraggArmUpstream",
        _MONOCHROMATOR_ID,
        "dmm_us_arm",
        "deg",
        [
            {"energy": 13.374, "position": 1.20},
            {"energy": 18.0, "position": 0.90},
            {"energy": 25.0, "position": 0.65},
        ],
    ),
    (
        "Monochromator_BraggArmDownstream",
        _MONOCHROMATOR_ID,
        "dmm_ds_arm",
        "deg",
        [
            {"energy": 13.374, "position": 1.20},
            {"energy": 18.0, "position": 0.90},
            {"energy": 25.0, "position": 0.65},
        ],
    ),
    (
        "Monochromator_M2Y",
        _MONOCHROMATOR_ID,
        "dmm_m2_y",
        "mm",
        [
            {"energy": 13.374, "position": 2.0},
            {"energy": 18.0, "position": 1.5},
            {"energy": 25.0, "position": 1.0},
        ],
    ),
    (
        "SampleSlit_VerticalTop",
        _SAMPLE_SLIT_ID,
        "b_slit_top",
        "mm",
        [
            {"energy": 13.374, "position": 0.5},
            {"energy": 18.0, "position": 0.3},
            {"energy": 25.0, "position": 0.1},
        ],
    ),
    (
        "SampleSlit_VerticalBottom",
        _SAMPLE_SLIT_ID,
        "b_slit_bot",
        "mm",
        [
            {"energy": 13.374, "position": -0.5},
            {"energy": 18.0, "position": -0.3},
            {"energy": 25.0, "position": -0.1},
        ],
    ),
)


def _id_queue() -> list[UUID]:
    """FixedIdGenerator queue: the facility prefix (Unit + FrontEndDrive +
    Monochromator + SampleSlit + their Families) plus a generous anonymous
    tail. Facet / calibration / revision ids are captured from handler
    return values, so the tail just needs to be long enough."""
    return [
        *facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=_DEVICES),
        *[uuid4() for _ in range(60)],
    ]


@pytest.mark.integration
async def test_energy_driven_axes_carry_energy_curves(db_pool: asyncpg.Pool) -> None:
    """Give each of the five energy-driven optic axes a PseudoAxis facet
    backed by a provisional energy_position_curve Calibration and a keV ->
    position LookupTable. Assert each facet stream, each calibration stream,
    and each rule payload (real revision id, keV input, unit_out, invertible)."""
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
    rev_ids: dict[str, UUID] = {}
    cal_ids: dict[str, UUID] = {}

    for facet_name, parent_id, axis_designation, unit_out, points in _AXES:
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
        cal_id = await bind_define_calibration(deps)(
            DefineCalibration(
                target_id=facet_id,
                quantity=CalibrationQuantity.ENERGY_POSITION_CURVE,
                operating_point={"axis_designation": axis_designation, "beam_mode": "mono"},
                description=(
                    f"Provisional energy -> position curve for {axis_designation} (2-BM DMM "
                    "energy-driven axis). Placeholder points pending the real saved store_0 table."
                ),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        cal_ids[facet_name] = cal_id
        rev_id = await bind_append_calibration_revision(deps)(
            AppendCalibrationRevision(
                calibration_id=cal_id,
                value={"points": points, "position_unit": unit_out, "provisional": True},
                status=CalibrationStatus.PROVISIONAL,
                source=AssertedSource(asserted_by=actor),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        rev_ids[facet_name] = rev_id
        await bind_update_asset_partition_rule(deps)(
            UpdateAssetPartitionRule(
                asset_id=facet_id,
                partition_rule=LookupTable(
                    calibration_revision_id=rev_id,
                    interpolation_kind=InterpolationKind.LINEAR,
                    extrapolation_kind=ExtrapolationKind.CLAMP,
                    invertible=True,
                    unit_in="keV",
                    unit_out=unit_out,
                ),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ===== Assertions =====

    for facet_name, parent_id, _axis_designation, unit_out, _points in _AXES:
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
        assert rule["calibration_revision_id"] == str(rev_ids[facet_name])
        assert rule["unit_in"] == "keV"
        assert rule["unit_out"] == unit_out
        assert rule["invertible"] is True

        cal_events, _ = await deps.event_store.load("Calibration", cal_ids[facet_name])
        assert [e.event_type for e in cal_events] == [
            "CalibrationDefined",
            "CalibrationRevisionAppended",
        ], f"{facet_name}: unexpected calibration sequence"
        assert cal_events[0].payload["quantity"] == CalibrationQuantity.ENERGY_POSITION_CURVE.value
        assert cal_events[0].payload["target_id"] == str(facet_id)
        assert cal_events[1].payload["status"] == CalibrationStatus.PROVISIONAL.value
