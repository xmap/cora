"""Filter foil carousel as a discrete index axis at APS 2-BM.

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment, Calibration

Models both 2-BM absorber-foil paddles as discrete "pick one of N"
selectors. Per the staff-authored docs2bm components page, the foil changer
has two paddles (upstream 2bma:m17 and downstream 2bma:m18), each holding
four materials plus an empty (None) slot. Staff (FOIL-1/FOIL-2) corrected
the operational status: m17 is the operational selector today and m18
failed 2026-06-19 (parked 107.19 mm, cannot actuate). Both paddles'
published bindings stay valid in the IOC and are seeded here as real
values, not placeholders; the downstream m18 paddle is marked Faulted
(condition only, lifecycle stays Active, bindings retained).

CORA models each paddle as a PseudoAxis facet under the one Filter device,
carrying a LookupTable rule with interpolation_kind=NEAREST (snap to a
slot) backed by an index_position_table Calibration: the operator commands
a slot index, the rule snaps to the nearest tabulated index and returns the
saved motor position. This reuses the same partition-rule kernel as the
energy curves; the only difference is NEAREST vs LINEAR and a discrete index
table vs a continuous energy curve.

extrapolation_kind=Error: a slot index outside the table is refused (you
cannot select a foil that is not there), not clamped to the last slot.
invertible=False + readback_aggregator_kind=Identity: a discrete table has
no clean inverse, so readback reconstructs from the single constituent
motor.

## What this proves (and what it does not)

It proves the discrete-selector chain holds together for both paddles: a
PseudoAxis facet, a real index_position_table revision, and a NEAREST
LookupTable each, plus the orthogonal Asset condition (m18 Faulted while its
lifecycle stays Active). The position-only move is in scope; the foil's
ATTENUATION (transmission as a function of material, thickness, and energy)
is deferred (the Attenuable affordance). The conduct proof
(select a foil and dispatch its position through the in-memory ControlPort)
lives in test_pseudoaxis_roundtrip.py.

## Asset stack

```
2-BM (Unit)
+-- FrontEndDrive (Device)                  MotionController
    +-- Filter (Device)                     Filter  (driven by FrontEndDrive)
        +-- Filter_FoilSelector_Upstream    PseudoAxis  (index -> m17 position mm; operational)
        +-- Filter_FoilSelector_Downstream  PseudoAxis  (index -> m18 position mm; Faulted)
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
    ReadbackAggregatorKind,
)
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import bind as bind_add_asset_family
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.fault_asset import FaultAsset
from cora.equipment.features.fault_asset import bind as bind_fault_asset
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

_NOW = datetime(2026, 6, 16, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000004f0cc1")

_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-0000004f0a01")

_CAP_MOTION_CONTROLLER_ID = family_stream_id(FamilyName("MotionController"))
_CAP_FILTER_ID = family_stream_id(FamilyName("Filter"))
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))

_FRONTENDDRIVE_ID = UUID("01900000-0000-7000-8000-0000004f0a31")
_FILTER_ID = UUID("01900000-0000-7000-8000-0000004f0a12")

_DEVICES = (
    DeviceSpec("FrontEndDrive", _FRONTENDDRIVE_ID, "MotionController", _CAP_MOTION_CONTROLLER_ID),
    DeviceSpec("Filter", _FILTER_ID, "Filter", _CAP_FILTER_ID, controller_id=_FRONTENDDRIVE_ID),
)

# The downstream paddle (2bma:m18) foil slots, in selection order, with the
# staff-published motor positions (docs2bm components page + 2filter_setup.adl).
# The array index is the slot index; the name is documentary. Positions are
# real (not placeholders); the position unit is mm, staff-confirmed via
# caget 2bma:m18.EGU (FOIL-1). The m18 motor failed 2026-06-19 (Faulted);
# its bindings stay valid in the IOC. LowLimit (a homing reference also at
# 0.0) is excluded: it is not an operator foil selection.
_FOIL_DEVICE_DESIGNATION = "downstream_filter_paddle"
_FOIL_POINTS: list[dict[str, float | str]] = [
    {"name": "600 um Al", "position": 0.0},
    {"name": "150 um Al", "position": 26.0},
    {"name": "300 um C", "position": 53.0},
    {"name": "50 um C", "position": 80.0},
    {"name": "None", "position": 106.0},
]

# The upstream paddle (2bma:m17), the operational filter selector today
# (FOIL-1/FOIL-2): five materials from the 2filter_setup.adl admin screen, same
# mm unit. m17 was wrongly recorded "not in service"; it is in fact operational
# and m18 (downstream) is the one that failed.
_FOIL_DEVICE_DESIGNATION_UPSTREAM = "upstream_filter_paddle"
_FOIL_POINTS_UPSTREAM: list[dict[str, float | str]] = [
    {"name": "1 mm C", "position": 2.0},
    {"name": "150 um Al", "position": 25.0},
    {"name": "600 um Al", "position": 52.0},
    {"name": "1 mm Al", "position": 79.0},
    {"name": "None", "position": 106.0},
]


def _id_queue() -> list[UUID]:
    return [
        *facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=_DEVICES),
        *[uuid4() for _ in range(40)],
    ]


@pytest.mark.integration
async def test_filter_foil_selectors_two_paddles_m18_faulted(db_pool: asyncpg.Pool) -> None:
    """Model both filter paddles as PseudoAxis foil selectors under one Filter
    device, each backed by a real index_position_table Calibration + NEAREST
    LookupTable. The upstream m17 selector is operational (Nominal); the
    downstream m18 selector is Faulted (motor failed 2026-06-19), bindings
    retained. Assert both facet streams, both calibrations, and the m18 fault."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())
    actor = ActorId(_PRINCIPAL_ID)

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    await bind_define_family(deps)(
        DefineFamily(name="PseudoAxis", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    async def seed_selector(
        name: str,
        designation: str,
        points: list[dict[str, float | str]],
        description: str,
    ) -> tuple[UUID, UUID, UUID]:
        sel_id = await bind_register_asset(deps)(
            RegisterAsset(name=name, tier=AssetTier.DEVICE, parent_id=_FILTER_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        await bind_add_asset_family(deps)(
            AddAssetFamily(asset_id=sel_id, family_id=_CAP_PSEUDO_AXIS_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        c_id = await bind_define_calibration(deps)(
            DefineCalibration(
                target_id=sel_id,
                quantity=CalibrationQuantity.INDEX_POSITION_TABLE,
                operating_point={"device_designation": designation},
                description=description,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        r_id = await bind_append_calibration_revision(deps)(
            AppendCalibrationRevision(
                calibration_id=c_id,
                value={"points": points, "position_unit": "mm"},
                status=CalibrationStatus.VERIFIED,
                source=AssertedSource(asserted_by=actor),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        await bind_update_asset_partition_rule(deps)(
            UpdateAssetPartitionRule(
                asset_id=sel_id,
                partition_rule=LookupTable(
                    calibration_id=c_id,
                    calibration_revision_id=r_id,
                    interpolation_kind=InterpolationKind.NEAREST,
                    # ERROR, not CLAMP: an absent slot index is an error (there
                    # is no such foil), not a clamp to the last slot.
                    extrapolation_kind=ExtrapolationKind.ERROR,
                    # A discrete table is not monotonic-invertible; readback
                    # reconstructs from the single constituent motor.
                    invertible=False,
                    readback_aggregator_kind=ReadbackAggregatorKind.IDENTITY,
                    unit_in="index",
                    unit_out="mm",
                ),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        return sel_id, c_id, r_id

    # Upstream m17: the operational filter selector today.
    up_id, up_cal, _up_rev = await seed_selector(
        "Filter_FoilSelector_Upstream",
        _FOIL_DEVICE_DESIGNATION_UPSTREAM,
        _FOIL_POINTS_UPSTREAM,
        (
            "Slot index -> motor position for the OPERATIONAL upstream 2-BM absorber-foil "
            "paddle (2bma:m17). Positions from the 2filter_setup.adl admin screen; unit mm "
            "(FOIL-1/FOIL-2)."
        ),
    )
    # Downstream m18: bindings retained, but the motor failed 2026-06-19.
    down_id, down_cal, _down_rev = await seed_selector(
        "Filter_FoilSelector_Downstream",
        _FOIL_DEVICE_DESIGNATION,
        _FOIL_POINTS,
        (
            "Slot index -> motor position for the downstream 2-BM absorber-foil paddle "
            "(2bma:m18; motor Faulted 2026-06-19, bindings still valid). Positions from "
            "the docs2bm components page; unit mm (caget 2bma:m18.EGU, FOIL-1)."
        ),
    )
    await bind_fault_asset(deps)(
        FaultAsset(
            asset_id=down_id,
            reason="m18 motor failed 2026-06-19, parked at 107.19 mm, cannot actuate (FOIL-1)",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ===== Assertions =====

    # Upstream m17: operational selector, three facet events, no fault.
    up_events, _ = await deps.event_store.load("Asset", up_id)
    assert [e.event_type for e in up_events] == [
        "AssetRegistered",
        "AssetFamilyAdded",
        "AssetPartitionRuleUpdated",
    ]
    assert up_events[0].payload["parent_id"] == str(_FILTER_ID)
    up_rule = up_events[2].payload["partition_rule"]
    assert up_rule["kind"] == "LookupTable"
    assert up_rule["interpolation_kind"] == "Nearest"
    assert up_rule["extrapolation_kind"] == "Error"
    assert up_rule["invertible"] is False
    assert up_rule["readback_aggregator_kind"] == "Identity"
    assert up_rule["unit_in"] == "index"
    assert up_rule["unit_out"] == "mm"

    up_cal_events, _ = await deps.event_store.load("Calibration", up_cal)
    assert [e.event_type for e in up_cal_events] == [
        "CalibrationDefined",
        "CalibrationRevisionAppended",
    ]
    assert up_cal_events[0].payload["operating_point"] == {
        "device_designation": _FOIL_DEVICE_DESIGNATION_UPSTREAM
    }
    assert up_cal_events[1].payload["value"]["points"] == _FOIL_POINTS_UPSTREAM

    # Downstream m18: same selector shape PLUS the fault. Condition is
    # orthogonal to lifecycle (the asset stays Active, bindings retained).
    down_events, _ = await deps.event_store.load("Asset", down_id)
    assert [e.event_type for e in down_events] == [
        "AssetRegistered",
        "AssetFamilyAdded",
        "AssetPartitionRuleUpdated",
        "AssetFaulted",
    ]
    assert down_events[3].payload["reason"].startswith("m18 motor failed")

    down_cal_events, _ = await deps.event_store.load("Calibration", down_cal)
    assert down_cal_events[0].payload["quantity"] == CalibrationQuantity.INDEX_POSITION_TABLE.value
    assert down_cal_events[0].payload["target_id"] == str(down_id)
    assert down_cal_events[1].payload["value"]["points"] == _FOIL_POINTS
