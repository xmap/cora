"""Rotation-axis characterization at APS 2-BM, CORA-conducted.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Calibration, Equipment, Operation, Recipe

Scenario test for the "characterize the rotation axis" routine at 2-BM
micro-CT: acquire a dark frame, then two projections of an alignment sample
at theta = 0 deg and theta = 180 deg, then a single COMPUTE step that finds
the rotation-axis geometry from the 0/180 pair. The conduct produces a
multi-Measurement result (center + tilt + pitch), and the rotation center is
written as a Provisional Calibration sourced from the conducting Procedure.

This is slice 6b: it REUSES the slice-6a conduct engine entirely (the
`ComputeStep` arm, `Conductor._run_compute`, `ComputePort.fetch_measurements`,
the multi-`Measurement` tuple). It is a new recipe + scenario + procedure kind
only, with ZERO engine changes. It mirrors `test_2bm_align_resolution.py`
(recipe -> register-from-recipe -> conduct re-expands -> value -> Calibration)
and exercises two things 6a's single-value scenario did not:

  1. THE MULTI-MEASUREMENT TUPLE: the ComputeStep's `fetch_measurements`
     surfaces THREE `Measurement`s (rotation_center, rotation_axis_tilt,
     rotation_axis_pitch), so `result.measurements` carries all three and the
     scenario selects the one it records by `name`.
  2. A SECOND CONDUCTED VALUE-ROUTINE: a different procedure kind
     (`rotation_characterization`) over the same engine, proving the 6a
     conduct path generalizes to another measured-Calibration routine.

It is deliberately a BARE Procedure (parent_run_id=None) that yields a
Calibration, NOT a Run with a Dataset-of-record (the Run vs Procedure
boundary: a measured calibration figure is not a Dataset-of-record). There is
no iteration, no chaining, no motor correction step: the operator corrects the
axis out-of-band; the characterization act only measures and records.

The operator-journal `center_alignment` routine (test_2bm_alignment_center.py)
reaches the same `rotation_center` Calibration quantity by a DIFFERENT path: a
hand-driven 0/180 convergence loop recorded via append_activities, not a single
CORA-conducted ComputePort measurement. Same destination quantity, distinct
routine and spine path; do not read this file as a duplicate of that one.

## Stand-in PVs + values (illustrative-pending-staff)

The soft IOC carries generic test PVs, NOT production 2-BM addresses (same
caveat as the resolution + flat-field scenarios). The compute job's `command`
+ `input_uris` are illustrative literals pointing at the well-known paths the
acquisition action bodies would have written; the in-memory substrate does not
read them (it is the value-producing fake) and the measured geometry is seeded.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.calibration.aggregates.calibration import (
    CalibrationStatus,
    MeasuredSource,
)
from cora.calibration.features.append_calibration_revision import (
    AppendCalibrationRevision,
)
from cora.calibration.features.append_calibration_revision import (
    bind as bind_append_calibration_revision,
)
from cora.calibration.features.define_calibration import DefineCalibration
from cora.calibration.features.define_calibration import (
    bind as bind_define_calibration,
)
from cora.calibration.quantities import CalibrationQuantity
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
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.in_memory_recipe_expander import InMemoryRecipeExpander
from cora.operation.aggregates.procedure import PostgresActivityStore
from cora.operation.conductor import Conductor, InMemoryActionRegistry
from cora.operation.features.abort_procedure import bind as bind_abort
from cora.operation.features.append_activities import bind as bind_append
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.conduct_procedure import ConductProcedure
from cora.operation.features.conduct_procedure import bind as bind_conduct
from cora.operation.features.register_procedure_from_recipe import RegisterProcedureFromRecipe
from cora.operation.features.register_procedure_from_recipe import bind as bind_register_from_recipe
from cora.operation.features.start_procedure import bind as bind_start
from cora.operation.ports.control_port import ActuationKind
from cora.operation.ports.measurement import Measurement
from cora.recipe.aggregates.recipe import (
    RecipeActionStep,
    RecipeComputeStep,
    RecipeSetpointStep,
)
from cora.recipe.features.define_recipe import DefineRecipe
from cora.recipe.features.define_recipe import bind as bind_define_recipe
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 6, 24, 11, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000020e2099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000020e20aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-0000020e2c01")
_FAMILY_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))

# Illustrative-pending-staff stand-in codes / values (see module docstring).
_SHUTTER_CLOSED = 0
_SHUTTER_OPEN = 1
_THETA_ZERO_DEG = 0.0
_THETA_HALF_TURN_DEG = 180.0
_DWELL_S = 0.05

# The rotation-axis geometry the in-memory compute substrate surfaces. Three
# Measurements come back from one ComputeStep (the multi-Measurement tuple);
# only the center maps to a Calibration quantity at 6b.
_MEASURED_ROTATION_CENTER_PX = 1023.4
_MEASURED_ROTATION_AXIS_TILT_DEG = 0.12
_MEASURED_ROTATION_AXIS_PITCH_DEG = -0.05


@pytest.mark.integration
async def test_align_rotation_recipe_conducts_compute_and_writes_calibration(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """Define the align-rotation Recipe (control steps + one ComputeStep), register a
    standalone Procedure from it, conduct it to Completed against the soft IOC + the
    in-memory ComputePort, surface the THREE measured rotation-axis figures on the
    result, and write a Provisional rotation_center Calibration sourced from the
    Procedure. Tilt + pitch are produced and recorded but have no Calibration
    quantity at 6b."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(80)])

    shutter = f"{softioc}long_value"
    theta = f"{softioc}double_value"
    detector = f"{softioc}cam1"

    # ----- Recipe BC: the acquisition Capability + the align-rotation Recipe -----
    #
    # The Recipe realizes the EXISTING cora.capability.acquisition. The compute
    # leg is a single RecipeComputeStep (literal fields, value-only, no
    # BindingRef): one pass, no iteration, no chaining. Control steps close the
    # shutter, take a dark frame, open the shutter, then acquire two projections
    # at theta = 0 deg and theta = 180 deg. The compute step finds the
    # rotation-axis geometry from the already-acquired 0/180 pair (input_uris are
    # authored literals naming the well-known frame paths).
    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.acquisition",
        name="Acquisition",
    )
    recipe_id = await bind_define_recipe(deps)(
        DefineRecipe(
            name="2BM_align_rotation_recipe",
            capability_id=_CAPABILITY_ID,
            steps=(
                # close shutter, acquire a dark frame (no beam)
                RecipeSetpointStep(address=shutter, value=_SHUTTER_CLOSED, verify=True),
                RecipeActionStep(
                    name="collect",
                    params={
                        "detector": detector,
                        "trigger_mode": "Internal",
                        "repetitions": 1,
                        "dwell": _DWELL_S,
                    },
                ),
                # open shutter, rotate to 0 deg, acquire projection
                RecipeSetpointStep(address=shutter, value=_SHUTTER_OPEN, verify=True),
                RecipeSetpointStep(address=theta, value=_THETA_ZERO_DEG, verify=True),
                RecipeActionStep(
                    name="collect",
                    params={
                        "detector": detector,
                        "trigger_mode": "Internal",
                        "repetitions": 1,
                        "dwell": _DWELL_S,
                    },
                ),
                # rotate to 180 deg, acquire the counterpart projection
                RecipeSetpointStep(address=theta, value=_THETA_HALF_TURN_DEG, verify=True),
                RecipeActionStep(
                    name="collect",
                    params={
                        "detector": detector,
                        "trigger_mode": "Internal",
                        "repetitions": 1,
                        "dwell": _DWELL_S,
                    },
                ),
                # find the rotation-axis geometry from the 0/180 frames (value arm)
                RecipeComputeStep(
                    command=("tomopy", "find_center"),
                    input_uris=(
                        "file:///data/2bm/align/theta_0.h5",
                        "file:///data/2bm/align/theta_180.h5",
                    ),
                    parameters={"theta_pair_deg": (_THETA_ZERO_DEG, _THETA_HALF_TURN_DEG)},
                ),
                # return theta home + close shutter (safe state)
                RecipeSetpointStep(address=theta, value=_THETA_ZERO_DEG, verify=True),
                RecipeSetpointStep(address=shutter, value=_SHUTTER_CLOSED, verify=True),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Equipment BC: the rotary-stage Asset the Calibration targets -----
    await bind_define_family(deps)(
        DefineFamily(name="RotaryStage", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    rotary_asset_id = await bind_register_asset(deps)(
        RegisterAsset(
            name="2bm-rotary-stage", tier=AssetTier.DEVICE, parent_id=None, facility_code="cora"
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_asset_family(deps)(
        AddAssetFamily(asset_id=rotary_asset_id, family_id=_FAMILY_ROTARY_STAGE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operation BC: register a standalone Procedure from the Recipe -----
    #
    # parent_run_id=None: the boundary rule keeps a measured calibration figure a
    # Procedure (no Dataset-of-record, no Run).
    expander = InMemoryRecipeExpander()
    procedure_id = await bind_register_from_recipe(deps, expansion_port=expander)(
        RegisterProcedureFromRecipe(
            name="2-BM rotation-axis characterization (conducted, illustrative campaign)",
            # noun-LAST (R6): the act CHARACTERIZES the rotation axis into a
            # measured Calibration. "characterization" is the approved noun for a
            # Procedure that measures an equipment property; distinct from the
            # focus-sharpness `resolution_alignment` routine and from the per-axis
            # correction routines (operator corrects out-of-band, not modeled).
            kind="rotation_characterization",
            target_asset_ids=(rotary_asset_id,),
            parent_run_id=None,
            recipe_id=recipe_id,
            bindings={},
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Conduct: the handler re-expands the pinned recipe + drives the substrates -----
    #
    # The soft IOC is a declared simulator; the in-memory ComputePort is the
    # value-producing fake (Simulated). Both make the conduct observe Simulated.
    # The three rotation-axis Measurements are seeded as one tuple so a single
    # ComputeStep's fetch_measurements surfaces all of them (the multi-Measurement
    # tuple under exercise).
    port = EpicsCaControlPort()
    registry = ControlPortRegistry()
    registry.register(softioc, port, is_simulated=True)
    compute_port = InMemoryComputePort()
    compute_port.set_next_measurements(
        (
            _rotation_center_measurement(_MEASURED_ROTATION_CENTER_PX),
            _rotation_axis_tilt_measurement(_MEASURED_ROTATION_AXIS_TILT_DEG),
            _rotation_axis_pitch_measurement(_MEASURED_ROTATION_AXIS_PITCH_DEG),
        )
    )
    step_store = PostgresActivityStore(db_pool)
    conductor = Conductor(
        control_port=registry,
        append_step=bind_append(deps, step_store=step_store),
        clock=deps.clock,
        id_generator=deps.id_generator,
        action_registry=InMemoryActionRegistry({"collect": collect}),
        compute_port=compute_port,
        start_procedure=bind_start(deps),
        complete_procedure=bind_complete(deps),
        abort_procedure=bind_abort(deps),
    )
    conduct = bind_conduct(deps, conductor=conductor, expansion_port=expander)

    try:
        # Park theta at the home the first rotation setpoint expects.
        await port.write(theta, _THETA_ZERO_DEG, wait=True)
        # Recipe-driven conduct: empty caller steps re-expand the pinned template.
        result = await conduct(
            ConductProcedure(procedure_id=procedure_id, steps=()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    finally:
        await registry.aclose()
        await compute_port.aclose()

    # ----- Conduct outcome: all steps ran, the three rotation figures surfaced -----

    assert result.succeeded is True
    # 10 steps: 6 setpoints (close, open, 0deg, 180deg, home, close) + 3 actions
    # (dark, 0deg, 180deg) + 1 compute.
    assert result.completed_count == 10
    # Both the simulated control routes AND the simulated compute substrate were
    # touched, so the conduct observes Simulated (the compute kind folds in).
    assert result.actuation_kind == ActuationKind.SIMULATED.value

    # The multi-Measurement validation: the single ComputeStep surfaced all THREE
    # rotation-axis figures on the result, selectable by name.
    assert len(result.measurements) == 3
    by_name = {m.name: m for m in result.measurements}
    assert set(by_name) == {"rotation_center", "rotation_axis_tilt", "rotation_axis_pitch"}
    center = by_name["rotation_center"]
    assert center.value == pytest.approx(_MEASURED_ROTATION_CENTER_PX)
    assert center.units == "pixel"
    assert by_name["rotation_axis_tilt"].value == pytest.approx(_MEASURED_ROTATION_AXIS_TILT_DEG)
    assert by_name["rotation_axis_tilt"].units == "deg"
    assert by_name["rotation_axis_pitch"].value == pytest.approx(_MEASURED_ROTATION_AXIS_PITCH_DEG)
    assert by_name["rotation_axis_pitch"].units == "deg"

    # ----- Procedure FSM stream: Registered (from recipe) -> ... -> Completed -----

    events, _ = await deps.event_store.load("Procedure", procedure_id)
    event_types = [e.event_type for e in events]
    assert event_types[0] == "ProcedureRegistered"
    assert "RecipeExpansionRecorded" in event_types
    assert "ProcedureStarted" in event_types
    assert event_types[-1] == "ProcedureCompleted"
    # Standalone Procedure: no parent Run.
    registered = next(e for e in events if e.event_type == "ProcedureRegistered")
    assert registered.payload["parent_run_id"] is None

    # ----- Journal: the compute step recorded all three Measurements (name + units) -----
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT step_kind, payload FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1",
            procedure_id,
        )
    compute_logical = [
        r for r in rows if r["step_kind"] == "compute" and r["payload"]["result"] == "ok"
    ]
    assert len(compute_logical) == 1
    compute_payload = compute_logical[0]["payload"]
    assert compute_payload["status"] == "Succeeded"
    recorded_names = [m["name"] for m in compute_payload["measurements"]]
    assert recorded_names == ["rotation_center", "rotation_axis_tilt", "rotation_axis_pitch"]
    # The compute step is side-effecting, so it also recorded a pre-effect marker.
    compute_markers = [
        r for r in rows if r["step_kind"] == "compute" and r["payload"]["result"] == "in_flight"
    ]
    assert len(compute_markers) == 1

    # ----- Calibration write: rotation_center ONLY, Provisional, MeasuredSource -----
    #
    # The conducting Procedure is the ACT; the Calibration BC stores the RESULT.
    # We record ONLY the rotation_center figure: tilt + pitch are produced and
    # recorded Measurements but have NO Calibration quantity at 6b (only
    # rotation_center exists in calibration/quantities/). Tilt + pitch quantities
    # are a future addition for when a downstream consumer needs them.
    calibration_id = await bind_define_calibration(deps)(
        DefineCalibration(
            target_id=rotary_asset_id,
            quantity=CalibrationQuantity.ROTATION_CENTER,
            operating_point={"energy": 25.0, "optics_config": "5x"},
            description="Rotation centre from the 2-BM rotation-characterization routine.",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    revision_id = await bind_append_calibration_revision(deps)(
        AppendCalibrationRevision(
            calibration_id=calibration_id,
            # center.value is the measured scalar; shape it into the rotation_center
            # {"center": ...} VALUE_SCHEMA dict here (the name->schema-key bridge,
            # like the 6a sibling). The port stays quantity-agnostic.
            value={"center": center.value},
            status=CalibrationStatus.PROVISIONAL,
            source=MeasuredSource(procedure_id=procedure_id),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert revision_id is not None

    # The Calibration stream proves the act -> result link: the appended revision
    # cites this Procedure as its MeasuredSource, Provisional until blessed.
    calibration_events, _ = await deps.event_store.load("Calibration", calibration_id)
    assert [e.event_type for e in calibration_events] == [
        "CalibrationDefined",
        "CalibrationRevisionAppended",
    ]
    appended = calibration_events[1].payload
    assert appended["status"] == CalibrationStatus.PROVISIONAL.value
    assert appended["source_procedure_id"] == str(procedure_id)
    assert appended["value"] == {"center": pytest.approx(_MEASURED_ROTATION_CENTER_PX)}


def _rotation_center_measurement(center_px: float) -> Measurement:
    """Build the rotation-center `Measurement` the in-memory ComputePort surfaces.

    `name="rotation_center"` selects the Calibration quantity at the scenario's
    name->schema-key bridge; the value is the measured scalar (the center pixel),
    shaped into the rotation_center `{"center": ...}` VALUE_SCHEMA dict at the
    Calibration write (like the 6a sibling). `units="pixel"` matches the
    rotation_center value schema.
    """
    return Measurement(
        value=center_px,
        kind="Scalar",
        quality="Good",
        produced_at=_NOW,
        name="rotation_center",
        units="pixel",
    )


def _rotation_axis_tilt_measurement(tilt_deg: float) -> Measurement:
    """Build the rotation-axis-tilt `Measurement`.

    Produced + recorded at 6b but with NO Calibration quantity yet (a future
    addition when a consumer needs it).
    """
    return Measurement(
        value=tilt_deg,
        kind="Scalar",
        quality="Good",
        produced_at=_NOW,
        name="rotation_axis_tilt",
        units="deg",
    )


def _rotation_axis_pitch_measurement(pitch_deg: float) -> Measurement:
    """Build the rotation-axis-pitch `Measurement`.

    Produced + recorded at 6b but with NO Calibration quantity yet (a future
    addition when a consumer needs it).
    """
    return Measurement(
        value=pitch_deg,
        kind="Scalar",
        quality="Good",
        produced_at=_NOW,
        name="rotation_axis_pitch",
        units="deg",
    )
