"""Filter foil carousel as a discrete index axis at APS 2-BM.

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment, Calibration

Models the 2-BM downstream absorber-foil paddle as a discrete "pick one of
N" selector. Per the staff-authored docs2bm components page, the foil
changer has two paddles (upstream 2bma:m17 and downstream 2bma:m18), each
holding four materials plus an empty (None) slot. Staff (FOIL-1/FOIL-2)
corrected the operational status: m17 is the operational selector today and
m18 failed 2026-06-19 (Faulted, parked 107.19 mm). The downstream paddle's
published bindings stay valid in the IOC and are seeded here as real
values, not placeholders.

CORA models the selector as a PseudoAxis facet under the Filter device,
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

It proves the discrete-selector chain holds together: a PseudoAxis facet, a
real index_position_table revision, and a NEAREST LookupTable. The
position-only move is in scope; the foil's ATTENUATION (transmission as a
function of material, thickness, and energy) is deferred (the Attenuable
affordance), as is the upstream m17 selector (the operational paddle today;
its slot table is a later slice). The conduct proof
(select a foil and dispatch its position through the in-memory ControlPort)
lives in test_pseudoaxis_roundtrip.py.

## Asset stack

```
2-BM (Unit)
+-- FrontEndDrive (Device)        MotionController
    +-- Filter (Device)           Filter  (driven by FrontEndDrive)
        +-- Filter_FoilSelector   PseudoAxis  (index -> downstream paddle position mm)
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


def _id_queue() -> list[UUID]:
    return [
        *facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=_DEVICES),
        *[uuid4() for _ in range(40)],
    ]


@pytest.mark.integration
async def test_filter_foil_selector_carries_index_table(db_pool: asyncpg.Pool) -> None:
    """Give the downstream filter paddle a PseudoAxis foil selector backed by
    a real index_position_table Calibration and a NEAREST LookupTable. Assert
    the facet stream, the calibration stream, and the rule payload (NEAREST,
    Error extrapolation, index input, non-invertible with Identity readback)."""
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

    selector_id = await bind_register_asset(deps)(
        RegisterAsset(name="Filter_FoilSelector", tier=AssetTier.DEVICE, parent_id=_FILTER_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_asset_family(deps)(
        AddAssetFamily(asset_id=selector_id, family_id=_CAP_PSEUDO_AXIS_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    cal_id = await bind_define_calibration(deps)(
        DefineCalibration(
            target_id=selector_id,
            quantity=CalibrationQuantity.INDEX_POSITION_TABLE,
            operating_point={"device_designation": _FOIL_DEVICE_DESIGNATION},
            description=(
                "Slot index -> motor position for the 2-BM downstream absorber-foil paddle "
                "(2bma:m18; motor Faulted 2026-06-19, bindings still valid). Positions from "
                "the docs2bm components page; the unit is mm (caget 2bma:m18.EGU, FOIL-1)."
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    rev_id = await bind_append_calibration_revision(deps)(
        AppendCalibrationRevision(
            calibration_id=cal_id,
            value={"points": _FOIL_POINTS, "position_unit": "mm"},
            status=CalibrationStatus.VERIFIED,
            source=AssertedSource(asserted_by=actor),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_update_asset_partition_rule(deps)(
        UpdateAssetPartitionRule(
            asset_id=selector_id,
            partition_rule=LookupTable(
                calibration_id=cal_id,
                calibration_revision_id=rev_id,
                interpolation_kind=InterpolationKind.NEAREST,
                # ERROR, not CLAMP: selecting a slot index that is not in the
                # table is an error (there is no such foil), not a clamp to
                # the last slot.
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

    # ===== Assertions =====

    facet_events, _ = await deps.event_store.load("Asset", selector_id)
    assert [e.event_type for e in facet_events] == [
        "AssetRegistered",
        "AssetFamilyAdded",
        "AssetPartitionRuleUpdated",
    ]
    assert facet_events[0].payload["parent_id"] == str(_FILTER_ID)
    assert facet_events[1].payload["family_id"] == str(_CAP_PSEUDO_AXIS_ID)

    rule = facet_events[2].payload["partition_rule"]
    assert rule["kind"] == "LookupTable"
    assert rule["calibration_id"] == str(cal_id)
    assert rule["calibration_revision_id"] == str(rev_id)
    assert rule["interpolation_kind"] == "Nearest"
    assert rule["extrapolation_kind"] == "Error"
    assert rule["invertible"] is False
    assert rule["readback_aggregator_kind"] == "Identity"
    assert rule["unit_in"] == "index"
    assert rule["unit_out"] == "mm"

    cal_events, _ = await deps.event_store.load("Calibration", cal_id)
    assert [e.event_type for e in cal_events] == [
        "CalibrationDefined",
        "CalibrationRevisionAppended",
    ]
    assert cal_events[0].payload["quantity"] == CalibrationQuantity.INDEX_POSITION_TABLE.value
    assert cal_events[0].payload["target_id"] == str(selector_id)
    assert cal_events[0].payload["operating_point"] == {
        "device_designation": _FOIL_DEVICE_DESIGNATION
    }
    assert cal_events[1].payload["value"]["points"] == _FOIL_POINTS
