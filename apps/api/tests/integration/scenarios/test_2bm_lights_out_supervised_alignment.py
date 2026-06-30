"""Lights-out, agent-supervised alignment-and-first-acquisition at APS 2-BM.

cluster: Runs
archetype: agent
bc_primary: Run
bc_touches: Agent, Decision, Equipment, Operation, Recipe, Run

One overnight, unattended Run that exercises the full autonomous arc the
replay-scrubber paper is built around:

  1. An operator starts a calibration Run lights-out (subject_id=None) and
     leaves.
  2. CORA conducts the pre-scan rotation-axis centering alignment as a
     phase-of-Run Procedure (parent_run_id = the Run): a four-iteration
     peak-bracket search on SampleTop_X that converges.
  3. The run locks at the centered position, commands the science scan's
     continuous rotation (fly-scan, 0->180 deg), taxis to constant velocity and
     arms the PSO, and acquisition begins: the first two projections complete and
     the third is in flight.
  4. The beam drops mid-scan. The RunSupervisor agent HOLDS the Run (RunHeld
     carries the Decision link), leaving the third projection mid-flight.
  5. The beam returns and the start-safety envelope is good again, so the
     supervisor AUTO-RESUMES (RunResumed carries a Resume Decision).
  6. The fly-scan is restarted (the rotary stage taxis back to constant velocity
     and the PSO trigger is re-armed), the interrupted third projection is
     re-acquired, the science scan continues to the end, the collected dataset is
     written to disk, the Procedure completes, the Run completes.

The supervisor loop is driven white-box via `_supervise_tick` (the same
pattern as `test_2bm_run_supervisor_auto_resume.py`), beam availability is the
one injected fake (down on the first tick, up on the second), and the
alignment is conducted via the `append_activities` path (no softIOC). Default
deps (AllowAll authz, always-covered Clearance) plus a subjectless calibration
Run keep the envelope satisfied without the full beamtime/ESAF ceremony; the
point here is the autonomous hold/resume around a conducted alignment, not the
Clearance machinery (that is `test_2bm_run_supervisor_auto_resume.py`).

This is the scenario the paper's figures are exported from.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportPrivateUsage=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.seed_run_supervisor import RUN_SUPERVISOR_AGENT_ID, seed_run_supervisor_agent
from cora.api._run_supervisor import _MEM_HELD, ObservationRuleConfig, _supervise_tick
from cora.decision.aggregates.decision import load_decision
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.beam_availability_lookup import BeamAvailabilityLookupResult
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.operation._projections import register_operation_projections
from cora.operation.aggregates.procedure import PostgresActivityStore
from cora.operation.features.append_activities import ActivityInput, AppendProcedureActivities
from cora.operation.features.append_activities import bind as bind_append_step
from cora.operation.features.complete_procedure import CompleteProcedure
from cora.operation.features.complete_procedure import bind as bind_complete_procedure
from cora.operation.features.end_iteration import EndProcedureIteration
from cora.operation.features.end_iteration import bind as bind_end_iteration
from cora.operation.features.list_procedure_iterations import ListProcedureIterations
from cora.operation.features.list_procedure_iterations import bind as bind_list_iterations
from cora.operation.features.register_procedure import RegisterProcedure
from cora.operation.features.register_procedure import bind as bind_register_procedure
from cora.operation.features.start_iteration import StartProcedureIteration
from cora.operation.features.start_iteration import bind as bind_start_iteration
from cora.operation.features.start_procedure import StartProcedure
from cora.operation.features.start_procedure import bind as bind_start_procedure
from cora.run._projections import register_run_projections
from cora.run.features.abort_run import bind as bind_abort_run
from cora.run.features.complete_run import CompleteRun
from cora.run.features.complete_run import bind as bind_complete_run
from cora.run.features.hold_run import bind as bind_hold_run
from cora.run.features.list_runs import bind as bind_list_runs
from cora.run.features.resume_run import bind as bind_resume_run
from cora.run.features.start_run import StartRun
from cora.run.features.start_run import bind as bind_start_run
from cora.run.features.stop_run import bind as bind_stop_run
from cora.run.features.truncate_run import bind as bind_truncate_run
from cora.run.ports import InMemoryRunChannelLookup
from cora.shared.identity import ActorId
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._facility_fixture import operator_for
from tests.integration.scenarios._tomography_fixture import (
    RecipeSpec,
    TomographyAssetIds,
    define_recipe_ladder,
    install_and_activate_tomography_assets,
    recipe_ladder_id_prefix,
    tomography_install_id_prefix,
)

_RULES_OFF = ObservationRuleConfig(
    quality_channel_name=None,
    stall_channel_name=None,
    stall_window_factor=3.0,
    stall_hysteresis_ticks=2,
    feed_heartbeat_ceiling_seconds=None,
)

_NOW = datetime(2026, 5, 19, 1, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000004700bb")

# Scenario tag: 470 (lights-out supervised alignment).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000470501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000470a01")

_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000470a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000470a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000470a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000470a41")

_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d470")
_METHOD_ID = UUID("01900000-0000-7000-8000-000000470d01")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-000000470d11")
_PLAN_ID = UUID("01900000-0000-7000-8000-000000470d21")
_RUN_ID = UUID("01900000-0000-7000-8000-000000470f02")

_PROCEDURE_ID = UUID("01900000-0000-7000-8000-000000470f01")
_STEPS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-000000470f11")
_STEPS_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-000000470f12")

_TOMO_ASSETS = TomographyAssetIds(
    unit_id=_2BM_UNIT_ID,
    rotary_cap_id=_CAP_ROTARY_STAGE_ID,
    linear_x_cap_id=_CAP_LINEAR_STAGE_ID,
    camera_cap_id=_CAP_CAMERA_ID,
    scintillator_cap_id=_CAP_SCINTILLATOR_ID,
    rotary_id=_ASSET_AEROTECH_ABRS_ID,
    linear_x_id=_ASSET_SAMPLE_TOP_X_ID,
    camera_id=_ASSET_ORYX_5MP_ID,
    scintillator_id=_ASSET_SCINTILLATOR_LUAG_ID,
)

_RECIPE = RecipeSpec(
    capability_id=_CAPABILITY_ID,
    capability_code="cora.capability.tomography",
    capability_name="Tomography",
    method_id=_METHOD_ID,
    method_name="tomography",
    needed_family_ids=frozenset(
        {_CAP_ROTARY_STAGE_ID, _CAP_LINEAR_STAGE_ID, _CAP_CAMERA_ID, _CAP_SCINTILLATOR_ID}
    ),
    parameters_schema={
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "exposure_ms": {"type": "integer", "minimum": 1},
            "n_projections": {"type": "integer", "minimum": 1},
            "angle_range_deg": {"type": "number", "minimum": 1, "maximum": 360},
        },
        "required": ["exposure_ms", "n_projections", "angle_range_deg"],
    },
    practice_id=_PRACTICE_ID,
    practice_name="2BM_tomography_practice",
    site_id=_APS_SITE_ID,
    plan_id=_PLAN_ID,
    plan_name="2BM_lights_out_tomography_plan",
    plan_asset_ids=frozenset(
        {
            _ASSET_AEROTECH_ABRS_ID,
            _ASSET_SAMPLE_TOP_X_ID,
            _ASSET_ORYX_5MP_ID,
            _ASSET_SCINTILLATOR_LUAG_ID,
        }
    ),
)


def _id_queue() -> list[UUID]:
    """Setup ids through the alignment iterations, then a generous pad: the
    supervisor allocates an unpredictable number of ids per tick (drain
    correlation ids, Decision id, command correlation + event ids), and
    complete_procedure / complete_run draw their event ids from the same pad."""
    e = uuid4
    return [
        *tomography_install_id_prefix(asset_ids=_TOMO_ASSETS),
        *recipe_ladder_id_prefix(spec=_RECIPE),
        # start_run
        _RUN_ID,
        e(),  # RunStarted event
        # register_procedure (parent_run_id = run) + start_procedure
        _PROCEDURE_ID,
        e(),  # ProcedureRegistered event
        e(),  # ProcedureStarted event
        # iteration 1 (first append lazy-opens the activities logbook)
        e(),  # start_iteration(1) event
        _STEPS_LOGBOOK_ID,
        _STEPS_OPEN_EVENT_ID,
        e(),  # end_iteration(1) event
        # iterations 2-4 (logbook already open; entries carry their own uuid4 ids)
        e(),
        e(),  # start/end iteration(2)
        e(),
        e(),  # start/end iteration(3)
        e(),
        e(),  # start/end iteration(4)
        # supervisor ticks (hold + resume) + complete_procedure + complete_run + drains
        *[e() for _ in range(300)],
    ]


def _setpoint(*, target_mm: float, role: str, note: str | None = None) -> ActivityInput:
    """A SampleTop_X centering setpoint."""
    payload: dict[str, Any] = {
        "channel": "SampleTop_X",
        "target_value": target_mm,
        "units": "mm",
        "role": role,
    }
    if note is not None:
        payload["note"] = note
    return ActivityInput(event_id=uuid4(), step_kind="setpoint", payload=payload, sampled_at=_NOW)


def _acquire(*, exposure_ms: int, purpose: str) -> ActivityInput:
    """An acquisition action (alignment frame or science projection)."""
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload={
            "action_name": "acquire_frame",
            "params": {"exposure_ms": exposure_ms, "purpose": purpose},
        },
        sampled_at=_NOW,
    )


def _centering_check(
    *, residual_px: float, direction: str | None, passed: bool = False
) -> ActivityInput:
    """A rotation-axis centering check: residual of the center-of-rotation fit
    (smaller is better; the search brackets the minimum)."""
    payload: dict[str, Any] = {
        "channel": "cor_residual",
        "passed": passed,
        "source": "tomopy.recon.rotation",
        "actual": residual_px,
        "units": "px",
    }
    if direction is not None:
        payload["direction"] = direction
    return ActivityInput(event_id=uuid4(), step_kind="check", payload=payload, sampled_at=_NOW)


def _projection(*, index: int, angle_deg: float, result: str) -> ActivityInput:
    """A science-scan projection. The interrupted projection records a pre-effect
    in-flight marker (intent before effect) and, after recovery, its outcome, so
    folding to the beam-loss instant shows it as an open interval; the others
    record an outcome directly."""
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload={
            "action_name": "acquire_projection",
            "params": {"exposure_ms": 100, "angle_deg": angle_deg, "index": index},
            "result": result,
        },
        sampled_at=_NOW,
    )


def _fly_scan_setpoint() -> ActivityInput:
    """Command the science scan's rotation: a continuous 0->180 deg fly-scan on
    the rotary stage, set once before the projections are triggered."""
    return ActivityInput(
        event_id=uuid4(),
        step_kind="setpoint",
        payload={
            "channel": "rotation_angle",
            "target_value": 180.0,
            "units": "deg",
            "role": "fly_scan",
            "note": "continuous 0->180 deg sweep",
        },
        sampled_at=_NOW,
    )


def _taxi_setpoint() -> ActivityInput:
    """Fly-scan taxi: bring the rotary stage to a run-up position so it is at
    constant velocity before acquiring. Needed both at the start of the scan and
    again on the restart after a hold."""
    return ActivityInput(
        event_id=uuid4(),
        step_kind="setpoint",
        payload={
            "channel": "rotation_angle",
            "target_value": -5.0,
            "units": "deg",
            "role": "taxi",
            "note": "run-up to constant velocity",
        },
        sampled_at=_NOW,
    )


def _fly_scan_prep() -> ActivityInput:
    """Fly-scan setup: arm the PSO trigger and prepare the scan before
    acquisition begins (and again before it resumes after a hold)."""
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload={
            "action_name": "fly_scan_prep",
            "params": {"rearm_pso": True},
            "result": "ok",
        },
        sampled_at=_NOW,
    )


def _write_dataset() -> ActivityInput:
    """Save the collected scan: write the projections to an HDF5/DXfile dataset
    once acquisition is complete (the 2-BM data-collection run ends here; volume
    reconstruction is a separate downstream job)."""
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload={
            "action_name": "write_dataset",
            "params": {"format": "dxfile-hdf5", "projections": 6},
            "result": "ok",
        },
        sampled_at=_NOW,
    )


class _BeamDown:
    async def read(self) -> BeamAvailabilityLookupResult:
        return BeamAvailabilityLookupResult(
            fes_open=False, sbs_open=True, fes_permit=True, quality_ok=True
        )


class _BeamOpen:
    async def read(self) -> BeamAvailabilityLookupResult:
        return BeamAvailabilityLookupResult(
            fes_open=True, sbs_open=True, fes_permit=True, quality_ok=True
        )


async def _drain_run(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_run_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _drain_operation(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_operation_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


def _tick_kwargs(
    deps: Kernel, beam: object, memory: dict[UUID, str], settle: dict[UUID, int]
) -> dict[str, Any]:
    return {
        "deps": deps,
        "list_runs": bind_list_runs(deps),
        "hold_run": bind_hold_run(deps),
        "resume_run": bind_resume_run(deps),
        "truncate_run": bind_truncate_run(deps),
        "abort_run": bind_abort_run(deps),
        "stop_run": bind_stop_run(deps),
        "beam_lookup": beam,
        "memory": memory,
        "settle": settle,
        "liveness": set(),
        "channel_lookup": InMemoryRunChannelLookup(),
        "rules_config": _RULES_OFF,
        "quality": set(),
        "stall": set(),
        "stall_streak": {},
        "feed_dead_warned": set(),
        "truncate_settle": {},
        "quality_act_settle": {},
        "stall_act_settle": {},
        "liveness_ceiling_seconds": None,
        "advise_enabled": False,
        "resume_enabled": True,
        "resume_settle_ticks": 1,
        "truncate_enabled": False,
        "truncate_settle_ticks": 3,
        "quality_act_enabled": False,
        "quality_settle_ticks": 3,
        "stall_act_enabled": False,
        "stall_settle_ticks": 2,
    }


@pytest.mark.integration
async def test_lights_out_run_is_aligned_supervised_and_audited(db_pool: asyncpg.Pool) -> None:
    """An overnight Run: conducted centering alignment converges, a beam dump
    holds the Run mid-acquisition, the supervisor auto-resumes, and the Run
    completes. Asserts the full auditable record the scrubber visualizes."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())
    step_store = PostgresActivityStore(db_pool)

    await seed_run_supervisor_agent(deps)
    await install_and_activate_tomography_assets(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        asset_ids=_TOMO_ASSETS,
    )
    await define_recipe_ladder(
        deps, principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID, spec=_RECIPE
    )

    # ----- Operator starts the lights-out calibration Run and leaves -----
    await bind_start_run(deps)(
        StartRun(
            name="2-BM lights-out tomography (pre-scan align + science scan)",
            plan_id=_PLAN_ID,
            subject_id=None,
            override_parameters={
                "exposure_ms": 100,
                "n_projections": 1500,
                "angle_range_deg": 180.0,
            },
            trigger_source="operator-manual; lights-out overnight session",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_run(db_pool)

    # ----- CORA conducts the rotation-axis centering alignment (phase-of-Run) -----
    await bind_register_procedure(deps)(
        RegisterProcedure(
            name="2-BM rotation-axis centering (pre-scan alignment)",
            kind="alignment",
            target_asset_ids=frozenset(
                {_ASSET_AEROTECH_ABRS_ID, _ASSET_SAMPLE_TOP_X_ID, _ASSET_ORYX_5MP_ID}
            ),
            parent_run_id=_RUN_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start_procedure(deps)(
        StartProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Four-iteration peak-bracket search on SampleTop_X (minimize COR residual).
    iters = (
        (
            (
                _setpoint(target_mm=0.000, role="initial", note="user-supplied start"),
                _acquire(exposure_ms=100, purpose="alignment"),
                _centering_check(residual_px=2.00, direction=None),
            ),
            False,
            "initial residual 2.00 px; minimum not yet bracketed",
        ),
        (
            (
                _setpoint(target_mm=0.040, role="step_positive"),
                _acquire(exposure_ms=100, purpose="alignment"),
                _centering_check(residual_px=1.05, direction="better"),
            ),
            False,
            "residual improving (1.05 px); minimum not yet bracketed",
        ),
        (
            (
                _setpoint(target_mm=0.080, role="step_positive"),
                _acquire(exposure_ms=100, purpose="alignment"),
                _centering_check(residual_px=1.40, direction="worse"),
            ),
            False,
            "residual rose to 1.40 px; minimum bracketed in [0.040, 0.080] mm",
        ),
        (
            (
                _setpoint(target_mm=0.060, role="bisect"),
                _acquire(exposure_ms=100, purpose="alignment"),
                _centering_check(residual_px=0.30, direction="minimum", passed=True),
            ),
            True,
            None,
        ),
    )

    for index, (entries, converged, reason) in enumerate(iters, start=1):
        await bind_start_iteration(deps)(
            StartProcedureIteration(procedure_id=_PROCEDURE_ID, iteration_index=index),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        count = await bind_append_step(deps, step_store=step_store)(
            AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=entries),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        assert count == 3
        await bind_end_iteration(deps)(
            EndProcedureIteration(
                procedure_id=_PROCEDURE_ID,
                iteration_index=index,
                converged=converged,
                reason=reason,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Lock at the converged center, command the fly-scan rotation, taxi to
    # constant velocity and arm the PSO, then begin the scan: the first two
    # projections complete and the third is in flight (an in-flight marker
    # recorded before the effect) when the beam drops.
    await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(
            procedure_id=_PROCEDURE_ID,
            entries=(
                _setpoint(target_mm=0.060, role="lock_at_center"),
                _fly_scan_setpoint(),
                _taxi_setpoint(),
                _fly_scan_prep(),
                _projection(index=1, angle_deg=0.0, result="ok"),
                _projection(index=2, angle_deg=30.0, result="ok"),
                _projection(index=3, angle_deg=60.0, result="in_flight"),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_run(db_pool)

    # ----- Beam dump: the RunSupervisor agent holds the Run mid-acquisition ---
    memory: dict[UUID, str] = {}
    settle: dict[UUID, int] = {}
    await _supervise_tick(**_tick_kwargs(deps, _BeamDown(), memory, settle))
    assert memory[_RUN_ID] == _MEM_HELD
    run_events, _ = await deps.event_store.load("Run", _RUN_ID)
    assert [e.event_type for e in run_events] == ["RunStarted", "RunHeld"]
    await _drain_run(db_pool)

    # ----- Beam returns: the supervisor auto-resumes (envelope safe again) ----
    await _supervise_tick(**_tick_kwargs(deps, _BeamOpen(), memory, settle))
    run_events, _ = await deps.event_store.load("Run", _RUN_ID)
    assert [e.event_type for e in run_events] == ["RunStarted", "RunHeld", "RunResumed"]
    await _drain_run(db_pool)

    # Fly-scan restart after resume: taxi the rotary stage back to constant
    # velocity and re-arm the PSO trigger before acquisition resumes.
    await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(
            procedure_id=_PROCEDURE_ID,
            entries=(_taxi_setpoint(), _fly_scan_prep()),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # The interrupted third projection is re-acquired and completes, the scan
    # continues to the end, and the collected dataset is written to disk: the
    # 2-BM data-collection run ends with the save.
    await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(
            procedure_id=_PROCEDURE_ID,
            entries=(
                _projection(index=3, angle_deg=60.0, result="ok"),
                _projection(index=4, angle_deg=90.0, result="ok"),
                _projection(index=5, angle_deg=120.0, result="ok"),
                _projection(index=6, angle_deg=150.0, result="ok"),
                _write_dataset(),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await bind_complete_procedure(deps)(
        CompleteProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_complete_run(deps)(
        CompleteRun(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: Run lifecycle is the four-beat autonomous arc -----
    run_events, _ = await deps.event_store.load("Run", _RUN_ID)
    assert [e.event_type for e in run_events] == [
        "RunStarted",
        "RunHeld",
        "RunResumed",
        "RunCompleted",
    ]

    # ----- Assert: the hold and resume were the supervisor agent's decisions ---
    resumed = next(e for e in run_events if e.event_type == "RunResumed")
    decision_id = resumed.payload["decided_by_decision_id"]
    assert decision_id is not None
    decision = await load_decision(deps.event_store, UUID(decision_id))
    assert decision is not None
    assert decision.context.value == "RunSupervision"
    assert decision.choice.value == "Resume"
    assert decision.decided_by == ActorId(RUN_SUPERVISOR_AGENT_ID)

    # ----- Assert: the Procedure is a phase-of-Run that converged -----
    proc_events, version = await deps.event_store.load("Procedure", _PROCEDURE_ID)
    assert version == 12
    assert proc_events[0].payload["parent_run_id"] == str(_RUN_ID)
    assert [e.event_type for e in proc_events] == [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureIterationStarted",
        "ProcedureActivitiesLogbookOpened",
        "ProcedureIterationEnded",
        "ProcedureIterationStarted",
        "ProcedureIterationEnded",
        "ProcedureIterationStarted",
        "ProcedureIterationEnded",
        "ProcedureIterationStarted",
        "ProcedureIterationEnded",
        "ProcedureCompleted",
    ]

    await _drain_operation(db_pool)
    iterations = await bind_list_iterations(deps)(
        ListProcedureIterations(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert [i.iteration_index for i in iterations.items] == [1, 2, 3, 4]
    assert [i.converged for i in iterations.items] == [False, False, False, True]

    # ----- Assert: six science projections; the third was caught mid-flight -----
    async with db_pool.acquire() as conn:
        proj_rows = await conn.fetch(
            "SELECT payload->'params'->>'index' AS idx, payload->>'result' AS result "
            "FROM entries_operation_procedure_activities WHERE procedure_id = $1 "
            "AND payload->>'action_name' = 'acquire_projection'",
            _PROCEDURE_ID,
        )
    by_index: dict[str, list[str]] = {}
    for r in proj_rows:
        by_index.setdefault(r["idx"], []).append(r["result"])
    assert sorted(by_index) == ["1", "2", "3", "4", "5", "6"]
    assert sorted(by_index["3"]) == ["in_flight", "ok"]
    assert all(by_index[i] == ["ok"] for i in ("1", "2", "4", "5", "6"))

    # ----- Assert: the collected dataset was written to disk at the end -----
    async with db_pool.acquire() as conn:
        save_rows = await conn.fetch(
            "SELECT payload->>'result' AS result FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1 AND payload->>'action_name' = 'write_dataset'",
            _PROCEDURE_ID,
        )
    assert len(save_rows) == 1
    assert save_rows[0]["result"] == "ok"

    # ----- Assert: the science scan commanded a continuous rotation (fly-scan) ---
    async with db_pool.acquire() as conn:
        rot_rows = await conn.fetch(
            "SELECT payload->>'role' AS role FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1 AND payload->>'channel' = 'rotation_angle' "
            "AND payload->>'role' = 'fly_scan'",
            _PROCEDURE_ID,
        )
    assert len(rot_rows) == 1
    assert rot_rows[0]["role"] == "fly_scan"

    # ----- Assert: the fly-scan was prepped at the start and restarted after the
    # hold (a taxi + PSO re-arm each time) -----
    async with db_pool.acquire() as conn:
        taxi_prep_rows = await conn.fetch(
            "SELECT 1 FROM entries_operation_procedure_activities WHERE procedure_id = $1 "
            "AND (payload->>'role' = 'taxi' OR payload->>'action_name' = 'fly_scan_prep')",
            _PROCEDURE_ID,
        )
    assert len(taxi_prep_rows) == 4
