"""AUTO rotation-axis alignment at APS 2-BM, CORA-conducted convergence loop.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Calibration, Equipment, Operation, Recipe

Scenario test for the "iterate-measure-correct the rotation axis until it
converges" routine at 2-BM micro-CT. This is slice 6c (AUTO align): where 6b
(`test_2bm_align_rotation.py`) MEASURES the rotation-axis geometry in a single
pass and records it, this DRIVES a multi-pass convergence loop that measures
the rotation center, corrects the axis toward it, re-measures, and repeats until
the measured center lands within tolerance OR a patience cap trips.

It exercises the two slice-6c additions over the 6a/6b engine:

  1. C1 CHAINING (a field, not a union arm): a single `RecipeComputeStep`
     carries `capture_name="rotation_center"`, so the produced Measurement's
     value deposits into the per-pass captures bus; a same-pass
     `RecipeSetpointStep` with a `CaptureRef` then drives the rotary axis to
     that value (arithmetic-free correction).
  2. I3 ITERATION (`conduct_until_converged`): CORA re-walks the ONE-pass recipe
     until `_criterion_matches(WithinToleranceCriterion(...), captures["rotation_center"])`
     holds, evaluated OUT of the captures bus after each pass (option C: no
     walked convergence CheckStep). The in-memory ComputePort seeds a SEQUENCE
     of centers shrinking into tolerance by pass N (one consumed per submit).

It is a BARE Procedure (parent_run_id=None) yielding a Calibration, NOT a Run
with a Dataset-of-record (the Run vs Procedure boundary). The rotation center
is written as a Provisional Calibration sourced from the conducting Procedure
from the FINAL converged measured value.

## Stand-in PVs + values (illustrative-pending-staff)

The soft IOC carries generic test PVs, NOT production 2-BM addresses (same
caveat as the 6a/6b scenarios). The compute job's `command` + `input_uris` are
illustrative literals; the in-memory substrate does not read them (it is the
value-producing fake) and the per-pass measured centers are seeded.
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
from cora.operation.aggregates.procedure import PostgresActivityStore, load_procedure
from cora.operation.conductor import (
    Conductor,
    InMemoryActionRegistry,
    WithinToleranceCriterion,
)
from cora.operation.features.abort_procedure import bind as bind_abort
from cora.operation.features.append_activities import bind as bind_append
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.conduct_until_converged import ConductUntilConverged
from cora.operation.features.conduct_until_converged import bind as bind_conduct_until_converged
from cora.operation.features.end_iteration import bind as bind_end_iteration
from cora.operation.features.register_procedure_from_recipe import RegisterProcedureFromRecipe
from cora.operation.features.register_procedure_from_recipe import bind as bind_register_from_recipe
from cora.operation.features.start_iteration import bind as bind_start_iteration
from cora.operation.features.start_procedure import bind as bind_start
from cora.operation.ports.control_port import ActuationKind
from cora.operation.ports.measurement import Measurement
from cora.recipe.aggregates.recipe import (
    CaptureRef,
    RecipeActionStep,
    RecipeComputeStep,
    RecipeSetpointStep,
)
from cora.recipe.features.define_recipe import DefineRecipe
from cora.recipe.features.define_recipe import bind as bind_define_recipe
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 6, 24, 11, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000020e3099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000020e30aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-0000020e3c01")
_FAMILY_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))

_SHUTTER_CLOSED = 0
_SHUTTER_OPEN = 1
_THETA_ZERO_DEG = 0.0
_THETA_HALF_TURN_DEG = 180.0
_DWELL_S = 0.05

_CONVERGENCE_NAME = "rotation_center"
# Target center (the alignment goal) + tolerance. The seeded sequence of
# measured centers shrinks toward the target and lands within tolerance by the
# final pass.
_TARGET_CENTER_PX = 1024.0
_TOLERANCE_PX = 0.5
# A converging sequence (3 passes): far, closer, within tolerance.
_CONVERGING_CENTERS_PX = (1027.0, 1025.2, 1024.3)
_FINAL_CONVERGED_CENTER_PX = _CONVERGING_CENTERS_PX[-1]
# A never-converging sequence (cap variant): always far from target.
_DIVERGENT_CENTERS_PX = (1030.0, 1031.0, 1029.5)
_MAX_UNCONVERGED = 3


def _rotation_center_measurement(center_px: float) -> Measurement:
    """The rotation-center `Measurement` the in-memory ComputePort surfaces per pass.

    `name=_CONVERGENCE_NAME` is BOTH the captures-slot the C1 deposit fills (read
    by the same-pass CaptureRef correction + the convergence predicate) AND the
    name the scenario selects to write the Calibration. `units="pixel"` matches
    the rotation_center value schema."""
    return Measurement(
        value=center_px,
        kind="Scalar",
        quality="Good",
        produced_at=_NOW,
        name=_CONVERGENCE_NAME,
        units="pixel",
    )


def _one_pass_recipe_steps(rotation_center_addr: str, shutter: str, theta: str, detector: str):
    """ONE convergence pass: acquire 0/180, compute the center (deposit), correct the axis."""
    return (
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
        # find the rotation center from the 0/180 frames; DEPOSIT it (C1).
        RecipeComputeStep(
            command=("tomopy", "find_center"),
            input_uris=(
                "file:///data/2bm/align/theta_0.h5",
                "file:///data/2bm/align/theta_180.h5",
            ),
            parameters={"theta_pair_deg": (_THETA_ZERO_DEG, _THETA_HALF_TURN_DEG)},
            capture_name=_CONVERGENCE_NAME,
        ),
        # correct the rotary axis to the measured center (arithmetic-free CaptureRef).
        RecipeSetpointStep(
            address=rotation_center_addr,
            value=CaptureRef(_CONVERGENCE_NAME),
            verify=True,
        ),
    )


async def _build_align_routine(
    db_pool: asyncpg.Pool,
    softioc: str,
    *,
    centers_sequence: tuple[float, ...],
):
    """Define the recipe + register the Procedure + wire the convergence-loop handler.

    Returns (deps, conduct_handler, procedure_id, rotary_asset_id, registry,
    compute_port, theta) so the caller drives + asserts, then closes the ports.
    """
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(120)])

    shutter = f"{softioc}long_value"
    theta = f"{softioc}double_value"
    detector = f"{softioc}cam1"
    # A second writable analog PV stands in for the rotary-center correction
    # target (the soft IOC carries one spare unbounded `ao`); the CaptureRef
    # setpoint drives the measured center to it each pass. Test-shape PV, not a
    # production address (see module docstring).
    rotation_center_addr = f"{softioc}cam1:AcquireTime"

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.acquisition",
        name="Acquisition",
    )
    recipe_id = await bind_define_recipe(deps)(
        DefineRecipe(
            name="2BM_align_rotation_auto_recipe",
            capability_id=_CAPABILITY_ID,
            steps=_one_pass_recipe_steps(rotation_center_addr, shutter, theta, detector),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

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

    expander = InMemoryRecipeExpander()
    procedure_id = await bind_register_from_recipe(deps, expansion_port=expander)(
        RegisterProcedureFromRecipe(
            # noun-LAST (R6): rotation_alignment is the correct-and-converge cousin
            # of 6b's measure-only rotation_characterization.
            name="2-BM rotation-axis alignment (AUTO convergence, illustrative campaign)",
            kind="rotation_alignment",
            target_asset_ids=(rotary_asset_id,),
            parent_run_id=None,
            recipe_id=recipe_id,
            bindings={},
            max_consecutive_unconverged_iterations=_MAX_UNCONVERGED,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    port = EpicsCaControlPort()
    registry = ControlPortRegistry()
    registry.register(softioc, port, is_simulated=True)
    compute_port = InMemoryComputePort()
    compute_port.set_measurement_sequence(
        tuple((_rotation_center_measurement(c),) for c in centers_sequence)
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
        start_iteration=bind_start_iteration(deps),
        end_iteration=bind_end_iteration(deps),
    )
    conduct = bind_conduct_until_converged(deps, conductor=conductor, expansion_port=expander)
    # Park theta at the home the first rotation setpoint expects.
    await port.write(theta, _THETA_ZERO_DEG, wait=True)
    return deps, conduct, procedure_id, rotary_asset_id, registry, compute_port


@pytest.mark.integration
async def test_align_rotation_auto_converges_completes_and_writes_calibration(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """CORA drives a multi-pass measure-correct loop to convergence, completes the
    Procedure, and writes a Provisional rotation_center Calibration from the FINAL
    converged measured value via MeasuredSource(procedure_id)."""
    (
        deps,
        conduct,
        procedure_id,
        rotary_asset_id,
        registry,
        compute_port,
    ) = await _build_align_routine(db_pool, softioc, centers_sequence=_CONVERGING_CENTERS_PX)

    try:
        result = await conduct(
            ConductUntilConverged(
                procedure_id=procedure_id,
                convergence_capture_name=_CONVERGENCE_NAME,
                criterion=WithinToleranceCriterion(
                    expected=_TARGET_CENTER_PX, tolerance=_TOLERANCE_PX
                ),
                steps=(),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    finally:
        await registry.aclose()
        await compute_port.aclose()

    # ----- Loop outcome: converged-complete terminal -----
    assert result.succeeded is True
    assert result.failure is None
    # Both simulated control routes AND the simulated compute substrate touched.
    assert result.actuation_kind == ActuationKind.SIMULATED.value
    # The final pass surfaced the converged center for the Calibration write.
    by_name = {m.name: m for m in result.measurements}
    assert _CONVERGENCE_NAME in by_name
    assert by_name[_CONVERGENCE_NAME].value == pytest.approx(_FINAL_CONVERGED_CENTER_PX)

    # ----- Procedure FSM stream: Registered -> Started -> iterations -> Completed -----
    events, _ = await deps.event_store.load("Procedure", procedure_id)
    event_types = [e.event_type for e in events]
    assert event_types[0] == "ProcedureRegistered"
    assert "ProcedureStarted" in event_types
    assert event_types[-1] == "ProcedureCompleted"
    # The convergence loop opened + closed one iteration per pass.
    started = [e for e in events if e.event_type == "ProcedureIterationStarted"]
    ended = [e for e in events if e.event_type == "ProcedureIterationEnded"]
    assert len(started) == len(_CONVERGING_CENTERS_PX)
    assert len(ended) == len(_CONVERGING_CENTERS_PX)
    # The final iteration ended converged; the earlier ones did not.
    converged_flags = [e.payload["converged"] for e in ended]
    assert converged_flags[-1] is True
    assert all(flag is False for flag in converged_flags[:-1])

    # ----- iteration_count == N + current_iteration_index None at terminal -----
    procedure = await load_procedure(deps.event_store, procedure_id)
    assert procedure is not None
    assert procedure.iteration_count == len(_CONVERGING_CENTERS_PX)
    assert procedure.current_iteration_index is None
    assert procedure.status.value == "Completed"

    # ----- Calibration write: rotation_center, Provisional, MeasuredSource -----
    calibration_id = await bind_define_calibration(deps)(
        DefineCalibration(
            target_id=rotary_asset_id,
            quantity=CalibrationQuantity.ROTATION_CENTER,
            operating_point={"energy": 25.0, "optics_config": "5x"},
            description="Rotation centre from the 2-BM AUTO rotation-alignment routine.",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    revision_id = await bind_append_calibration_revision(deps)(
        AppendCalibrationRevision(
            calibration_id=calibration_id,
            value={"center": by_name[_CONVERGENCE_NAME].value},
            status=CalibrationStatus.PROVISIONAL,
            source=MeasuredSource(procedure_id=procedure_id),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert revision_id is not None

    calibration_events, _ = await deps.event_store.load("Calibration", calibration_id)
    assert [e.event_type for e in calibration_events] == [
        "CalibrationDefined",
        "CalibrationRevisionAppended",
    ]
    appended = calibration_events[1].payload
    assert appended["status"] == CalibrationStatus.PROVISIONAL.value
    assert appended["source_procedure_id"] == str(procedure_id)
    assert appended["value"] == {"center": pytest.approx(_FINAL_CONVERGED_CENTER_PX)}


@pytest.mark.integration
async def test_align_rotation_auto_never_converges_trips_cap_and_aborts(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """A never-converging sequence trips the patience cap: the loop aborts the
    Procedure (ConvergenceIterationCapReached) with current_iteration_index None
    at the terminal state (every iteration closed before the abort)."""
    (
        deps,
        conduct,
        procedure_id,
        _rotary_asset_id,
        registry,
        compute_port,
    ) = await _build_align_routine(db_pool, softioc, centers_sequence=_DIVERGENT_CENTERS_PX)

    try:
        result = await conduct(
            ConductUntilConverged(
                procedure_id=procedure_id,
                convergence_capture_name=_CONVERGENCE_NAME,
                criterion=WithinToleranceCriterion(
                    expected=_TARGET_CENTER_PX, tolerance=_TOLERANCE_PX
                ),
                steps=(),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    finally:
        await registry.aclose()
        await compute_port.aclose()

    # ----- Loop outcome: cap-abort terminal -----
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "ConvergenceIterationCapReached"

    events, _ = await deps.event_store.load("Procedure", procedure_id)
    event_types = [e.event_type for e in events]
    assert event_types[-1] == "ProcedureAborted"
    # The cap permits exactly _MAX_UNCONVERGED passes, all ended unconverged.
    ended = [e for e in events if e.event_type == "ProcedureIterationEnded"]
    assert len(ended) == _MAX_UNCONVERGED
    assert all(e.payload["converged"] is False for e in ended)

    procedure = await load_procedure(deps.event_store, procedure_id)
    assert procedure is not None
    assert procedure.iteration_count == _MAX_UNCONVERGED
    assert procedure.current_iteration_index is None
    assert procedure.status.value == "Aborted"
