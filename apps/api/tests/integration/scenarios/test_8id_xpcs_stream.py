"""XPCS event-stream acquisition at APS 8-ID, CORA-conducted from a Recipe.

cluster: Runs
archetype: routine
bc_primary: Operation
bc_touches: Data, Equipment, Operation, Recipe, Run

Scenario test for the event-stream acquisition axis (the `stream` action body)
end to end: the 8-ID XPCS technique is a STREAMING Method, realized as a Recipe
whose single conduct step is a `stream` action against a DAQ-owned high-rate
file-writer. An operator registers a Procedure from the Recipe as a phase of a
subject-less acquisition Run; the conduct handler re-expands the recipe and drives
the `stream` body through the ControlPort against a seeded in-memory DAQ. The
captured frame stream becomes a Dataset attributed to the Run.

See [[project_event_stream_axis_stage1_design]] for the design lock this
scenario consumes (gate-reviewed; the data plane is the caller-driven
register_dataset path, NOT RunCompleted.artifact_uri, which is compute-only), and
[[project_light_source_device_audit]] for the XPCS/XFEL audit that surfaced the
axis. 8-ID (and 9-ID surface) XPCS is the second beamline family after LCLS-MFX
to need a DAQ-owned high-rate frame stream (the rule-of-three trigger).

## Why this scenario exists

It exercises the event-stream axis end to end: it MATERIALIZES the catalog
`xpcs` Method as `ExecutionPattern.STREAMING` and CONDUCTS a `stream` Run
end to end, proving the two load-bearing claims of the lock:

  1. A `stream` ActionStep conducts through the production conduct path
     (define-recipe -> register-from-recipe -> conduct re-expands -> Conductor ->
     ControlPort) exactly like `collect`/`continuous`, with no new port, runtime,
     Conductor change, or Run-event change.
  2. The frame stream is DAQ-owned and NEVER ingested: the conducted Run carries
     ZERO observation rows (the per-frame data stays in the external file). The
     Dataset is registered by the caller-driven `register_dataset` path
     (`producing_run_id`), the same path the 2-BM tomography stack uses; the
     stream does not ride `RunCompleted.artifact_uri`.

## Stand-in PVs + values (illustrative-pending-staff)

There is no soft IOC for the file-writer convention, so the DAQ is a seeded
`InMemoryControlPort` routed through a `ControlPortRegistry` marked
`is_simulated=True` (so the conduct observes `Simulated`, as a soft-IOC route
would). The `stream` body drives the areaDetector HDF file-writer PVs on the
detector root `8idRigaku3m:HDF1` (`AcquireTime`/`NumCapture`/`Capture`, terminal
on `NumCaptured_RBV`, output uri from `FullFileName_RBV`). `NumCaptured_RBV` is
seeded `>= events` so the count terminal exits at once. Frame count / dwell are
illustrative (tiny); real per-campaign values are operator-bound.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

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
from cora.operation.acquisitions import stream
from cora.operation.adapters.control_port_registry import ControlPortRegistry
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
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
from cora.operation.ports.control_port import ActuationKind, Measurement
from cora.recipe.aggregates.method import ExecutionPattern
from cora.recipe.aggregates.recipe import RecipeActionStep
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

_NOW = datetime(2026, 6, 24, 10, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000020e0099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000020e00aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-0000020e0d01")
_SITE_ID = UUID("01900000-0000-7000-8000-0000020e0d02")
_FAMILY_CAMERA_ID = family_stream_id(FamilyName("Camera"))

# Illustrative-pending-staff DAQ root + values (see module docstring).
_DETECTOR = "8idRigaku3m:HDF1"
_URI = "/data/xpcs/8id/run0042/stream.h5"
_EVENTS = 100
_DWELL_S = 0.001


@pytest.mark.integration
async def test_xpcs_stream_recipe_conducts_event_stream_and_leaves_no_observations(
    db_pool: asyncpg.Pool,
) -> None:
    """Define the XPCS Recipe (one `stream` step), define the Method as STREAMING,
    register a Procedure from it as a phase of a subject-less acquisition Run,
    conduct it to Completed against a seeded in-memory DAQ, register the frame
    stream as a Run-attributed Dataset, and confirm the Run carries zero
    observation rows (the per-frame data stays DAQ-owned)."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(80)])

    # ----- Recipe BC: the xpcs Capability + a one-step `stream` Recipe -----
    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.xpcs",
        name="X-ray Photon Correlation Spectroscopy",
    )
    recipe_id = await bind_define_recipe(deps)(
        DefineRecipe(
            name="8ID_xpcs_recipe",
            capability_id=_CAPABILITY_ID,
            steps=(
                RecipeActionStep(
                    name="stream",
                    params={"detector": _DETECTOR, "events": _EVENTS, "dwell": _DWELL_S},
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Recipe ladder (STREAMING Method) + a subject-less acquisition Run -----
    await bind_define_family(deps)(
        DefineFamily(name="Camera", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    detector_asset_id = await bind_register_asset(deps)(
        RegisterAsset(
            name="8id-rigaku3m", tier=AssetTier.DEVICE, parent_id=None, facility_code="cora"
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
            name="xpcs",
            capability_id=_CAPABILITY_ID,
            execution_pattern=ExecutionPattern.STREAMING,  # the STREAMING-classification claim
            needed_family_ids=frozenset({_FAMILY_CAMERA_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await bind_define_practice(deps)(
        DefinePractice(name="8ID_xpcs_practice", method_id=method_id, site_id=_SITE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_id = await bind_define_plan(deps)(
        DefinePlan(
            name="8ID_xpcs_plan",
            practice_id=practice_id,
            asset_ids=frozenset({detector_asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    run_id = await bind_start_run(deps)(
        StartRun(
            name="8-ID XPCS (subject-less acquisition Run)",
            plan_id=plan_id,
            subject_id=None,
            trigger_source="operator-manual; xpcs event stream",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operation BC: register a Procedure from the Recipe (a phase of the Run) -----
    expander = InMemoryRecipeExpander()
    procedure_id = await bind_register_from_recipe(deps, expansion_port=expander)(
        RegisterProcedureFromRecipe(
            name="8-ID XPCS (conducted event stream)",
            kind="xpcs",
            target_asset_ids=(),
            parent_run_id=run_id,
            recipe_id=recipe_id,
            bindings={},
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Conduct the `stream` step against a seeded in-memory DAQ -----
    #
    # No soft IOC has the file-writer PVs, so the DAQ is a seeded InMemoryControlPort
    # routed through a registry marked is_simulated=True (so the conduct observes
    # Simulated). NumCaptured_RBV is seeded >= events so the count terminal exits
    # at once; FullFileName_RBV carries the output uri the body returns.
    port = InMemoryControlPort()
    port.simulate_connect(f"{_DETECTOR}:AcquireTime")
    port.simulate_connect(f"{_DETECTOR}:NumCapture")
    port.simulate_connect(f"{_DETECTOR}:Capture")
    port.set_reading(
        f"{_DETECTOR}:NumCaptured_RBV",
        Measurement(value=_EVENTS, kind="Scalar", quality="Good", produced_at=_NOW),
    )
    port.set_reading(
        f"{_DETECTOR}:FullFileName_RBV",
        Measurement(value=_URI, kind="Categorical", quality="Good", produced_at=_NOW),
    )
    registry = ControlPortRegistry()
    registry.register(_DETECTOR, port, is_simulated=True)
    step_store = PostgresActivityStore(db_pool)
    conductor = Conductor(
        control_port=registry,
        append_step=bind_append(deps, step_store=step_store),
        clock=deps.clock,
        id_generator=deps.id_generator,
        action_registry=InMemoryActionRegistry({"stream": stream}),
        start_procedure=bind_start(deps),
        complete_procedure=bind_complete(deps),
        abort_procedure=bind_abort(deps),
    )
    conduct = bind_conduct(deps, conductor=conductor, expansion_port=expander)

    try:
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

    # ----- Conduct outcome: the single stream step ran, conduct observed Simulated -----
    assert result.succeeded is True
    assert result.completed_count == 1
    assert result.actuation_kind == ActuationKind.SIMULATED.value

    # ----- Procedure FSM: Registered (from recipe) -> ... -> Completed, phase of the Run -----
    proc_events, _ = await deps.event_store.load("Procedure", procedure_id)
    proc_types = [e.event_type for e in proc_events]
    assert proc_types[0] == "ProcedureRegistered"
    assert "RecipeExpansionRecorded" in proc_types
    assert proc_types[-1] == "ProcedureCompleted"
    registered = next(e for e in proc_events if e.event_type == "ProcedureRegistered")
    assert registered.payload["parent_run_id"] == str(run_id)

    # ----- Run FSM: the glue completed the Run carrying the conduct's kind.
    #       Exactly RunStarted -> RunCompleted: NO RunObservationLogbookOpened, the
    #       event-level proof that the stream ingested no per-frame observations. -----
    run_events, _ = await deps.event_store.load("Run", run_id)
    assert [e.event_type for e in run_events] == ["RunStarted", "RunCompleted"]
    assert run_events[0].payload["subject_id"] is None

    # ----- Data BC: the frame stream as a Run-attributed Dataset (caller-driven) -----
    #
    # The stream does NOT ride RunCompleted.artifact_uri (compute-only); the caller
    # registers the Dataset via producing_run_id with the body's output uri plus the
    # file-derived checksum/size, the same path the 2-BM tomography stack uses.
    dataset_id = await bind_register_dataset(deps)(
        RegisterDataset(
            name="8ID_xpcs_2026-06-24",
            uri=f"file://{_URI}",
            checksum_algorithm="sha256",
            checksum_value="b" * 64,
            byte_size=96_000_000_000,
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
    # The conduct's Simulated provenance flows onto the Dataset via the Run.
    assert payload["producing_actuation_kind"] == ActuationKind.SIMULATED.value

    # ----- The no-ingest guarantee: zero observation rows for the stream Run -----
    #
    # The per-frame data stays in the external DAQ file; CORA never ingests it into
    # the sub-Hz observation logbook. The projection table has no row for this Run.
    async with db_pool.acquire() as conn:
        observation_count = await conn.fetchval(
            "SELECT count(*) FROM entries_run_observations WHERE run_id = $1", run_id
        )
    assert observation_count == 0
