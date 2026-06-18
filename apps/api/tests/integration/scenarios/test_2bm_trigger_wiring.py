"""Camera + piezo trigger wiring at APS 2-BM (the softGlueZynq output surface).

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment, Recipe

Scenario test for the trigger-output surface of the 2-BM softGlueZynq
timing box (item_060). test_2bm_timing_setup.py registers the box's
identity; this scenario models how its generated triggers reach the
devices they drive, as typed `AssetPort`s resolved to `Plan` wires at
bind time, the same idiom as the hexapod constituent wiring
(test_2bm_hexapod_pose_wiring.py).

The box drives two distinct consumers, so the two legs carry two
signal types:

  - the camera trigger (`frame_trigger_ttl`): the headline path of
    item_060, where the box generates the camera trigger pulse train
    and routes it (PSO or the trigILF subset, selected by MUX2-1)
    through to the camera. This edge starts an exposure.
  - the NV200D piezo step triggers (`step_trigger_ttl`): the two legs
    documented under docs/deployments/2-bm/assets.md "NV200D trigger
    wiring" (item_028), where each TTL edge advances a preloaded piezo
    position during camera readout. This edge advances a motion step,
    not an exposure, so its signal type is deliberately distinct.

## What this proves (and what it does not)

Three wires validate end-to-end against the strict forward-reference
contract (ports must exist before they are wired): one camera-trigger
wire (`Timing.camera_trigger_out -> Camera.trigger_in`) and two piezo
step-trigger wires (`Timing.out2 -> SampleFineDrive.step_x_in`,
`Timing.out3 -> SampleFineDrive.step_y_in`). A successful `add_plan_wire`
is itself the proof of direction (source OUTPUT, target INPUT) and exact
signal_type match, which `validate_wire_endpoints` enforces at add time;
the camera target is not a `PseudoAxis`, so no fan-out arity check
applies.

It does NOT actuate any trigger: which PSO subset reaches the camera
(MUX2-1 select, trigILF via write_PSO_array), the GateDly width/delay
values, and the exact FPGA output channel feeding the camera are per-scan
Method / Plan configuration and operator-confirmed facts (TIME-2), not
the durable wire topology this slice models.

See [[project_plan_wiring_design]] for the Wire 4-tuple + direction +
signal_type rules; the ports + wired Plan mirror
test_2bm_hexapod_pose_wiring.py.

## Asset stack

```
2-BM (Unit)
+-- Timing (Device)            Family: TimingController   softGlueZynq box (2bmbMZ1:SG:)
+-- Camera (Device)            Family: Camera             detector that the trigger drives
+-- SampleFineDrive (Device)   Family: MotionController   NV200D piezo, FPGA-stepped
```
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.asset import PortDirection
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.add_asset_port import AddAssetPort
from cora.equipment.features.add_asset_port import bind as bind_add_asset_port
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

_NOW = datetime(2026, 6, 18, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000004d0cc1")

# Scenario tag: 4d0 (camera + piezo trigger wiring).

_APS_SITE_ID = UUID("01900000-0000-7000-8000-0000004d0501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-0000004d0a01")

# Family ids derive from the name (deterministic uuid5); the install
# defines each from the DeviceSpec.
_CAP_TIMING_CONTROLLER_ID = family_stream_id(FamilyName("TimingController"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_MOTION_CONTROLLER_ID = family_stream_id(FamilyName("MotionController"))

_TIMING_ID = UUID("01900000-0000-7000-8000-0000004d0a11")
_CAMERA_ID = UUID("01900000-0000-7000-8000-0000004d0a12")
_SAMPLE_FINE_DRIVE_ID = UUID("01900000-0000-7000-8000-0000004d0a13")

# Recipe ladder
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-0000004d0e01")
_METHOD_ID = UUID("01900000-0000-7000-8000-0000004d0d01")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-0000004d0d11")
_PLAN_ID = UUID("01900000-0000-7000-8000-0000004d0d21")

# Two signal types on the box's output surface: the camera trigger starts
# an exposure; the piezo step trigger advances a preloaded motion step.
_SIG_FRAME = "frame_trigger_ttl"
_SIG_STEP = "step_trigger_ttl"

_DEVICES = (
    DeviceSpec("Timing", _TIMING_ID, "TimingController", _CAP_TIMING_CONTROLLER_ID),
    DeviceSpec("Camera", _CAMERA_ID, "Camera", _CAP_CAMERA_ID),
    DeviceSpec(
        "SampleFineDrive", _SAMPLE_FINE_DRIVE_ID, "MotionController", _CAP_MOTION_CONTROLLER_ID
    ),
)

# Six typed ports: three OUTPUTs on the Timing box (camera leg + two
# piezo legs) and the matching INPUT on each driven device.
# (asset_id, port_name, direction, signal_type)
_PORT_SPECS: tuple[tuple[UUID, str, PortDirection, str], ...] = (
    (_TIMING_ID, "camera_trigger_out", PortDirection.OUTPUT, _SIG_FRAME),
    (_TIMING_ID, "out2", PortDirection.OUTPUT, _SIG_STEP),
    (_TIMING_ID, "out3", PortDirection.OUTPUT, _SIG_STEP),
    (_CAMERA_ID, "trigger_in", PortDirection.INPUT, _SIG_FRAME),
    (_SAMPLE_FINE_DRIVE_ID, "step_x_in", PortDirection.INPUT, _SIG_STEP),
    (_SAMPLE_FINE_DRIVE_ID, "step_y_in", PortDirection.INPUT, _SIG_STEP),
)

# Three wires: one camera-trigger leg + two piezo step-trigger legs.
# (source_asset_id, source_port_name, target_asset_id, target_port_name)
_WIRE_CAMERA = (_TIMING_ID, "camera_trigger_out", _CAMERA_ID, "trigger_in")
_WIRE_SPECS: tuple[tuple[UUID, str, UUID, str], ...] = (
    _WIRE_CAMERA,
    (_TIMING_ID, "out2", _SAMPLE_FINE_DRIVE_ID, "step_x_in"),
    (_TIMING_ID, "out3", _SAMPLE_FINE_DRIVE_ID, "step_y_in"),
)


def _id_queue() -> list[UUID]:
    """FixedIdGenerator queue. Anonymous event ids are uuid4()."""
    e = uuid4
    return [
        # install_aps_unit (operators, reviewers, Unit, the 3 device
        # Families + their register + add_family, Trust shape).
        *facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=_DEVICES),
        # add_asset_port x 6: event_id each.
        *(e() for _ in range(len(_PORT_SPECS))),
        # define_method: method_id, event_id.
        _METHOD_ID,
        e(),
        # define_practice: practice_id, event_id.
        _PRACTICE_ID,
        e(),
        # define_plan: plan_id, event_id.
        _PLAN_ID,
        e(),
        # add_plan_wire x 3: event_id each.
        *(e() for _ in range(len(_WIRE_SPECS))),
    ]


@pytest.mark.integration
async def test_trigger_wiring_validates_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Wire the softGlueZynq box's three output legs to the camera and the
    NV200D piezo. Assert each Asset's event stream, the Timing box's three
    output ports, and the three Plan wire 4-tuples (identities, not just
    counts, to catch a direction-swap or signal_type-coerce regression)."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Facility install (Argonne -> APS -> 2-BM + the 3 Devices) -----

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    # ----- Ports: 3 OUTPUTs on the Timing box + the matching INPUTs -----

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

    # ----- Minimal Recipe ladder binding the box + both driven devices -----

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.trigger_routing",
        name="TriggerRouting",
    )
    await bind_define_method(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="trigger_routing",
            needed_family_ids=frozenset(
                {_CAP_TIMING_CONTROLLER_ID, _CAP_CAMERA_ID, _CAP_MOTION_CONTROLLER_ID}
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="2BM_trigger_routing_practice", method_id=_METHOD_ID, site_id=_APS_SITE_ID
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_trigger_routing_plan",
            practice_id=_PRACTICE_ID,
            asset_ids=frozenset({_TIMING_ID, _CAMERA_ID, _SAMPLE_FINE_DRIVE_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Three trigger wires (camera leg + two piezo step legs) -----

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

    # The Timing box: genesis + Family (from install) + its 3 output ports.
    timing_events, _ = await deps.event_store.load("Asset", _TIMING_ID)
    timing_types = [ev.event_type for ev in timing_events]
    assert timing_types == [
        "AssetRegistered",
        "AssetFamilyAdded",
        *["AssetPortAdded"] * 3,
    ], f"Timing: unexpected event sequence {timing_types}"

    # The Camera: genesis + Family + its single trigger INPUT port.
    camera_events, _ = await deps.event_store.load("Asset", _CAMERA_ID)
    assert [ev.event_type for ev in camera_events] == [
        "AssetRegistered",
        "AssetFamilyAdded",
        "AssetPortAdded",
    ], f"Camera: unexpected event sequence {[ev.event_type for ev in camera_events]}"

    # The NV200D piezo: genesis + Family + its two step INPUT ports.
    piezo_events, _ = await deps.event_store.load("Asset", _SAMPLE_FINE_DRIVE_ID)
    assert [ev.event_type for ev in piezo_events] == [
        "AssetRegistered",
        "AssetFamilyAdded",
        *["AssetPortAdded"] * 2,
    ], f"SampleFineDrive: unexpected event sequence {[ev.event_type for ev in piezo_events]}"

    # Plan stream carries exactly the three wires. Assert the 4-tuple
    # identities, including the camera-trigger leg specifically (the
    # item_060 headline path), not just the count.
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
    assert _WIRE_CAMERA in actual_wires, (
        "the camera-trigger wire (Timing.camera_trigger_out -> Camera.trigger_in) is missing"
    )
