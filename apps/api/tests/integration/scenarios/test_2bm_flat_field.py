"""Flat-field capture at APS 2-BM, CORA-conducted from a Recipe.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Data, Operation, Recipe

Scenario test for the flat-field capture, modeled as a deployment Recipe and run
through the Procedure Conductor. The ceremony is a Recipe (a templated step list)
realizing the existing `cora.capability.acquisition`; an operator registers a
Procedure from it (`register_procedure_from_recipe`), and the conduct handler
re-expands the recipe into conduct steps and drives them through the ControlPort
against a soft IOC. The captured flat field is the illumination-plus-gain
reference a tomographic Run divides by; its dark sibling (`dark_field`, the
no-beam reference subtracted before the division) is a separate capture. Running
both is a Plan that composes the two captures; "normalization" is the downstream
reduction, not a CORA act.

See [[project_value_capture_stage0_design]] for the runtime-value-capture design
this scenario consumes, and [[project_flat_dark_prologue_design]] for the
ceremony design lock. See [[project_seam_model]] for why this is a deliberate
Actuate-axis move (CORA conducts), not the record-path the live 2-BM seam uses
today.

## Why this scenario exists

A conduct-path "101" that exercises the whole modeled ladder end to end:
Capability -> Recipe (step template) -> Procedure (register-from-recipe) ->
expand -> Conductor -> ControlPort -> soft IOC.

  1. Drives the Procedure Conductor on the recipe-driven conduct path (define
     recipe -> register-from-recipe -> conduct re-expands the pinned template).
     The `dark_field` sibling is record-path (hand-built `append_activities`
     entries, no Conductor); flats need conduct because the sample must move.
  2. RUNTIME VALUE CAPTURE: a `CaptureStep` reads the sample axis at execute
     time into the `captures` slot "sample_home", and a later `SetpointStep`
     with a `CaptureRef` restores the axis to it. The save-and-restore is the
     reason a flat capture is CORA-conducted: the sample must leave the beam for
     the flat and return to its aligned position afterward, which is live value
     capture, not a literal setpoint. No bespoke action body (the retired
     `staging.flats`).
  3. The flat field is a subject-less acquisition Run whose conducting phase
     Procedure (`parent_run_id`) drives the steps; the Dataset is attributed to
     the Run (`producing_run_id`), per the Run vs Procedure boundary rule.
     The soft IOC is a declared simulator, so the conduct observes `Simulated`.
     The Conductor stamps that kind on the *Procedure* terminal; the
     `conduct_phase_then_complete_run` glue then completes the parent Run
     carrying it, so the kind reaches `RunCompleted` autonomously (no
     hand-threading). This exercises the production bridge end to end: conduct
     kind -> Run terminal -> the Run-fallback derivation in `register_dataset`
     (Run kind -> `producing_actuation_kind` -> the promote gate). 2-BM's live
     captures are still TomoScan record-path, so a CORA-conducted capture is
     exploratory, but the kind no longer depends on a hand-threaded test step.

## Domain shape

The DATA need is universal across CT facilities: every pipeline (tomopy, ASTRA,
plain numpy) flat-field corrects raw projections against a flat reference (and a
dark reference). The CONCRETE sequence below follows TomoScan / 2-BM practice but
is staff-confirm-pending per the design lock's open questions on transit-safety
ordering and ceremony ORDER / FREQUENCY:

  1. Open the shutter; CAPTURE the sample's aligned position; retract the sample
     to a known out-of-beam position; acquire N flat frames; RESTORE the sample
     to the captured aligned position.
  2. Close the shutter (return to the safe state).
  3. Store the flat field so future Runs can divide by it.

The ceremony starts sample-in and ends sample-in (the restore returns the axis
to the captured aligned position), and ends shutter-closed (return to safe). The
sample transits the live beam during both the retraction and the restore (the
shutter closes only after the flats), which follows TomoScan's open-beam practice
at 2-BM (SBS as the per-scan fast shutter); confirm before any live wiring.

## Stand-in PVs + values (illustrative-pending-staff)

The soft IOC carries generic test PVs, NOT production 2-BM addresses. This
mapping is illustrative and MUST be confirmed with staff before any live-EPICS
wiring:

  - shutter -> `long_value` (0 = closed, 1 = open). The real station shutter is
    a PSS-owned categorical leaf (S02BM-PSS:SBS family) with an INVERTED sense;
    its leaf name and closed-code are unconfirmed and safety-load-bearing, so
    this scenario uses a neutral binary stand-in.
  - sample axis -> `double_value` (the SampleTop_X analog). The aligned home is
    CAPTURED at runtime; the out-of-beam position is a literal (Option A: a fixed
    safe park, not a relative nudge). The real axis, the out position, and any
    theta-park coupling are unconfirmed.
  - detector -> `cam1` (the areaDetector ADCore PV family).

Frame counts and dwell are illustrative (tiny, to keep the test fast); real
per-campaign values are operator-bound.

## What this scenario surfaces (gap-finding intent)

  - **The save-and-restore is plain recipe steps.** A `CaptureStep` records the
    observed aligned position; a `CaptureRef` setpoint returns to it. No opaque
    action body hides the motion (the retired `staging.flats` anti-pattern). The
    capture is journaled, so the observed value is auditable.
  - **Capture reads the OBSERVED value.** The restore returns the axis to where
    it actually was (the readback), not a commanded number; the restore setpoint
    uses `verify=True` so its landed value is recorded.
  - **Conducted provenance flows to the artifact autonomously.** The Dataset
    carries `producing_actuation_kind="Simulated"`, the fact that gates
    `promote_dataset` later. The conduct stamps that kind on the Procedure
    terminal, and the `conduct_phase_then_complete_run` glue completes the parent
    Run carrying it, so the kind reaches the Run terminal without hand-threading
    and `register_dataset` derives it from the Run. A live conduct would carry
    `Physical` and clear the gate.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections import Counter
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.api._run_phase_conduct import conduct_phase_then_complete_run
from cora.data.features.register_dataset import RegisterDataset
from cora.data.features.register_dataset import bind as bind_register_dataset
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import bind as bind_add_asset_family
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.operation.acquisitions import collect
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
    CaptureRef,
    RecipeActionStep,
    RecipeCaptureStep,
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

_NOW = datetime(2026, 6, 22, 10, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000020e0099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000020e00aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-0000020e0c01")
_SITE_ID = UUID("01900000-0000-7000-8000-0000020e0c02")
_FAMILY_CAMERA_ID = family_stream_id(FamilyName("Camera"))

# Illustrative-pending-staff stand-in codes / values (see module docstring).
_SHUTTER_CLOSED = 0
_SHUTTER_OPEN = 1
_FLAT_FRAMES = 3
_DWELL_S = 0.05
_SAMPLE_HOME_MM = 12.5
_SAMPLE_OUT_MM = 20.0


@pytest.mark.integration
async def test_flat_field_recipe_conducts_flats_against_softioc(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """Define the flat-field Recipe (capture-based save-and-restore), register a
    Procedure from it, conduct it to Completed against the soft IOC, and confirm
    the sample axis is restored to its captured aligned position, then register
    the flat-field Dataset with the conduct's Simulated provenance derived onto it."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(80)])

    shutter = f"{softioc}long_value"
    axis = f"{softioc}double_value"
    detector = f"{softioc}cam1"

    # ----- Recipe BC: the acquisition Capability + the flat-field Recipe -----
    #
    # The Recipe realizes the EXISTING cora.capability.acquisition. The flats
    # save-and-restore is expressed as a CaptureStep ("sample_home") + a
    # CaptureRef restore setpoint, not an action body. All-literal otherwise
    # (no BindingRef), so no parameters_schema / operator bindings.
    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.acquisition",
        name="Acquisition",
    )
    recipe_id = await bind_define_recipe(deps)(
        DefineRecipe(
            name="2BM_flat_field_recipe",
            capability_id=_CAPABILITY_ID,
            steps=(
                # flats: shutter open, remember home, retract to a fixed out
                # position, collect, restore to the captured home
                RecipeSetpointStep(address=shutter, value=_SHUTTER_OPEN, verify=True),
                RecipeCheckStep(
                    address=shutter, criterion={"kind": "equals", "expected": _SHUTTER_OPEN}
                ),
                RecipeCaptureStep(address=axis, capture_name="sample_home"),
                RecipeSetpointStep(address=axis, value=_SAMPLE_OUT_MM, verify=True),
                RecipeActionStep(
                    name="collect",
                    params={
                        "detector": detector,
                        "trigger_mode": "Internal",
                        "repetitions": _FLAT_FRAMES,
                        "dwell": _DWELL_S,
                    },
                ),
                RecipeSetpointStep(
                    address=axis, value=CaptureRef(capture_name="sample_home"), verify=True
                ),
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

    # ----- Recipe ladder + a subject-less acquisition Run to wrap the conduct -----
    #
    # Under the Run vs Procedure boundary rule the flat-field Dataset-of-record
    # makes the act a Run; the conducted ceremony below is a phase of that Run
    # (parent_run_id), and the Dataset is attributed to the Run. The Plan binds a
    # minimal detector Asset; the conduct itself drives the literal soft-IOC PVs, so
    # the Plan's asset set is illustrative-pending-staff, like the PV mapping.
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
            name="flat_field",
            capability_id=_CAPABILITY_ID,
            execution_pattern=ExecutionPattern.BATCH,
            needed_family_ids=frozenset({_FAMILY_CAMERA_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await bind_define_practice(deps)(
        DefinePractice(name="2BM_flat_field_practice", method_id=method_id, site_id=_SITE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_id = await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_flat_field_plan",
            practice_id=practice_id,
            asset_ids=frozenset({detector_asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    run_id = await bind_start_run(deps)(
        StartRun(
            name="2-BM flat field (subject-less acquisition Run)",
            plan_id=plan_id,
            subject_id=None,
            trigger_source="operator-manual; pre-scan flat field",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operation BC: register a Procedure from the Recipe (lands Defined) -----
    expander = InMemoryRecipeExpander()
    procedure_id = await bind_register_from_recipe(deps, expansion_port=expander)(
        RegisterProcedureFromRecipe(
            name="2-BM flat field (conducted, illustrative campaign)",
            kind="flat_field",
            target_asset_ids=(),
            parent_run_id=run_id,
            recipe_id=recipe_id,
            bindings={},
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Conduct: the handler re-expands the pinned recipe + drives the soft IOC -----
    #
    # The soft IOC is a declared simulator (a real CA speaker that is not real
    # hardware); routing through the registry with is_simulated=True makes the
    # conduct observe Simulated.
    port = EpicsCaControlPort()
    registry = ControlPortRegistry()
    registry.register(softioc, port, is_simulated=True)
    step_store = PostgresActivityStore(db_pool)
    conductor = Conductor(
        control_port=registry,
        append_step=bind_append(deps, step_store=step_store),
        clock=deps.clock,
        id_generator=deps.id_generator,
        action_registry=InMemoryActionRegistry({"collect": collect}),
        start_procedure=bind_start(deps),
        complete_procedure=bind_complete(deps),
        abort_procedure=bind_abort(deps),
    )
    conduct = bind_conduct(deps, conductor=conductor, expansion_port=expander)

    try:
        # The aligned home the CaptureStep observes + the restore returns to.
        await port.write(axis, _SAMPLE_HOME_MM, wait=True)
        # The conduct->complete-Run glue conducts the phase Procedure (recipe-
        # driven: empty caller steps re-expand the pinned template) THEN completes
        # the parent Run carrying the conduct's observed kind. This is the
        # production bridge; the scenario no longer threads the kind by hand.
        result = await conduct_phase_then_complete_run(
            run_id=run_id,
            procedure_id=procedure_id,
            conduct_procedure=conduct,
            complete_run=bind_complete_run(deps),
            abort_run=bind_abort_run(deps),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    finally:
        await registry.aclose()

    # ----- Conduct outcome: all eight steps ran, conduct observed Simulated -----

    assert result.succeeded is True
    assert result.completed_count == 8
    assert result.actuation_kind == ActuationKind.SIMULATED.value

    # ----- Procedure FSM stream: Registered (from recipe) -> ... -> Completed -----

    events, _ = await deps.event_store.load("Procedure", procedure_id)
    event_types = [e.event_type for e in events]
    assert event_types[0] == "ProcedureRegistered"
    # the recipe-driven genesis pins a template-expansion provenance event
    assert "RecipeExpansionRecorded" in event_types
    assert "ProcedureStarted" in event_types
    assert event_types[-1] == "ProcedureCompleted"
    # The Procedure is a phase of the acquisition Run (the headline modeling
    # claim): its genesis carries parent_run_id back to the Run.
    registered = next(e for e in events if e.event_type == "ProcedureRegistered")
    assert registered.payload["parent_run_id"] == str(run_id)

    # ----- Run FSM stream: the subject-less acquisition Run that wraps the phase -----
    #
    # The Run was started subject-less; the glue above already drove it to
    # RunCompleted carrying the kind (the full terminal stream is asserted below).
    run_events, _ = await deps.event_store.load("Run", run_id)
    assert run_events[0].event_type == "RunStarted"
    assert run_events[0].payload["subject_id"] is None

    # ----- Journal: eight logical step entries + five pre-effect markers -----
    #
    # The clock is frozen so all entries share sampled_at; assert on the
    # order-independent multiset AND the clock/id-independent step_index set.
    # Eight steps: 4 setpoints (idx 0,3,5,6), 2 checks (1,7), 1 action (4),
    # 1 capture (2). Setpoints + actions are side-effecting (one pre-effect
    # in_flight marker each = 5); checks + capture are reads (no marker).
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT step_kind, payload FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1",
            procedure_id,
        )
    logical = [r for r in rows if r["payload"]["result"] != "in_flight"]
    markers = [r for r in rows if r["payload"]["result"] == "in_flight"]
    assert Counter(r["step_kind"] for r in logical) == {
        "setpoint": 4,
        "check": 2,
        "action": 1,
        "capture": 1,
    }
    assert {r["payload"]["step_index"] for r in logical} == set(range(8))
    assert {r["payload"]["step_index"] for r in markers} == {0, 3, 4, 5, 6}

    # ----- The capture recorded the OBSERVED home, and the CaptureRef restore
    #       resolved to it (the runtime-value-capture round-trip) -----
    capture_entry = next(r for r in logical if r["step_kind"] == "capture")
    assert capture_entry["payload"]["capture_name"] == "sample_home"
    assert capture_entry["payload"]["captured_value"] == pytest.approx(_SAMPLE_HOME_MM)

    restore_entry = next(
        r
        for r in logical
        if r["step_kind"] == "setpoint" and r["payload"].get("capture_ref") == "sample_home"
    )
    assert restore_entry["payload"]["value"] == pytest.approx(_SAMPLE_HOME_MM)

    # The axis is back at the captured aligned home (the restore landed).
    readback_port = EpicsCaControlPort()
    try:
        axis_final = await readback_port.read(axis)
        assert axis_final.value == pytest.approx(_SAMPLE_HOME_MM)
    finally:
        await readback_port.aclose()

    # ----- The Run reached its terminal via the conduct->complete-Run glue -----
    #
    # The phase Procedure conducted the steps; the Run is the producing batch.
    # The glue (above) completed the Run carrying the conduct's observed kind, so
    # the kind reaches RunCompleted autonomously, no hand-threading. This is the
    # bridge the boundary memo formerly tracked as deferred.
    run_events, _ = await deps.event_store.load("Run", run_id)
    assert [e.event_type for e in run_events] == ["RunStarted", "RunCompleted"]

    # ----- Data BC: the flat-field Dataset (Run-produced) -----
    #
    # producing_run_id attributes the flat field to the producing Run (the boundary
    # rule: a Dataset-of-record makes the act a Run; the conducting Procedure
    # produces no Dataset). subject_id=None is the calibration idiom (no sample).
    dataset_id = await bind_register_dataset(deps)(
        RegisterDataset(
            name="2BM_flat_field_2026-06-22",
            uri="file:///data/2bm/2026-06/flat_field.h5",
            checksum_algorithm="sha256",
            checksum_value="a" * 64,
            byte_size=2448 * 2048 * 2 * _FLAT_FRAMES,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
            producing_run_id=run_id,
            producing_procedure_id=None,
            subject_id=None,
            derived_from=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    dataset_events, _ = await deps.event_store.load("Dataset", dataset_id)
    assert [e.event_type for e in dataset_events] == ["DatasetRegistered"]
    payload = dataset_events[0].payload
    assert payload["producing_run_id"] == str(run_id)
    assert payload["producing_procedure_id"] is None
    assert payload["subject_id"] is None
    # The conduct's Simulated provenance flows onto the Dataset via the Run
    # (Run-fallback derivation; the fact promote_dataset gates on).
    assert payload["producing_actuation_kind"] == ActuationKind.SIMULATED.value
