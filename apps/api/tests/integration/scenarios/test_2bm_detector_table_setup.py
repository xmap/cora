"""Detector optical-table corrective-DoF wiring at APS 2-BM.

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment, Recipe

Scenario test for the detector optical table at 2-BM. The Microscope
detector rides on an SRI-geometry table whose six physical motors on the
b-station OMS VME58 crate (`SampleStageDrive`) feed the virtual EPICS
record `2bmb:table3`; the table's IOC solver resolves them into four
operator-addressable corrective degrees of freedom (centering X / Y,
corrective pitch about lab-X, corrective yaw about lab-Y).

The physical `DetectorTable` (Family `OpticalTable`) is one Asset; its
four corrective DoFs are surfaced as `PseudoAxis` sub-modules parented to
it (Device-in-Device, the addressable-sub-module case the `register_asset`
decider sanctions), so a Plan, Procedure, or Caution can address one
corrective DoF by name. This mirrors the Hexapod DoF model exactly; see
docs/deployments/2-bm/assets.md "Detector optical table DoF model" and
test_2bm_hexapod_pose_wiring.py.

## What this proves (and what it does not)

The ports + wires validate end-to-end: four feedback OUTPUT ports on the
table, a `constituent_in` INPUT + one operator-addressable OUTPUT on each
DoF, and four wires (`DetectorTable.<axis>_feedback_out ->
DetectorTable_<Axis>.constituent_in`). Each wire trips
`validate_pseudoaxis_fanout` on its DoF target (exactly one OUTPUT port,
one incoming wire, homogeneous signal_type; `SolverReference` is exempt
from the arity check because the IOC owns the six-motor kinematics).

It does NOT execute motion: `eval_solver_reference` is still
`NotImplementedError` (the bridge to the live `2bmb:table3` soft-IOC is
deferred, shared with the hexapod), so the wired Plan is
validated-but-not-runtime-executable. The six physical motors stay
unregistered (the IOC owns them), exactly as the hexapod's six legs are.

## Asset stack

```
2-BM (Unit)
+-- DetectorTable (Device)            Family: OpticalTable
    +-- DetectorTable_X (Device)      Family: PseudoAxis   centering X
    +-- DetectorTable_Y (Device)      Family: PseudoAxis   centering Y
    +-- DetectorTable_AX (Device)     Family: PseudoAxis   corrective pitch about lab-X
    +-- DetectorTable_AY (Device)     Family: PseudoAxis   corrective yaw about lab-Y
```
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates._partition_rule import SolverReference, SolverTransportKind
from cora.equipment.aggregates.asset import AssetTier, PortDirection
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import bind as bind_add_asset_family
from cora.equipment.features.add_asset_port import AddAssetPort
from cora.equipment.features.add_asset_port import bind as bind_add_asset_port
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.equipment.features.update_asset_partition_rule import UpdateAssetPartitionRule
from cora.equipment.features.update_asset_partition_rule import (
    bind as bind_update_asset_partition_rule,
)
from cora.recipe.features.add_plan_wire import AddPlanWire
from cora.recipe.features.add_plan_wire import bind as bind_add_plan_wire
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_plan import bind as bind_define_plan
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.define_practice import bind as bind_define_practice
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

_NOW = datetime(2026, 6, 14, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000490cc1")

# Scenario tag: 490 (detector optical-table corrective-DoF wiring).

# Facility hierarchy
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000490501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000490a01")

# Family ids are derived from the name (deterministic uuid5): install
# defines "OpticalTable" from the DeviceSpec; this scenario defines "PseudoAxis".
_CAP_OPTICAL_TABLE_ID = family_stream_id(FamilyName("OpticalTable"))
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))

# Physical detector table (facility-install Device under 2-BM)
_ASSET_DETECTOR_TABLE_ID = UUID("01900000-0000-7000-8000-000000490a11")

# Four corrective-DoF PseudoAxis sub-modules (parented to the table)
_ASSET_TABLE_X_ID = UUID("01900000-0000-7000-8000-000000490a21")
_ASSET_TABLE_Y_ID = UUID("01900000-0000-7000-8000-000000490a22")
_ASSET_TABLE_AX_ID = UUID("01900000-0000-7000-8000-000000490a23")
_ASSET_TABLE_AY_ID = UUID("01900000-0000-7000-8000-000000490a24")

# Recipe ladder
_CAPABILITY_RECIPE_ID = UUID("01900000-0000-7000-8000-000000c0490e")
_METHOD_ID = UUID("01900000-0000-7000-8000-000000490d01")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-000000490d11")
_PLAN_ID = UUID("01900000-0000-7000-8000-000000490d21")

# Locked signal_type vocabulary (shared with the Hexapod + MCTOptics topology).
_SIG_FB_LIN = "position_feedback_linear_mm"
_SIG_FB_ROT = "position_feedback_rotation_deg"
_SIG_SET_LIN = "position_setpoint_linear_mm"
_SIG_SET_ROT = "position_setpoint_rotation_deg"

# The physical table is the single facility-install Device. The four DoF
# facets are registered separately (parent = DetectorTable) because the
# install ceremony parents every DeviceSpec to the Unit.
_DEVICES = (
    DeviceSpec("DetectorTable", _ASSET_DETECTOR_TABLE_ID, "OpticalTable", _CAP_OPTICAL_TABLE_ID),
)

# Per-DoF spec drives registration, partition rule, ports, and wires.
# (asset_id, name, table_feedback_port, feedback_signal, dof_out_port, setpoint_signal)
_DOFS: tuple[tuple[UUID, str, str, str, str, str], ...] = (
    (_ASSET_TABLE_X_ID, "DetectorTable_X", "x_feedback_out", _SIG_FB_LIN, "x_out", _SIG_SET_LIN),
    (_ASSET_TABLE_Y_ID, "DetectorTable_Y", "y_feedback_out", _SIG_FB_LIN, "y_out", _SIG_SET_LIN),
    (
        _ASSET_TABLE_AX_ID,
        "DetectorTable_AX",
        "ax_feedback_out",
        _SIG_FB_ROT,
        "ax_out",
        _SIG_SET_ROT,
    ),
    (
        _ASSET_TABLE_AY_ID,
        "DetectorTable_AY",
        "ay_feedback_out",
        _SIG_FB_ROT,
        "ay_out",
        _SIG_SET_ROT,
    ),
)

# 12 typed ports: 4 feedback OUTPUTs on the table + (constituent_in INPUT,
# <axis>_out OUTPUT) on each of the 4 DoFs.
# (asset_id, port_name, direction, signal_type)
_PORT_SPECS: tuple[tuple[UUID, str, PortDirection, str], ...] = (
    *(
        (_ASSET_DETECTOR_TABLE_ID, fb_port, PortDirection.OUTPUT, fb_sig)
        for _id, _name, fb_port, fb_sig, _out, _set in _DOFS
    ),
    *(
        port
        for dof_id, _name, _fb_port, fb_sig, out_port, set_sig in _DOFS
        for port in (
            (dof_id, "constituent_in", PortDirection.INPUT, fb_sig),
            (dof_id, out_port, PortDirection.OUTPUT, set_sig),
        )
    ),
)

# 4 wires, one per DoF: table feedback OUTPUT -> DoF constituent_in.
# (source_asset_id, source_port_name, target_asset_id, target_port_name)
_WIRE_SPECS: tuple[tuple[UUID, str, UUID, str], ...] = tuple(
    (_ASSET_DETECTOR_TABLE_ID, fb_port, dof_id, "constituent_in")
    for dof_id, _name, fb_port, _fb_sig, _out, _set in _DOFS
)

# SolverReference partition rule shared by all four DoFs: the 2bmb:table3
# IOC solver owns the six-motor SRI-geometry kinematics.
_SOLVER_RULE = SolverReference(
    solver_id="2bmb_table3",
    solver_version="1.0.0",
    solver_transport_kind=SolverTransportKind.SOFT_IOC_RECORD,
    residual_tolerance_limit=0.001,
    singularity_threshold=0.01,
    invertible=True,
    readback_aggregator_kind=None,
)


def _id_queue() -> list[UUID]:
    """FixedIdGenerator queue. Anonymous event ids are uuid4()."""
    e = uuid4
    return [
        # install_aps_unit (operators, reviewers, Unit, OpticalTable Family +
        # DetectorTable register + add_family, Trust shape).
        *facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=_DEVICES),
        # define_family PseudoAxis: event_id only (stream id derived from name).
        e(),
        # register_asset x 4 (DoFs, parent = DetectorTable): asset_id, event_id.
        _ASSET_TABLE_X_ID,
        e(),
        _ASSET_TABLE_Y_ID,
        e(),
        _ASSET_TABLE_AX_ID,
        e(),
        _ASSET_TABLE_AY_ID,
        e(),
        # add_asset_family x 4 (DoFs -> PseudoAxis): event_id.
        e(),
        e(),
        e(),
        e(),
        # update_asset_partition_rule x 4 (DoFs): event_id.
        e(),
        e(),
        e(),
        e(),
        # add_asset_port x 12 (4 table feedback + 2 per DoF): event_id.
        *(e() for _ in range(12)),
        # define_method: method_id, event_id.
        _METHOD_ID,
        e(),
        # define_practice: practice_id, event_id.
        _PRACTICE_ID,
        e(),
        # define_plan: plan_id, event_id.
        _PLAN_ID,
        e(),
        # add_plan_wire x 4: event_id each.
        e(),
        e(),
        e(),
        e(),
    ]


@pytest.mark.integration
async def test_detector_table_four_dof_wiring_validates_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Surface the four detector-table corrective DoFs as PseudoAxis
    sub-modules and wire each to a table feedback port. Assert the per-DoF
    event streams, the table port count, and the four Plan wire 4-tuples."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Facility install (Argonne -> APS -> 2-BM + the DetectorTable Device) -----

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    # ----- PseudoAxis Family (the DoF facets' Family) -----

    await bind_define_family(deps)(
        DefineFamily(name="PseudoAxis", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Register the four DoF facets as sub-modules of the table -----

    for _dof_id, name, _fb_port, _fb_sig, _out, _set in _DOFS:
        await bind_register_asset(deps)(
            RegisterAsset(name=name, tier=AssetTier.DEVICE, parent_id=_ASSET_DETECTOR_TABLE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    for dof_id, _name, _fb_port, _fb_sig, _out, _set in _DOFS:
        await bind_add_asset_family(deps)(
            AddAssetFamily(asset_id=dof_id, family_id=_CAP_PSEUDO_AXIS_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- SolverReference partition rule on each DoF (2bmb:table3 solver) -----

    for dof_id, _name, _fb_port, _fb_sig, _out, _set in _DOFS:
        await bind_update_asset_partition_rule(deps)(
            UpdateAssetPartitionRule(asset_id=dof_id, partition_rule=_SOLVER_RULE),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Ports: 4 feedback OUTPUTs on the table + 2 per DoF -----

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

    # ----- Minimal Recipe ladder binding the table + its four DoFs -----

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_RECIPE_ID,
        code="cora.capability.detector_table_correction",
        name="DetectorTableCorrection",
    )
    await bind_define_method(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_RECIPE_ID,
            name="detector_table_correction",
            needed_family_ids=frozenset({_CAP_OPTICAL_TABLE_ID, _CAP_PSEUDO_AXIS_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="2BM_detector_table_correction_practice",
            method_id=_METHOD_ID,
            site_id=_APS_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_detector_table_correction_plan",
            practice_id=_PRACTICE_ID,
            asset_ids=frozenset({_ASSET_DETECTOR_TABLE_ID, *(dof[0] for dof in _DOFS)}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Four constituent wires (table feedback -> DoF constituent_in) -----

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

    # Each DoF stream: genesis + Family + partition rule + its 2 ports.
    # No activation, no settings (PseudoAxis carries neither).
    for dof_id, name, _fb_port, _fb_sig, _out, _set in _DOFS:
        events, _version = await deps.event_store.load("Asset", dof_id)
        types = [ev.event_type for ev in events]
        assert types == [
            "AssetRegistered",
            "AssetFamilyAdded",
            "AssetPartitionRuleUpdated",
            "AssetPortAdded",
            "AssetPortAdded",
        ], f"{name}: unexpected event sequence {types}"

    # The physical table: genesis + Family (from install) + 4 feedback ports.
    table_events, _ = await deps.event_store.load("Asset", _ASSET_DETECTOR_TABLE_ID)
    table_types = [ev.event_type for ev in table_events]
    assert table_types == [
        "AssetRegistered",
        "AssetFamilyAdded",
        *["AssetPortAdded"] * 4,
    ], f"DetectorTable: unexpected event sequence {table_types}"

    # Plan stream carries exactly the four constituent wires. Assert the
    # 4-tuple identities (not just count) to catch a silent direction-swap
    # or signal_type-coerce regression in AddPlanWire.
    plan_events, _plan_version = await deps.event_store.load("Plan", _PLAN_ID)
    plan_wire_added = [ev for ev in plan_events if ev.event_type == "PlanWireAdded"]
    assert len(plan_wire_added) == len(_WIRE_SPECS), (
        f"expected {len(_WIRE_SPECS)} PlanWireAdded events, got {len(plan_wire_added)}"
    )
    actual_wires = frozenset(
        (
            UUID(ev.payload["source_asset_id"]),
            ev.payload["source_port_name"],
            UUID(ev.payload["target_asset_id"]),
            ev.payload["target_port_name"],
        )
        for ev in plan_wire_added
    )
    assert actual_wires == frozenset(_WIRE_SPECS), (
        f"wire 4-tuples diverge.\n  missing: {frozenset(_WIRE_SPECS) - actual_wires}\n  "
        f"unexpected: {actual_wires - frozenset(_WIRE_SPECS)}"
    )
