"""19-BM single-axis adaptive characterization, steered by a DecidePort (S6).

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Equipment, Operation, Calibration

One standalone Procedure, no Run. This is the first end-to-end consumer of the
decide layer (S1-S5): a `GridWalkDecidePort` brain drives
`Conductor.conduct_until_advised` over a single rotation axis, measuring a
rotation-center metric per swept point, and the loop completes when the brain
advises Stop. The brain's per-iteration decision is recorded on the Procedure
ledger, and the measured center is written as a Provisional ROTATION_CENTER
Calibration via `MeasuredSource(procedure_id)`.

ADAPTIVE, not a fixed raster: the lattice carries five points, but the
GridWalkDecidePort stops after the third because the Satisfy objective
(rotation-center equals the target) is met by the third observation. A dumb
raster would have actuated all five; the brain shortened the campaign. That
early Stop is the decide-layer value this scenario grounds.

The control + compute substrates are in-memory (the decide layer is what is
under test, not the EPICS adapter), but the event store, the activity logbook,
and the Calibration are the real Postgres-backed stack, so the per-iteration
provenance is asserted on the persisted ledger, not a transcript. No Run is
involved: the Calibration is sourced from the Procedure, so it never crosses the
Run/Procedure boundary.
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
from cora.infrastructure.kernel import Kernel
from cora.operation.adapters.grid_walk_decide_port import GridWalkDecidePort
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.aggregates.procedure import PostgresActivityStore, load_procedure
from cora.operation.conductor import ComputeStep, Conductor, SetpointStep
from cora.operation.features.abort_procedure import bind as bind_abort
from cora.operation.features.append_activities import bind as bind_append
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.end_iteration import bind as bind_end_iteration
from cora.operation.features.register_procedure import RegisterProcedure
from cora.operation.features.register_procedure import bind as bind_register_procedure
from cora.operation.features.start_iteration import bind as bind_start_iteration
from cora.operation.features.start_procedure import bind as bind_start
from cora.operation.ports.decide_port import (
    SteeringAxis,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringPoint,
    SteeringSpace,
)
from cora.operation.ports.measurement import Measurement
from cora.recipe.aggregates.recipe.body import CaptureRef
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 26, 9, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000019b001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000019b002")
_FAMILY_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))

# The steering axis is the sample-rotary angle. It is BOTH the SteeringAxis name,
# the SetpointStep address the seeded angle is written to, and the CaptureRef the
# step resolves, so the seed-the-captures keystone drives the one rotary axis.
_THETA_ADDR = "19bm:sample_rotary_theta"
# The objective metric the find-center compute deposits each pass. Distinct from
# the seeded axis (the brain reads it, never seeds it).
_METRIC_NAME = "rotation_center"
_TARGET_CENTER_PX = 1024.0
# Three swept measurements; the third equals the target exactly, so the Satisfy
# objective is met and the grid walk stops after three of its five lattice points.
_SWEPT_CENTERS_PX = (1027.0, 1025.0, 1024.0)
_THETA_LOWER_DEG = -5.0
_THETA_UPPER_DEG = 5.0
_POINTS_PER_AXIS = 5


def _rotation_center_measurement(center_px: float) -> Measurement:
    """The rotation-center `Measurement` the in-memory ComputePort surfaces per pass.

    `name=_METRIC_NAME` is BOTH the captures slot the find-center deposit fills
    (the objective the brain reads) AND the name the scenario selects to write the
    Calibration. `units="pixel"` matches the rotation_center value schema.
    """
    return Measurement(
        value=center_px,
        kind="Scalar",
        quality="Good",
        produced_at=_NOW,
        name=_METRIC_NAME,
        units="pixel",
    )


def _one_pass_block() -> tuple[object, ...]:
    """One steering pass: find the rotation center (deposit), move the seeded angle.

    The ComputeStep deposits `rotation_center` (the objective slot the brain
    reads); the SetpointStep consumes the `19bm:sample_rotary_theta` axis via a
    CaptureRef, so the brain-seeded angle resolves to an actual rotary write and
    the G2 coverage guard is satisfied.
    """
    return (
        ComputeStep(
            command=("tomopy", "find_center"),
            input_uris=("file:///data/19bm/align/theta_pair.h5",),
            output_uri=None,
            parameters={},
            capture_name=_METRIC_NAME,
        ),
        SetpointStep(
            address=_THETA_ADDR,
            value=CaptureRef(capture_name=_THETA_ADDR),
        ),
    )


def _point_to_captures(point: SteeringPoint) -> dict[str, object]:
    return {_THETA_ADDR: point.coordinates[_THETA_ADDR]}


async def _register_rotary_and_procedure(deps: Kernel) -> tuple[UUID, UUID]:
    """Seed a SampleRotary asset (the Calibration target) + a standalone Procedure."""
    await bind_define_family(deps)(
        DefineFamily(name="RotaryStage", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    rotary_asset_id = await bind_register_asset(deps)(
        RegisterAsset(
            name="19bm-sample-rotary",
            tier=AssetTier.DEVICE,
            parent_id=None,
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_asset_family(deps)(
        AddAssetFamily(asset_id=rotary_asset_id, family_id=_FAMILY_ROTARY_STAGE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    procedure_id = await bind_register_procedure(deps)(
        RegisterProcedure(
            # noun-LAST (R6): the operation is characterization of the rotation center.
            name="19-BM rotation-centre characterization (adaptive, GridWalk-steered)",
            kind="rotation_center_characterization",
            target_asset_ids=frozenset({rotary_asset_id}),
            parent_run_id=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return rotary_asset_id, procedure_id


@pytest.mark.integration
async def test_19bm_rotation_characterization_grid_walk_steers_loop_and_writes_calibration(
    db_pool: asyncpg.Pool,
) -> None:
    """A GridWalk-steered loop characterizes the rotation centre then writes a Calibration.

    The brain stops after three of five lattice points (Satisfy met), the loop
    completes, the per-iteration advice is on the persisted ledger, and the
    measured centre is recorded as a Provisional ROTATION_CENTER Calibration via
    MeasuredSource(procedure_id).
    """
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(200)])
    rotary_asset_id, procedure_id = await _register_rotary_and_procedure(deps)

    control = InMemoryControlPort()
    control.simulate_connect(_THETA_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(
        tuple((_rotation_center_measurement(c),) for c in _SWEPT_CENTERS_PX)
    )
    step_store = PostgresActivityStore(db_pool)
    conductor = Conductor(
        control_port=control,
        append_step=bind_append(deps, step_store=step_store),
        clock=deps.clock,
        id_generator=deps.id_generator,
        compute_port=compute,
        start_procedure=bind_start(deps),
        complete_procedure=bind_complete(deps),
        abort_procedure=bind_abort(deps),
        start_iteration=bind_start_iteration(deps),
        end_iteration=bind_end_iteration(deps),
    )

    try:
        result = await conductor.conduct_until_advised(
            procedure_id=procedure_id,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            steps=_one_pass_block(),  # type: ignore[arg-type]
            decide_port=GridWalkDecidePort(points_per_axis=_POINTS_PER_AXIS),
            objective=SteeringObjective(
                kind=SteeringObjectiveKind.SATISFY,
                target_measurement_name=_METRIC_NAME,
                target_value=_TARGET_CENTER_PX,
            ),
            space=SteeringSpace(
                axes=(
                    SteeringAxis(name=_THETA_ADDR, lower=_THETA_LOWER_DEG, upper=_THETA_UPPER_DEG),
                )
            ),
            objective_capture_name=_METRIC_NAME,
            point_to_captures=_point_to_captures,
        )
    finally:
        await control.aclose()
        await compute.aclose()

    # ----- Loop outcome: brain-advised-Stop completion after three passes -----
    assert result.succeeded is True
    assert result.failure is None
    by_name = {m.name: m for m in result.measurements}
    assert _METRIC_NAME in by_name
    assert by_name[_METRIC_NAME].value == pytest.approx(_TARGET_CENTER_PX)

    # ----- Procedure FSM stream: Registered -> Started -> 3 iterations -> Completed -----
    events, _ = await deps.event_store.load("Procedure", procedure_id)
    event_types = [e.event_type for e in events]
    assert event_types[0] == "ProcedureRegistered"
    assert "ProcedureStarted" in event_types
    assert event_types[-1] == "ProcedureCompleted"
    started = [e for e in events if e.event_type == "ProcedureIterationStarted"]
    ended = [e for e in events if e.event_type == "ProcedureIterationEnded"]
    assert len(started) == len(_SWEPT_CENTERS_PX)
    assert len(ended) == len(_SWEPT_CENTERS_PX)

    # ----- Per-iteration steering provenance on the persisted ledger -----
    # Every steering pass leaves converged None (no convergence verdict); the
    # brain advised Continue for the first two and Stop on the third; the brain
    # identity rides every iteration.
    assert [e.payload["converged"] for e in ended] == [None, None, None]
    assert [e.payload["advised_stop"] for e in ended] == [False, False, True]
    assert [e.payload["model_ref"] for e in ended] == ["grid_walk", "grid_walk", "grid_walk"]
    assert all(e.payload["reasoning"] is not None for e in ended)

    # ----- iteration_count == 3, no open iteration, terminal Completed -----
    procedure = await load_procedure(deps.event_store, procedure_id)
    assert procedure is not None
    assert procedure.iteration_count == len(_SWEPT_CENTERS_PX)
    assert procedure.current_iteration_index is None
    assert procedure.status.value == "Completed"

    # ----- Calibration: rotation_center, Provisional, MeasuredSource(procedure_id) -----
    calibration_id = await bind_define_calibration(deps)(
        DefineCalibration(
            target_id=rotary_asset_id,
            quantity=CalibrationQuantity.ROTATION_CENTER,
            # The shared rotation_center operating_point requires energy; 19-BM is
            # filtered white beam, so this is the representative effective energy
            # of the F3-30 filtered spectrum, not a monochromator setpoint.
            operating_point={"energy": 25.0, "optics_config": "5x"},
            description="Rotation centre from the 19-BM adaptive characterization routine.",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_append_calibration_revision(deps)(
        AppendCalibrationRevision(
            calibration_id=calibration_id,
            value={"center": by_name[_METRIC_NAME].value},
            status=CalibrationStatus.PROVISIONAL,
            source=MeasuredSource(procedure_id=procedure_id),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    calibration_events, _ = await deps.event_store.load("Calibration", calibration_id)
    calibration_event_types = [e.event_type for e in calibration_events]
    assert calibration_event_types == ["CalibrationDefined", "CalibrationRevisionAppended"]
    revision = calibration_events[-1]
    assert revision.payload["source_procedure_id"] == str(procedure_id)
    assert revision.payload["value"] == {"center": _TARGET_CENTER_PX}
