"""Detector Z-rail alignment to the beam at APS 2-BM.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Equipment, Operation, Recipe

Scenario test for the staff-validated "detector Z-rail alignment to the
beam" routine (2bm-procedures `detector_z_rail_alignment`): walk the
Optique Peter detector along its PRO225SL Z rail with a small aperture,
fit the centroid drift, and rotate the detector optical table
(`2bmb:table3.AX` / `.AY`) until the rail runs parallel to the beam.

Modeled in the CORA lens, not mirrored: this is an alignment Procedure
(Operation BC, ISA-106), NOT a Run (no Subject, no Campaign). It is the
detector-table counterpart of `center_alignment` (which aligns the
sample rotary stage). The centroid fit and the convergence judgement
live at the edge; CORA records the act, its iterations, and the
converged table-angle setpoints. Distinct from `roll_alignment` /
`pitch_alignment`, which align the sample `Hexapod`, not the detector
table.

The converged `.AX` / `.AY` table angles are recorded as setpoints in
the procedure step-log, not as a Calibration: they are an alignment
state re-established by re-running the routine, not an instrument
constant cited by downstream reconstruction. See
`docs/deployments/2-bm/procedures.md`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.operation._projections import register_operation_projections
from cora.operation.aggregates.procedure import ProcedureStatus
from cora.operation.features.append_activities import (
    ActivityInput,
    AppendProcedureActivities,
)
from cora.operation.features.append_activities import bind as bind_append_step
from cora.operation.features.complete_procedure import CompleteProcedure
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.end_iteration import EndProcedureIteration
from cora.operation.features.end_iteration import bind as bind_end_iteration
from cora.operation.features.list_procedure_iterations import ListProcedureIterations
from cora.operation.features.list_procedure_iterations import bind as bind_list_iterations
from cora.operation.features.list_procedures import ListProcedures
from cora.operation.features.list_procedures import bind as bind_list
from cora.operation.features.register_procedure import RegisterProcedure
from cora.operation.features.register_procedure import bind as bind_register_procedure
from cora.operation.features.start_iteration import StartProcedureIteration
from cora.operation.features.start_iteration import bind as bind_start_iteration
from cora.operation.features.start_procedure import StartProcedure
from cora.operation.features.start_procedure import bind as bind_start
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

_NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000003a05bb")

_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-0000003a0a01")
_APS_SITE_ID = UUID("01900000-0000-7000-8000-0000003a0501")

# Family ids (derived from the name; all four names unique here).
_FAM_TABLE_ID = family_stream_id(FamilyName("Table"))
_FAM_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_FAM_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_FAM_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

# Asset ids
_ASSET_DETECTOR_TABLE_ID = UUID("01900000-0000-7000-8000-0000003a0a11")
_ASSET_PROPAGATION_ID = UUID("01900000-0000-7000-8000-0000003a0a21")
_ASSET_CAMERA_ID = UUID("01900000-0000-7000-8000-0000003a0a31")
_ASSET_SCINTILLATOR_ID = UUID("01900000-0000-7000-8000-0000003a0a41")

# Recipe ladder
_METHOD_ID = UUID("01900000-0000-7000-8000-0000003a0d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-0000003a0d31")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-0000003a0d11")
_PLAN_ID = UUID("01900000-0000-7000-8000-0000003a0d21")

# Procedure + lazy steps logbook
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000003a0e01")
_STEPS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-0000003a0f01")
_STEPS_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-0000003a0f02")


_DEVICES = (
    DeviceSpec("DetectorTable", _ASSET_DETECTOR_TABLE_ID, "Table", _FAM_TABLE_ID),
    DeviceSpec("PropagationDistance", _ASSET_PROPAGATION_ID, "LinearStage", _FAM_LINEAR_STAGE_ID),
    DeviceSpec("Camera", _ASSET_CAMERA_ID, "Camera", _FAM_CAMERA_ID),
    DeviceSpec("Scintillator", _ASSET_SCINTILLATOR_ID, "Scintillator", _FAM_SCINTILLATOR_ID),
)


def _id_queue() -> list[UUID]:
    """FixedIdGenerator queue (head-first). Anonymous event ids are uuid4()."""
    e = uuid4
    return [
        *facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=_DEVICES),
        # define_method: method_id, event_id
        _METHOD_ID,
        e(),
        # define_practice: practice_id, event_id
        _PRACTICE_ID,
        e(),
        # define_plan: plan_id, event_id
        _PLAN_ID,
        e(),
        # register_procedure: procedure_id, event_id
        _PROCEDURE_ID,
        e(),
        # start_procedure: event_id
        e(),
        # start_iteration(1): event_id
        e(),
        # append iter1 (lazy-open on first call): logbook_id, open_event_id
        _STEPS_LOGBOOK_ID,
        _STEPS_OPEN_EVENT_ID,
        # end_iteration(1): event_id
        e(),
        # start_iteration(2): event_id
        e(),
        # end_iteration(2): event_id (iter2 append + finalize append: no generator ids)
        e(),
        # complete_procedure: event_id
        e(),
    ]


def _setpoint(
    *,
    channel: str,
    target_value: float | str,
    units: str,
    note: str | None = None,
    sampled_at: datetime,
) -> ActivityInput:
    payload: dict[str, Any] = {"channel": channel, "target_value": target_value, "units": units}
    if note is not None:
        payload["note"] = note
    return ActivityInput(
        event_id=uuid4(), step_kind="setpoint", payload=payload, sampled_at=sampled_at
    )


def _action(*, action_name: str, sampled_at: datetime, **params: Any) -> ActivityInput:
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload={"action_name": action_name, "params": params},
        sampled_at=sampled_at,
    )


def _check(
    *,
    channel: str,
    passed: bool,
    source: str,
    sampled_at: datetime,
    actual: float | None = None,
    expected: float | None = None,
    tolerance: float | None = None,
    **evidence: Any,
) -> ActivityInput:
    payload: dict[str, Any] = {"channel": channel, "passed": passed, "source": source}
    if actual is not None:
        payload["actual"] = actual
    if expected is not None:
        payload["expected"] = expected
    if tolerance is not None:
        payload["tolerance"] = tolerance
    if evidence:
        payload["evidence"] = evidence
    return ActivityInput(
        event_id=uuid4(), step_kind="check", payload=payload, sampled_at=sampled_at
    )


def _postgres_step_store(db_pool: asyncpg.Pool):
    from cora.operation.aggregates.procedure import PostgresActivityStore

    return PostgresActivityStore(db_pool)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_operation_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _read_steps(db_pool: asyncpg.Pool, procedure_id: UUID) -> list[asyncpg.Record]:
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            "SELECT step_kind, payload, sampled_at "
            "FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1 ORDER BY sampled_at",
            procedure_id,
        )


@pytest.mark.integration
async def test_detector_z_rail_alignment_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed Equipment + Recipe + Operation, run the iterative Z-walk /
    table-rotate convergence loop, finalize with the converged table
    angles, and assert the operator-readable record."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    # ----- Recipe BC: the alignment technique + its 2-BM binding -----

    await seed_capability_postgres(
        deps.event_store, _CAPABILITY_ID, code="cora.capability.alignment", name="Alignment"
    )
    await bind_define_method(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_ID,
            name="detector_z_rail_alignment",
            needed_family_ids=frozenset(
                {_FAM_TABLE_ID, _FAM_LINEAR_STAGE_ID, _FAM_CAMERA_ID, _FAM_SCINTILLATOR_ID}
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="2BM_detector_alignment_practice", method_id=_METHOD_ID, site_id=_APS_SITE_ID
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_detector_z_rail_plan",
            practice_id=_PRACTICE_ID,
            asset_ids=frozenset(
                {
                    _ASSET_DETECTOR_TABLE_ID,
                    _ASSET_PROPAGATION_ID,
                    _ASSET_CAMERA_ID,
                    _ASSET_SCINTILLATOR_ID,
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operation BC: register + start the Procedure -----

    await bind_register_procedure(deps)(
        RegisterProcedure(
            name="2-BM detector Z-rail alignment to the beam",
            kind="detector_z_rail_alignment",
            target_asset_ids=frozenset(
                {
                    _ASSET_DETECTOR_TABLE_ID,
                    _ASSET_PROPAGATION_ID,
                    _ASSET_CAMERA_ID,
                    _ASSET_SCINTILLATOR_ID,
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start(deps)(
        StartProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    def t(seconds: int) -> datetime:
        return datetime(2026, 5, 19, 10, 0, seconds, tzinfo=UTC)

    # Iteration 1: walk the rail near/far, the spot drifts, table rotated. Fails.
    iter1_steps = (
        _setpoint(
            channel="PropagationDistance",
            target_value=100.0,
            units="mm",
            note="Z near position",
            sampled_at=t(1),
        ),
        _action(
            action_name="acquire_alignment_frame",
            exposure_time=0.05,
            hdf5_location="/exchange/data/zrail_iter1_near.h5",
            sampled_at=t(2),
        ),
        _check(
            channel="spot_centroid_x_px",
            passed=False,
            actual=1024.0,
            expected=1024.0,
            tolerance=2.0,
            source="bbox_centroid",
            sampled_at=t(3),
        ),
        _setpoint(
            channel="PropagationDistance",
            target_value=900.0,
            units="mm",
            note="Z far position",
            sampled_at=t(4),
        ),
        _action(
            action_name="acquire_alignment_frame",
            exposure_time=0.05,
            hdf5_location="/exchange/data/zrail_iter1_far.h5",
            sampled_at=t(5),
        ),
        _check(
            channel="spot_centroid_x_px",
            passed=False,
            actual=1038.0,
            expected=1024.0,
            tolerance=2.0,
            source="bbox_centroid",
            drift_px=14.0,
            sampled_at=t(6),
        ),
        _setpoint(
            channel="DetectorTable.AY",
            target_value=-0.018,
            units="deg",
            note="yaw correction for the near/far drift; convention: -drift_px scaled",
            sampled_at=t(7),
        ),
    )

    # Iteration 2: drift within tolerance. Converges.
    iter2_steps = (
        _setpoint(
            channel="PropagationDistance",
            target_value=100.0,
            units="mm",
            note="Z near, post-correction",
            sampled_at=t(8),
        ),
        _action(
            action_name="acquire_alignment_frame",
            exposure_time=0.05,
            hdf5_location="/exchange/data/zrail_iter2_near.h5",
            sampled_at=t(9),
        ),
        _setpoint(
            channel="PropagationDistance",
            target_value=900.0,
            units="mm",
            note="Z far, post-correction",
            sampled_at=t(10),
        ),
        _action(
            action_name="acquire_alignment_frame",
            exposure_time=0.05,
            hdf5_location="/exchange/data/zrail_iter2_far.h5",
            sampled_at=t(11),
        ),
        _check(
            channel="spot_centroid_x_px",
            passed=True,
            actual=1025.0,
            expected=1024.0,
            tolerance=2.0,
            source="bbox_centroid",
            drift_px=1.0,
            sampled_at=t(12),
        ),
    )

    # Finalize (post-convergence): the converged detector-table angles that
    # make the Z rail parallel to the beam. Recorded as setpoints, not a
    # Calibration (alignment state, not a downstream-cited constant).
    finalize_steps = (
        _setpoint(
            channel="DetectorTable.AX",
            target_value=0.004,
            units="deg",
            note="converged pitch (rail parallel to beam)",
            sampled_at=t(13),
        ),
        _setpoint(
            channel="DetectorTable.AY",
            target_value=-0.018,
            units="deg",
            note="converged yaw (rail parallel to beam)",
            sampled_at=t(14),
        ),
    )

    step_store = _postgres_step_store(db_pool)

    await bind_start_iteration(deps)(
        StartProcedureIteration(procedure_id=_PROCEDURE_ID, iteration_index=1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    count1 = await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=iter1_steps),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count1 == 7
    await bind_end_iteration(deps)(
        EndProcedureIteration(
            procedure_id=_PROCEDURE_ID,
            iteration_index=1,
            converged=False,
            reason="near/far spot drift 14.0px exceeds 2.0px tolerance",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await bind_start_iteration(deps)(
        StartProcedureIteration(procedure_id=_PROCEDURE_ID, iteration_index=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    count2 = await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=iter2_steps),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count2 == 5
    await bind_end_iteration(deps)(
        EndProcedureIteration(
            procedure_id=_PROCEDURE_ID, iteration_index=2, converged=True, reason=None
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    count_final = await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=finalize_steps),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count_final == 2

    await bind_complete(deps)(
        CompleteProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert the Procedure stream tells the right lifecycle story -----

    procedure_events, procedure_version = await deps.event_store.load("Procedure", _PROCEDURE_ID)
    assert procedure_version == 8
    assert [e.event_type for e in procedure_events] == [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureIterationStarted",
        "ProcedureActivitiesLogbookOpened",
        "ProcedureIterationEnded",
        "ProcedureIterationStarted",
        "ProcedureIterationEnded",
        "ProcedureCompleted",
    ]

    # ----- Steps: 14 entries, the converged angles last -----

    step_rows = await _read_steps(db_pool, _PROCEDURE_ID)
    assert len(step_rows) == 14
    assert [r["step_kind"] for r in step_rows] == [
        "setpoint",
        "action",
        "check",
        "setpoint",
        "action",
        "check",
        "setpoint",  # iter1
        "setpoint",
        "action",
        "setpoint",
        "action",
        "check",  # iter2
        "setpoint",
        "setpoint",  # finalize: converged AX + AY
    ]
    import json

    last = json.loads(step_rows[-1]["payload"])
    assert last["channel"] == "DetectorTable.AY"
    assert last["units"] == "deg"

    # ----- Read-side: COMPLETED, iteration_count=2, per-iteration verdicts -----

    await _drain(db_pool)
    page = await bind_list(deps)(
        ListProcedures(kind="detector_z_rail_alignment"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    matching = [item for item in page.items if item.procedure_id == _PROCEDURE_ID]
    assert len(matching) == 1
    summary = matching[0]
    assert summary.kind == "detector_z_rail_alignment"
    assert summary.status == ProcedureStatus.COMPLETED.value
    assert summary.parent_run_id is None
    assert summary.iteration_count == 2
    assert set(summary.target_asset_ids) == {
        _ASSET_DETECTOR_TABLE_ID,
        _ASSET_PROPAGATION_ID,
        _ASSET_CAMERA_ID,
        _ASSET_SCINTILLATOR_ID,
    }

    iterations = await bind_list_iterations(deps)(
        ListProcedureIterations(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert [i.iteration_index for i in iterations.items] == [1, 2]
    assert iterations.items[0].converged is False
    assert iterations.items[1].converged is True
