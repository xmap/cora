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

## The emitter split is the point

The claim under test is the narrowest part of the placement rule. The
acquisition primitive writes only the detector-side trigger variables. The
emitter that will actually fire the trigger train, at 2-BM the Aerotech PSO,
is configured by steps that PRECEDE the action, and the field naming it in the
request (`source`) is recorded as evidence rather than written by the action.
Both halves are asserted below: the emitter appears as the address of a
setpoint step, and it appears again in the action's evidence, and those are
two different steps.

## What the simulator can and cannot rehearse

The soft IOC's `cam1:Acquire_RBV` is seeded to the always-Done state, so the
body's poll loop exits on the first read (see `tests/integration/_softioc.py`).
That means this tier proves the step ordering, the EPICS wire framing, the
emitter split, and the provenance the conduct records. It does NOT prove
trigger consumption: nothing here fires pulses, and no detector counts them.
That is what commissioning time exercises, with the real PSO.

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
from cora.operation.ports.control_port import ActuationKind
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
_PSO_DISARMED_LABEL = "off"
_PSO_ARMED_LABEL = "on"
_RUN_UP_DEG = -5.0
_SWEEP_END_DEG = 180.0
_PROJECTIONS = 8
_DWELL_S = 0.05
_RATE_DEG_S = 30.0


@pytest.mark.integration
async def test_fly_scan_recipe_conducts_sweep_against_softioc(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """Define the fly-scan Recipe, register a Procedure from it, conduct it to
    Completed against the soft IOC, and confirm the emitter was configured by a
    setpoint step that preceded the action while the action only named it."""
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
        result = await conduct_phase_then_complete_run(
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
    finally:
        await registry.aclose()

    # ----- Conduct outcome: all eight steps ran, conduct observed Simulated -----

    assert result.succeeded is True
    assert result.completed_count == 8
    assert result.actuation_kind == ActuationKind.SIMULATED.value

    # The sweep ran to its end angle and the emitter was disarmed by its own
    # teardown step, not left armed by the action.
    assert rotary_after.value == pytest.approx(_SWEEP_END_DEG)
    assert emitter_after.value == _PSO_DISARMED_LABEL

    # ----- Procedure stream: recipe-driven genesis pins its expansion -----

    events, _ = await deps.event_store.load("Procedure", procedure_id)
    event_types = [e.event_type for e in events]
    assert event_types[0] == "ProcedureRegistered"
    assert "RecipeExpansionRecorded" in event_types
    assert event_types[-1] == "ProcedureCompleted"
    registered = next(e for e in events if e.event_type == "ProcedureRegistered")
    assert registered.payload["parent_run_id"] == str(run_id)

    # ----- The emitter split, asserted on the journal -----
    #
    # Two facts, and they must come from two different steps. The emitter is the
    # address of setpoint steps (it was configured), and it is the `source` in
    # the action's evidence (it was named). If the action had written it, there
    # would be no setpoint step carrying that address.
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT step_kind, payload FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1 AND payload->>'result' IS DISTINCT FROM 'in_flight'",
            procedure_id,
        )

    setpoint_addresses = [r["payload"]["address"] for r in rows if r["step_kind"] == "setpoint"]
    assert emitter in setpoint_addresses

    action_rows = [r for r in rows if r["step_kind"] == "action"]
    assert len(action_rows) == 1
    evidence = action_rows[0]["payload"]["result_data"]
    assert evidence["source"] == emitter
    assert evidence["polarity"] == "Rising"
    assert evidence["trigger_mode"] == "ExternalEdge"
    # The rate is carried as evidence too; the body does not write an axis-rate
    # PV, which is why the recipe would set one itself on a real deployment.
    assert evidence["rate_requested"] == pytest.approx(_RATE_DEG_S)
    assert evidence["axis_start_requested"] == pytest.approx(_RUN_UP_DEG)
    assert evidence["axis_stop_requested"] == pytest.approx(_SWEEP_END_DEG)
    assert evidence["repetitions_requested"] == _PROJECTIONS
