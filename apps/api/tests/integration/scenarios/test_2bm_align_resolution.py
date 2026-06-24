"""Detector-pixel-size (resolution) alignment at APS 2-BM, CORA-conducted.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Calibration, Equipment, Operation, Recipe

Scenario test for the "align resolution" routine at 2-BM micro-CT (measure the
effective detector pixel size from a known sample translation), as performed by
operators today via `decarlof/adjust`. It is the smallest real conduct-path
routine whose payoff is a COMPUTE step: acquire two frames at a known horizontal
shift, then a `ComputeStep` over `ComputePort` measures the per-pixel scale, and
the resulting `detector_pixel_size` is written as a Provisional Calibration
sourced from the conducting Procedure.

This is slice 6a's headline exercise: the first conducted Procedure whose value
comes out of a compute job rather than a control read. It mirrors
`test_2bm_flat_field.py` (recipe -> register-from-recipe -> conduct re-expands)
but adds the compute leg + the value->Calibration bridge, and is deliberately a
BARE Procedure (parent_run_id=None) that yields a Calibration, NOT a Run with a
Dataset-of-record (the Run vs Procedure boundary: a measured calibration figure
is not a Dataset-of-record, so it stays a Procedure at 6a; Run-driving is
deferred).

## What this scenario surfaces

  1. RECIPE-DRIVEN COMPUTE: a `RecipeComputeStep` (literal fields, no BindingRef
     at 6a) expands to a Conductor `ComputeStep`; the conduct re-expands the
     pinned template and walks it through `ComputePort`.
  2. VALUE SURFACING: the in-memory ComputePort is seeded with the pixel-size
     `Measurement`; `_run_compute` submits -> awaits -> `fetch_measurements` ->
     `provide_result(measurements=...)`, records the Measurement on the activity
     log (name + units preserved), and surfaces it on
     `ConductProcedureResult.measurements`.
  3. VALUE -> CALIBRATION: the scenario reads `result.measurements`, defines the
     `detector_pixel_size` Calibration for the detector Asset, and appends a
     Provisional revision sourced from this Procedure (`MeasuredSource`). The
     name->schema-key mapping (`"pixel_size"` -> `{"pixel_size": ...}`) is the
     scenario's job; the port is quantity-agnostic.

## Stand-in PVs + values (illustrative-pending-staff)

The soft IOC carries generic test PVs, NOT production 2-BM addresses (same
caveat as the flat-field scenario). The compute job's `command` + `input_uris`
are illustrative literals pointing at the well-known paths the acquisition
action bodies would have written; the in-memory substrate does not read them
(it is the value-producing fake) and the measured pixel size is seeded.
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
from cora.recipe.aggregates.recipe import (
    RecipeActionStep,
    RecipeCheckStep,
    RecipeComputeStep,
    RecipeSetpointStep,
)
from cora.recipe.features.define_recipe import DefineRecipe
from cora.recipe.features.define_recipe import bind as bind_define_recipe
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 6, 24, 10, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000020e1099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000020e10aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-0000020e1c01")
_FAMILY_CAMERA_ID = family_stream_id(FamilyName("Camera"))

# Illustrative-pending-staff stand-in codes / values (see module docstring).
_SHUTTER_CLOSED = 0
_SHUTTER_OPEN = 1
_SAMPLE_IN_MM = 0.0
_SAMPLE_SHIFTED_MM = 0.1
_DWELL_S = 0.05
# The measured effective pixel size the in-memory compute substrate surfaces.
_MEASURED_PIXEL_SIZE_UM = 1.17


@pytest.mark.integration
async def test_align_resolution_recipe_conducts_compute_and_writes_calibration(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """Define the align-resolution Recipe (control steps + a ComputeStep), register a
    standalone Procedure from it, conduct it to Completed against the soft IOC + the
    in-memory ComputePort, surface the measured pixel size on the result, and write a
    Provisional detector_pixel_size Calibration sourced from the Procedure."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(80)])

    shutter = f"{softioc}long_value"
    axis = f"{softioc}double_value"
    detector = f"{softioc}cam1"

    # ----- Recipe BC: the acquisition Capability + the align-resolution Recipe -----
    #
    # The Recipe realizes the EXISTING cora.capability.acquisition. The compute
    # leg is a RecipeComputeStep (literal fields, no BindingRef at 6a). The
    # control steps acquire two frames at a known horizontal shift; the compute
    # step measures the per-pixel scale from the already-acquired frames (no
    # chaining: input_uris are authored literals).
    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.acquisition",
        name="Acquisition",
    )
    recipe_id = await bind_define_recipe(deps)(
        DefineRecipe(
            name="2BM_align_resolution_recipe",
            capability_id=_CAPABILITY_ID,
            steps=(
                # open shutter, sample in, acquire frame @ X=0
                RecipeSetpointStep(address=shutter, value=_SHUTTER_OPEN, verify=True),
                RecipeCheckStep(
                    address=shutter, criterion={"kind": "equals", "expected": _SHUTTER_OPEN}
                ),
                RecipeSetpointStep(address=axis, value=_SAMPLE_IN_MM, verify=True),
                RecipeActionStep(
                    name="collect",
                    params={
                        "detector": detector,
                        "trigger_mode": "Internal",
                        "repetitions": 1,
                        "dwell": _DWELL_S,
                    },
                ),
                # shift sample by a known amount, acquire frame @ X=0.1
                RecipeSetpointStep(address=axis, value=_SAMPLE_SHIFTED_MM, verify=True),
                RecipeActionStep(
                    name="collect",
                    params={
                        "detector": detector,
                        "trigger_mode": "Internal",
                        "repetitions": 1,
                        "dwell": _DWELL_S,
                    },
                ),
                # compute the effective pixel size from the two frames (value arm)
                RecipeComputeStep(
                    command=("tomopy", "find_pixel_size"),
                    input_uris=(
                        "file:///data/2bm/align/frame_x0.h5",
                        "file:///data/2bm/align/frame_x0p1.h5",
                    ),
                    parameters={"shift_mm": _SAMPLE_SHIFTED_MM},
                ),
                # return sample to beam + close shutter (safe state)
                RecipeSetpointStep(address=axis, value=_SAMPLE_IN_MM, verify=True),
                RecipeSetpointStep(address=shutter, value=_SHUTTER_CLOSED, verify=True),
                RecipeCheckStep(
                    address=shutter, criterion={"kind": "equals", "expected": _SHUTTER_CLOSED}
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Equipment BC: the detector Asset the Calibration targets -----
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

    # ----- Operation BC: register a standalone Procedure from the Recipe -----
    #
    # parent_run_id=None: the boundary rule keeps a measured calibration figure a
    # Procedure (no Dataset-of-record, no Run) at 6a.
    expander = InMemoryRecipeExpander()
    procedure_id = await bind_register_from_recipe(deps, expansion_port=expander)(
        RegisterProcedureFromRecipe(
            name="2-BM align resolution (conducted, illustrative campaign)",
            # noun-LAST (R6): the act CHARACTERIZES the detector pixel size into a
            # measured Calibration. Distinct from the focus-sharpness
            # `resolution_alignment` routine; "characterization" is the approved
            # noun for a Procedure that measures an equipment property.
            kind="pixel_size_characterization",
            target_asset_ids=(detector_asset_id,),
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
    # The pixel-size Measurement is seeded so fetch_measurements surfaces it.
    port = EpicsCaControlPort()
    registry = ControlPortRegistry()
    registry.register(softioc, port, is_simulated=True)
    compute_port = InMemoryComputePort()
    compute_port.set_next_measurements((_pixel_size_measurement(_MEASURED_PIXEL_SIZE_UM),))
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
        # Park the sample at the in-beam home the first setpoint expects.
        await port.write(axis, _SAMPLE_IN_MM, wait=True)
        # Recipe-driven conduct: empty caller steps re-expand the pinned template.
        result = await conduct(
            ConductProcedure(procedure_id=procedure_id, steps=()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    finally:
        await registry.aclose()
        await compute_port.aclose()

    # ----- Conduct outcome: all steps ran, the measured pixel size surfaced -----

    assert result.succeeded is True
    # 10 steps: 5 setpoints + 2 checks + 2 actions + 1 compute.
    assert result.completed_count == 10
    # Both the simulated control routes AND the simulated compute substrate were
    # touched, so the conduct observes Simulated (the compute kind folds in).
    assert result.actuation_kind == ActuationKind.SIMULATED.value
    # The ComputeStep's Measurement surfaced on the result (no re-reading the log).
    assert len(result.measurements) == 1
    measured = result.measurements[0]
    assert measured.name == "pixel_size"
    assert measured.value == pytest.approx(_MEASURED_PIXEL_SIZE_UM)
    assert measured.units == "um"

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

    # ----- Journal: the compute step recorded its Measurement (name + units kept) -----
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
    assert compute_payload["measurements"] == [
        {
            "name": "pixel_size",
            "value": pytest.approx(_MEASURED_PIXEL_SIZE_UM),
            "kind": "Scalar",
            "units": "um",
            "quality": "Good",
        }
    ]
    # The compute step is side-effecting, so it also recorded a pre-effect marker.
    compute_markers = [
        r for r in rows if r["step_kind"] == "compute" and r["payload"]["result"] == "in_flight"
    ]
    assert len(compute_markers) == 1

    # ----- Calibration write: detector_pixel_size, Provisional, MeasuredSource -----
    #
    # The conducting Procedure is the ACT; the Calibration BC stores the RESULT.
    # The scenario bridges them (a reusable composition-root bridge is deferred to
    # the second value-routine). The name->schema-key mapping (`pixel_size`) is the
    # scenario's job; the port stays quantity-agnostic.
    calibration_id = await bind_define_calibration(deps)(
        DefineCalibration(
            target_id=detector_asset_id,
            quantity=CalibrationQuantity.DETECTOR_PIXEL_SIZE,
            operating_point={"optics_config": "5x"},
            description="Detector pixel size from the 2-BM align-resolution routine.",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    revision_id = await bind_append_calibration_revision(deps)(
        AppendCalibrationRevision(
            calibration_id=calibration_id,
            value={"pixel_size": float(measured.value)},
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
    assert appended["value"] == {"pixel_size": pytest.approx(_MEASURED_PIXEL_SIZE_UM)}


def _pixel_size_measurement(value: float):
    """Build the pixel-size `Measurement` the in-memory ComputePort surfaces.

    `name="pixel_size"` selects the Calibration quantity at the scenario's
    name->schema-key bridge; `units="um"` matches the detector_pixel_size
    value schema. Local import keeps the module import list focused on the
    BC features under exercise.
    """
    from cora.operation.ports.measurement import Measurement

    return Measurement(
        value=value,
        kind="Scalar",
        quality="Good",
        produced_at=_NOW,
        name="pixel_size",
        units="um",
    )
