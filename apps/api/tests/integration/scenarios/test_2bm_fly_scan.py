"""Fly-scan tomography at APS 2-BM, CORA-conducted from a Recipe.

cluster: Runs
archetype: routine
bc_primary: Operation
bc_touches: Data, Equipment, Operation, Recipe, Run

Scenario test for the fly scan, modelled as a deployment Recipe and driven
through the Procedure Conductor against a soft IOC. It is the conduct-path
sibling of `test_2bm_continuous_rotation_sweep.py`, which is record-path: there
TomoScan drives and CORA records N child Runs; here CORA conducts the sweep
itself and TomoScan is not involved.

## Why this scenario exists

It is the rehearsal for the exchange demonstration in
`papers/2026-jsr-cora/notes/experiment-plan.md` (D3), the one procedure family
with edge and floor active at once. Everything below runs before the beamtime,
against a simulator, so the live attempt has a record to be diffed against
rather than a first attempt to debug.

The `continuous` action body already implements the fly-scan ordering
internally: it moves the axis to `start` with a blocking write (the taxi),
arms the detector, then commands motion toward `stop` with a non-blocking
write so the emitter sees motion and arm overlap. What this scenario adds is
the layer above it: a Recipe that expresses the whole scan as an ordered step
list, an emitter configured by setpoint steps that precede the action, and the
conduct running as a phase of a Run.

## External triggering is refused, not attempted

`continuous` now refuses any non-Internal `trigger_mode` with
`UnwiredExternalTriggerError` before writing a single detector PV (see
`cora.operation.acquisitions`): CORA does not configure the trigger emitter,
so arming the detector for pulses nothing arranged would hang against real
hardware. This scenario's Recipe still arms the emitter with setpoint steps
that PRECEDE the action, exactly as a real fly scan would; what changed is
the action step that follows them. It no longer runs the sweep.

The refusal is an ordinary halt, not an escape. `UnwiredExternalTriggerError`
subclasses `ActionRefusedError`, which the Conductor catches on the same arm
as a substrate error, so the step records a `failed` outcome and both the
Procedure and the Run reach a terminal state. That distinction is the point:
an uncaught raise would leave the Procedure at `ProcedureStarted` forever,
a record asserting a run still in progress against a beamline standing idle.

What this scenario does NOT claim is that the beamline is left tidy. A halt
returns from the step loop, so the three teardown steps after the action
never run: the emitter stays armed and the shutter stays open, exactly as
they would after any other failed step. Compensating for that needs a step
list that always runs, which CORA does not have and this change does not add.

The `source` field naming the emitter is still evidence-only by construction
(the action body never writes it); this scenario proves the stronger claim
that it never gets the chance to write anything for ExternalEdge, because
the guard fires first.

## What the simulator can and cannot rehearse

The soft IOC's `cam1:Acquire_RBV` is seeded to the always-Done state, so a
successfully-arming body's poll loop would exit on the first read (see
`tests/integration/_softioc.py`); that machinery is exercised by
`test_2bm_flat_field.py` and the other Internal-trigger scenarios. This
scenario's ExternalEdge sweep never reaches the poll loop at all, so what it
proves instead is the refusal itself: the guard fires before any detector PV
write, over real EPICS CA framing, inside a full Recipe-driven conduct.

PV names are pure test-shape (`double_value`, `enum_value`), NOT production
2-BM addresses, exactly as in `test_2bm_flat_field.py`. The sweep geometry and
the arm value are illustrative-pending-staff; the arming sequence itself is a
staff-confirmation item in the experiment plan.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.api._run_phase_conduct import conduct_phase_then_complete_run
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import bind as bind_add_asset_family
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.operation.acquisitions import continuous
from cora.operation.adapters.control_port_registry import ControlPortRegistry
from cora.operation.adapters.epics_ca_control_port import EpicsCaControlPort
from cora.operation.adapters.in_memory_recipe_expander import InMemoryRecipeExpander
from cora.operation.aggregates.procedure import PostgresActivityStore
from cora.operation.conductor import Conductor, InMemoryActionRegistry
from cora.operation.features.abort_procedure import bind as bind_abort
from cora.operation.features.append_activities import bind as bind_append
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.conduct_procedure import bind as bind_conduct
from cora.operation.features.register_procedure_from_recipe import RegisterProcedureFromRecipe
from cora.operation.features.register_procedure_from_recipe import bind as bind_register_from_recipe
from cora.operation.features.start_procedure import bind as bind_start
from cora.recipe.aggregates.method import ExecutionPattern
from cora.recipe.aggregates.recipe import (
    RecipeActionStep,
    RecipeCheckStep,
    RecipeSetpointStep,
)
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_plan import bind as bind_define_plan
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.define_practice import bind as bind_define_practice
from cora.recipe.features.define_recipe import DefineRecipe
from cora.recipe.features.define_recipe import bind as bind_define_recipe
from cora.run.features.abort_run import bind as bind_abort_run
from cora.run.features.complete_run import bind as bind_complete_run
from cora.run.features.start_run import StartRun
from cora.run.features.start_run import bind as bind_start_run
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 6, 22, 11, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000020f0099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000020f00aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-0000020f0c01")
_SITE_ID = UUID("01900000-0000-7000-8000-0000020f0c02")
_FAMILY_CAMERA_ID = family_stream_id(FamilyName("Camera"))

# Illustrative-pending-staff stand-in codes / values (see module docstring).
_SHUTTER_CLOSED = 0
_SHUTTER_OPEN = 1
# The emitter arm is an mbbo, so it is WRITTEN by index and READS BACK as its
# label. Both forms appear below for that reason, not by oversight.
_PSO_DISARMED = 0
_PSO_ARMED = 1
_PSO_ARMED_LABEL = "on"
_RUN_UP_DEG = -5.0
_SWEEP_END_DEG = 180.0
_PROJECTIONS = 8
_DWELL_S = 0.05
_RATE_DEG_S = 30.0


@pytest.mark.integration
async def test_fly_scan_recipe_external_trigger_halts_and_aborts_before_any_detector_write(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """Define the fly-scan Recipe, register a Procedure from it, and conduct it
    against the soft IOC: the emitter-arming setpoint steps run and stick, then
    the ExternalEdge action step is refused before touching a single detector
    PV, recording a failed outcome and aborting the Procedure and the Run."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(80)])

    shutter = f"{softioc}long_value"
    rotary = f"{softioc}double_value"
    emitter = f"{softioc}enum_value"
    detector = f"{softioc}cam1"

    # ----- Recipe BC: the fly-scan Capability + the fly-scan Recipe -----
    #
    # The emitter is armed by a setpoint step and checked by a check step, both
    # BEFORE the action. The action names it as `source` and never writes it.
    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.flyscan",
        name="FlyScan Tomography",
    )
    recipe_id = await bind_define_recipe(deps)(
        DefineRecipe(
            name="2BM_fly_scan_recipe",
            capability_id=_CAPABILITY_ID,
            steps=(
                RecipeSetpointStep(address=shutter, value=_SHUTTER_OPEN, verify=True),
                RecipeCheckStep(
                    address=shutter, criterion={"kind": "equals", "expected": _SHUTTER_OPEN}
                ),
                # Emitter side: armed here, named (not written) by the action.
                RecipeSetpointStep(address=emitter, value=_PSO_ARMED, verify=True),
                RecipeCheckStep(
                    address=emitter,
                    criterion={"kind": "equals", "expected": _PSO_ARMED_LABEL},
                ),
                RecipeActionStep(
                    name="continuous",
                    params={
                        "detector": detector,
                        "trigger_mode": "ExternalEdge",
                        "polarity": "Rising",
                        "source": emitter,
                        "axis": rotary,
                        "start": _RUN_UP_DEG,
                        "stop": _SWEEP_END_DEG,
                        "rate": _RATE_DEG_S,
                        "repetitions": _PROJECTIONS,
                        "dwell": _DWELL_S,
                    },
                ),
                RecipeSetpointStep(address=emitter, value=_PSO_DISARMED, verify=True),
                # return to safe: shutter closed
                RecipeSetpointStep(address=shutter, value=_SHUTTER_CLOSED, verify=True),
                RecipeCheckStep(
                    address=shutter, criterion={"kind": "equals", "expected": _SHUTTER_CLOSED}
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Recipe ladder + the acquisition Run the conduct is a phase of -----
    await bind_define_family(deps)(
        DefineFamily(name="Camera", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    detector_asset_id = await bind_register_asset(deps)(
        RegisterAsset(
            name="2bm-detector", tier=AssetTier.DEVICE, parent_id=None, facility_code="cora"
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_asset_family(deps)(
        AddAssetFamily(asset_id=detector_asset_id, family_id=_FAMILY_CAMERA_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    method_id = await bind_define_method(deps)(
        DefineMethod(
            name="flyscan_acquisition",
            capability_id=_CAPABILITY_ID,
            execution_pattern=ExecutionPattern.BATCH,
            needed_family_ids=frozenset({_FAMILY_CAMERA_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await bind_define_practice(deps)(
        DefinePractice(name="2BM_fly_scan_practice", method_id=method_id, site_id=_SITE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_id = await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_fly_scan_plan",
            practice_id=practice_id,
            asset_ids=frozenset({detector_asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    run_id = await bind_start_run(deps)(
        StartRun(
            name="2-BM fly scan (conducted)",
            plan_id=plan_id,
            subject_id=None,
            trigger_source="operator-manual; fly-scan exchange rehearsal",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    expander = InMemoryRecipeExpander()
    procedure_id = await bind_register_from_recipe(deps, expansion_port=expander)(
        RegisterProcedureFromRecipe(
            name="2-BM fly scan (conducted, illustrative campaign)",
            kind="flyscan_acquisition",
            target_asset_ids=(),
            parent_run_id=run_id,
            recipe_id=recipe_id,
            bindings={},
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Conduct against the soft IOC, declared a simulator -----
    port = EpicsCaControlPort()
    registry = ControlPortRegistry()
    registry.register_substrate_port(softioc, port, "epics_ca", is_simulated=True)
    step_store = PostgresActivityStore(db_pool)
    conductor = Conductor(
        control_port=registry,
        append_step=bind_append(deps, step_store=step_store),
        clock=deps.clock,
        id_generator=deps.id_generator,
        action_registry=InMemoryActionRegistry({"continuous": continuous}),
        start_procedure=bind_start(deps),
        complete_procedure=bind_complete(deps),
        abort_procedure=bind_abort(deps),
    )
    conduct = bind_conduct(deps, conductor=conductor, expansion_port=expander)

    try:
        await registry.write(emitter, _PSO_DISARMED, wait=True)
        outcome = await conduct_phase_then_complete_run(
            run_id=run_id,
            procedure_id=procedure_id,
            conduct_procedure=conduct,
            complete_run=bind_complete_run(deps),
            abort_run=bind_abort_run(deps),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        emitter_after = await registry.read(emitter)
        rotary_after = await registry.read(rotary)
        trigger_mode_after = await registry.read(f"{detector}:TriggerMode")
    finally:
        await registry.aclose()

    # ----- No PV the action would have touched moved -----
    #
    # The guard fires before any detector write, so the detector's TriggerMode
    # is untouched and the axis never taxied toward `start`. The emitter is
    # still armed: its own teardown setpoint step is AFTER the action in the
    # Recipe's step list, and the raise never let the conduct reach it.
    assert trigger_mode_after.value == "Internal"
    assert rotary_after.value == pytest.approx(0.0)
    assert emitter_after.value == _PSO_ARMED_LABEL

    # ----- The refusal is an ordinary recorded halt, not an escape -----
    #
    # `UnwiredExternalTriggerError` subclasses `ActionRefusedError`, which the
    # Conductor catches on the same arm as a substrate error. The conduct
    # therefore RETURNS a failure rather than raising through the glue, which
    # is what lets both aggregates reach a terminal state below.
    assert outcome.succeeded is False
    assert outcome.failure is not None
    assert outcome.failure.error_class == "UnwiredExternalTriggerError"
    assert outcome.failure.source_kind == "action"
    assert "ExternalEdge" in outcome.failure.message

    # ----- Procedure stream: started, then ABORTED -----
    #
    # The Procedure must not be left at `ProcedureStarted`. A stream with no
    # terminal event reads, forever, as a run still in progress, which is a
    # record that contradicts a beamline standing idle. A refused step is a
    # halt like any other, so the Procedure aborts and says so.
    events, _ = await deps.event_store.load("Procedure", procedure_id)
    event_types = [e.event_type for e in events]
    assert event_types[0] == "ProcedureRegistered"
    assert "RecipeExpansionRecorded" in event_types
    assert "ProcedureStarted" in event_types
    assert "ProcedureCompleted" not in event_types
    assert "ProcedureAborted" in event_types
    registered = next(e for e in events if e.event_type == "ProcedureRegistered")
    assert registered.payload["parent_run_id"] == str(run_id)

    # ----- Activity journal: the refused action recorded its own failure -----
    #
    # The two setpoint/check pairs before the action (shutter open, emitter
    # armed) recorded their outcome normally, and the action recorded a
    # `failed` outcome naming the refusal beside its in-flight marker. That
    # outcome row is the point of routing `ActionRefusedError` through the
    # Conductor's failure arm: without it the journal would show a step that
    # started and never resolved. The three teardown steps after the action
    # (disarm emitter, close shutter, check closed) still never ran, because
    # a halt returns from the step loop rather than continuing; the emitter
    # is left armed and the shutter open, which no part of this change
    # addresses and which a compensating step list would have to.
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT step_kind, payload FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1",
            procedure_id,
        )

    # No ORDER BY: the fixed test clock stamps every entry with the same
    # `sampled_at`, so row order here is not the step order. Membership,
    # not position, is what this journal check can prove.
    completed_rows = [r for r in rows if r["payload"].get("result") != "in_flight"]
    assert len(completed_rows) == 5
    setpoint_addresses = {
        r["payload"]["address"] for r in completed_rows if r["step_kind"] == "setpoint"
    }
    assert setpoint_addresses == {shutter, emitter}

    action_rows = [r for r in rows if r["step_kind"] == "action"]
    assert len(action_rows) == 2
    action_results = {r["payload"]["result"] for r in action_rows}
    assert action_results == {"in_flight", "failed"}
    failed_action = next(r for r in action_rows if r["payload"]["result"] == "failed")
    assert failed_action["payload"]["error_class"] == "UnwiredExternalTriggerError"
