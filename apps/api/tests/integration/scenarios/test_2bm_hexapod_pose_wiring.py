"""Hexapod 6-DoF pose-axis wiring at APS 2-BM.

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment, Recipe

Scenario test for the full six-degree-of-freedom surface of the
sample-positioning hexapod at 2-BM. The physical `Hexapod` (Aerotech
HEX300, vendor-sealed; inverse kinematics in controller firmware) is
one Asset; its six DoFs are surfaced as six `PseudoAxis` sub-modules
parented to it (Device-in-Device, the addressable-sub-module case the
`register_asset` decider sanctions), so a Plan, Procedure, or Caution
can address a single DoF by name.

This materializes the model documented under
docs/deployments/2-bm/inventory.md "Hexapod DoF model": the three
translations (X, Y, Z) and three rotations (Roll = A about X,
Pitch = B about Y, Yaw = C about Z), each carrying a `SolverReference`
partition rule naming the `2bmHXP` firmware solver, plus the
constituent-port wiring that lets every DoF read its feedback from the
physical Hexapod.

## What this proves (and what it does not)

The ports + wires validate end-to-end: 6 feedback OUTPUT ports on the
Hexapod, a `constituent_in` INPUT + one operator-addressable OUTPUT on
each DoF, and 6 wires (`Hexapod.<axis>_feedback_out ->
Hexapod_<Axis>.constituent_in`). Each wire trips
`validate_pseudoaxis_fanout` on its DoF target (exactly one OUTPUT port,
one incoming wire, homogeneous signal_type; `SolverReference` is exempt
from the arity check because the firmware owns the kinematics).

It does NOT execute motion: `eval_solver_reference` is still
`NotImplementedError` (the bridge to a live `2bmHXP` soft-IOC is
deferred), so the wired Plan is validated-but-not-runtime-executable.
This is an intentional-completeness model, not a runtime path.

See [[project-pitch-roll-retag]] for the Shape-2 design this realizes
and [[project-plan-wiring-design]] for the Wire 4-tuple + direction +
signal_type rules. The PseudoAxis ceremony mirrors
test_2bm_alignment_pitch.py; the ports + wired Plan mirror
test_2bm_mctoptics_setup.py.

## Asset stack

```
2-BM (Unit)
+-- Hexapod (Device)                 Family: Hexapod
    +-- Hexapod_X (Device)           Family: PseudoAxis   translation along X
    +-- Hexapod_Y (Device)           Family: PseudoAxis   translation along Y
    +-- Hexapod_Z (Device)           Family: PseudoAxis   translation along Z
    +-- Hexapod_Roll (Device)        Family: PseudoAxis   rotation A about X
    +-- Hexapod_Pitch (Device)       Family: PseudoAxis   rotation B about Y
    +-- Hexapod_Yaw (Device)         Family: PseudoAxis   rotation C about Z
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
from cora.recipe.aggregates.method import ExecutionPattern
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
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000480cc1")

# Scenario tag: 480 (hexapod 6-DoF pose-axis wiring).

# Facility hierarchy
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000480501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000480a01")

# Family ids are derived from the name (deterministic uuid5): install
# defines "Hexapod" from the DeviceSpec; this scenario defines "PseudoAxis".
_CAP_HEXAPOD_ID = family_stream_id(FamilyName("Hexapod"))
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))

# Physical hexapod (facility-install Device under 2-BM)
_ASSET_HEXAPOD_ID = UUID("01900000-0000-7000-8000-000000480a11")

# Six DoF PseudoAxis sub-modules (parented to the Hexapod)
_ASSET_HEXAPOD_X_ID = UUID("01900000-0000-7000-8000-000000480a21")
_ASSET_HEXAPOD_Y_ID = UUID("01900000-0000-7000-8000-000000480a22")
_ASSET_HEXAPOD_Z_ID = UUID("01900000-0000-7000-8000-000000480a23")
_ASSET_HEXAPOD_ROLL_ID = UUID("01900000-0000-7000-8000-000000480a24")
_ASSET_HEXAPOD_PITCH_ID = UUID("01900000-0000-7000-8000-000000480a25")
_ASSET_HEXAPOD_YAW_ID = UUID("01900000-0000-7000-8000-000000480a26")

# Recipe ladder
_CAPABILITY_RECIPE_ID = UUID("01900000-0000-7000-8000-000000c0480e")
_METHOD_ID = UUID("01900000-0000-7000-8000-000000480d01")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-000000480d11")
_PLAN_ID = UUID("01900000-0000-7000-8000-000000480d21")

# Locked signal_type vocabulary (shared with the MCTOptics topology).
_SIG_FB_LIN = "position_feedback_linear_mm"
_SIG_FB_ROT = "position_feedback_rotation_deg"
_SIG_SET_LIN = "position_setpoint_linear_mm"
_SIG_SET_ROT = "position_setpoint_rotation_deg"

# The physical hexapod is the single facility-install Device. The six
# DoF facets are registered separately (parent = Hexapod) because the
# install ceremony parents every DeviceSpec to the Unit.
_DEVICES = (DeviceSpec("Hexapod", _ASSET_HEXAPOD_ID, "Hexapod", _CAP_HEXAPOD_ID),)

# Per-DoF spec drives registration, partition rule, ports, and wires.
# (asset_id, name, hexapod_feedback_port, feedback_signal, dof_out_port, setpoint_signal)
_DOFS: tuple[tuple[UUID, str, str, str, str, str], ...] = (
    (_ASSET_HEXAPOD_X_ID, "Hexapod_X", "x_feedback_out", _SIG_FB_LIN, "x_out", _SIG_SET_LIN),
    (_ASSET_HEXAPOD_Y_ID, "Hexapod_Y", "y_feedback_out", _SIG_FB_LIN, "y_out", _SIG_SET_LIN),
    (_ASSET_HEXAPOD_Z_ID, "Hexapod_Z", "z_feedback_out", _SIG_FB_LIN, "z_out", _SIG_SET_LIN),
    (
        _ASSET_HEXAPOD_ROLL_ID,
        "Hexapod_Roll",
        "roll_feedback_out",
        _SIG_FB_ROT,
        "roll_out",
        _SIG_SET_ROT,
    ),
    (
        _ASSET_HEXAPOD_PITCH_ID,
        "Hexapod_Pitch",
        "pitch_feedback_out",
        _SIG_FB_ROT,
        "pitch_out",
        _SIG_SET_ROT,
    ),
    (
        _ASSET_HEXAPOD_YAW_ID,
        "Hexapod_Yaw",
        "yaw_feedback_out",
        _SIG_FB_ROT,
        "yaw_out",
        _SIG_SET_ROT,
    ),
)

# 18 typed ports: 6 feedback OUTPUTs on the Hexapod + (constituent_in
# INPUT, <axis>_out OUTPUT) on each of the 6 DoFs.
# (asset_id, port_name, direction, signal_type)
_PORT_SPECS: tuple[tuple[UUID, str, PortDirection, str], ...] = (
    *(
        (_ASSET_HEXAPOD_ID, fb_port, PortDirection.OUTPUT, fb_sig)
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

# 6 wires, one per DoF: Hexapod feedback OUTPUT -> DoF constituent_in.
# (source_asset_id, source_port_name, target_asset_id, target_port_name)
_WIRE_SPECS: tuple[tuple[UUID, str, UUID, str], ...] = tuple(
    (_ASSET_HEXAPOD_ID, fb_port, dof_id, "constituent_in")
    for dof_id, _name, fb_port, _fb_sig, _out, _set in _DOFS
)

# SolverReference partition rule shared by all six DoFs: the 2bmHXP
# firmware solver owns the 6-DoF parallel kinematics.
_SOLVER_RULE = SolverReference(
    solver_id="2bmHXP",
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
        # install_aps_unit (operators, reviewers, Unit, Hexapod Family +
        # Hexapod register + add_family, Trust shape).
        *facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=_DEVICES),
        # define_family PseudoAxis: event_id only (stream id derived from name).
        e(),
        # register_asset x 6 (DoFs, parent = Hexapod): asset_id, event_id.
        _ASSET_HEXAPOD_X_ID,
        e(),
        _ASSET_HEXAPOD_Y_ID,
        e(),
        _ASSET_HEXAPOD_Z_ID,
        e(),
        _ASSET_HEXAPOD_ROLL_ID,
        e(),
        _ASSET_HEXAPOD_PITCH_ID,
        e(),
        _ASSET_HEXAPOD_YAW_ID,
        e(),
        # add_asset_family x 6 (DoFs -> PseudoAxis): event_id.
        e(),
        e(),
        e(),
        e(),
        e(),
        e(),
        # update_asset_partition_rule x 6 (DoFs): event_id.
        e(),
        e(),
        e(),
        e(),
        e(),
        e(),
        # add_asset_port x 18 (6 Hexapod feedback + 2 per DoF): event_id.
        *(e() for _ in range(18)),
        # define_method: method_id, event_id.
        _METHOD_ID,
        e(),
        # define_practice: practice_id, event_id.
        _PRACTICE_ID,
        e(),
        # define_plan: plan_id, event_id.
        _PLAN_ID,
        e(),
        # add_plan_wire x 6: event_id each.
        e(),
        e(),
        e(),
        e(),
        e(),
        e(),
    ]


@pytest.mark.integration
async def test_hexapod_six_dof_wiring_validates_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Surface all six hexapod DoFs as PseudoAxis sub-modules and wire
    each to a Hexapod feedback port. Assert the per-DoF event streams,
    the Hexapod port count, and the six Plan wire 4-tuples."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Facility install (Argonne -> APS -> 2-BM + the Hexapod Device) -----

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

    # ----- Register the six DoF facets as sub-modules of the Hexapod -----

    for _dof_id, name, _fb_port, _fb_sig, _out, _set in _DOFS:
        await bind_register_asset(deps)(
            RegisterAsset(name=name, tier=AssetTier.DEVICE, parent_id=_ASSET_HEXAPOD_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    for dof_id, _name, _fb_port, _fb_sig, _out, _set in _DOFS:
        await bind_add_asset_family(deps)(
            AddAssetFamily(asset_id=dof_id, family_id=_CAP_PSEUDO_AXIS_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- SolverReference partition rule on each DoF (2bmHXP solver) -----

    for dof_id, _name, _fb_port, _fb_sig, _out, _set in _DOFS:
        await bind_update_asset_partition_rule(deps)(
            UpdateAssetPartitionRule(asset_id=dof_id, partition_rule=_SOLVER_RULE),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Ports: 6 feedback OUTPUTs on the Hexapod + 2 per DoF -----

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

    # ----- Minimal Recipe ladder binding the Hexapod + its six DoFs -----

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_RECIPE_ID,
        code="cora.capability.hexapod_pose",
        name="HexapodPose",
    )
    await bind_define_method(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_RECIPE_ID,
            name="hexapod_pose",
            needed_family_ids=frozenset({_CAP_HEXAPOD_ID, _CAP_PSEUDO_AXIS_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="2BM_hexapod_pose_practice", method_id=_METHOD_ID, site_id=_APS_SITE_ID
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_hexapod_pose_plan",
            practice_id=_PRACTICE_ID,
            asset_ids=frozenset({_ASSET_HEXAPOD_ID, *(dof[0] for dof in _DOFS)}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Six constituent wires (Hexapod feedback -> DoF constituent_in) -----

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

    # The physical Hexapod: genesis + Family (from install) + 6 feedback ports.
    hexapod_events, _ = await deps.event_store.load("Asset", _ASSET_HEXAPOD_ID)
    hexapod_types = [ev.event_type for ev in hexapod_events]
    assert hexapod_types == [
        "AssetRegistered",
        "AssetFamilyAdded",
        *["AssetPortAdded"] * 6,
    ], f"Hexapod: unexpected event sequence {hexapod_types}"

    # Plan stream carries exactly the six constituent wires. Assert the
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
