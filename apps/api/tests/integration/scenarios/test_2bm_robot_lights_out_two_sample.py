"""Robot-loaded, two-sample lights-out session at APS 2-BM.

cluster: Runs
archetype: agent
bc_primary: Run
bc_touches: Agent, Campaign, Decision, Equipment, Operation, Recipe, Run, Subject

One overnight Campaign in which a sample-changing robot loads two samples in
turn. For each sample the operator starts a Run bound to that sample's Subject
and to the Campaign; the robot mounts the Subject; CORA conducts a rotation-axis
centering alignment (a 4-iteration peak-bracket search that converges); the
science scan runs; the robot dismounts the Subject; the Run completes. On the
second sample the beam drops while the third projection is in flight, the
RunSupervisor agent holds the Run and auto-resumes it, and the fly-scan
restarts.

This is the scenario the paper's Figure 1 is exported from (see
papers/2026-vaxautosci-scrubber/data/build_lights_out_data.py). It extends the
single-sample lights-out scenario
(test_2bm_lights_out_supervised_alignment.py) with the robot sample changer and
the per-sample Subject custody lifecycle grouped under one Campaign.

Modeling notes (ROBOT-1 posture, adversarially-verified across 16 beamlines):
the robot is one Positioner-presenting Asset (the Manipulator Family), NOT a new
SampleChanger Family. It loads / unloads a Subject via the Subject BC's
mount_subject / dismount_subject custody lifecycle. This scenario is the first
place CORA models robot mount/dismount as activities with real Subject custody;
if 32-id / 19-BM later model the same lifecycle, that is the rule-of-three
trigger to revisit whether SampleChanger should graduate into its own Family
(the Goniometer-graduation precedent). Until then the locked posture holds.

Scope (modeled vs. deployed). The sample-change hardware at 2-BM (a UR3e arm
with its own EPICS control) is deployed and has executed mount/dismount cycles
with a beamline handshake; tomoscan is PV-scriptable. CORA's orchestration of
the robot is modeled here, played through the real Kernel + Postgres event
store; the supervisor decision layer beyond hold/resume (FOV-fit and lens-change
branches, per-sample recentering as a supervised decision) is out of scope.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportPrivateUsage=false

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.seed_run_supervisor import RUN_SUPERVISOR_AGENT_ID, seed_run_supervisor_agent
from cora.api._run_supervisor import _MEM_HELD, ObservationRuleConfig, _supervise_tick
from cora.campaign.aggregates.campaign import CampaignIntent
from cora.campaign.features.register_campaign import RegisterCampaign
from cora.campaign.features.register_campaign import bind as bind_register_campaign
from cora.campaign.features.start_campaign import StartCampaign
from cora.campaign.features.start_campaign import bind as bind_start_campaign
from cora.decision.aggregates.decision import load_decision
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.activate_asset import bind as bind_activate_asset
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
from cora.subject.features.dismount_subject import DismountSubject
from cora.subject.features.dismount_subject import bind as bind_dismount_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.mount_subject import bind as bind_mount_subject
from cora.subject.features.register_subject import RegisterSubject
from cora.subject.features.register_subject import bind as bind_register_subject
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._facility_fixture import DeviceSpec, install_aps_unit, operator_for
from tests.integration.scenarios._tomography_fixture import (
    RecipeSpec,
    define_recipe_ladder,
    recipe_ladder_id_prefix,
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
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000004720bb")

# Scenario tag: 472 (robot lights-out two-sample).
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000472a01")

_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))
_CAP_MANIPULATOR_ID = family_stream_id(FamilyName("Manipulator"))

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000472a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000472a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000472a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000472a41")
_ASSET_ROBOT_ID = UUID("01900000-0000-7000-8000-000000472a51")

_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d472")
_METHOD_ID = UUID("01900000-0000-7000-8000-000000472d01")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-000000472d11")
_PLAN_ID = UUID("01900000-0000-7000-8000-000000472d21")
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000472501")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000472b01")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000472b11")
_SUBJECT_A_ID = UUID("01900000-0000-7000-8000-000000472b21")
_SUBJECT_B_ID = UUID("01900000-0000-7000-8000-000000472b31")

_DEVICES = (
    DeviceSpec("Rotary", _ASSET_AEROTECH_ABRS_ID, "RotaryStage", _CAP_ROTARY_STAGE_ID),
    DeviceSpec("SampleTop_X", _ASSET_SAMPLE_TOP_X_ID, "LinearStage", _CAP_LINEAR_STAGE_ID),
    DeviceSpec("Camera", _ASSET_ORYX_5MP_ID, "Camera", _CAP_CAMERA_ID),
    DeviceSpec("Scintillator", _ASSET_SCINTILLATOR_LUAG_ID, "Scintillator", _CAP_SCINTILLATOR_ID),
    DeviceSpec("SampleChanger", _ASSET_ROBOT_ID, "Manipulator", _CAP_MANIPULATOR_ID),
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
    plan_name="2BM_robot_lights_out_plan",
    plan_asset_ids=frozenset(
        {
            _ASSET_AEROTECH_ABRS_ID,
            _ASSET_SAMPLE_TOP_X_ID,
            _ASSET_ORYX_5MP_ID,
            _ASSET_SCINTILLATOR_LUAG_ID,
        }
    ),
)


@dataclass(frozen=True)
class _SamplePlan:
    """One sample's run within the campaign: the sample's Subject, its own COR
    search, and whether the beam drops during its scan. Run and Procedure ids
    are captured from the handlers at runtime (returned by the bind calls), not
    pinned in the id-queue, so the per-sample ceremony is robust to how many ids
    mount / start_run / drains consume."""

    label: str
    subject_id: UUID
    iterations: tuple[tuple[float, float, str | None, bool, str | None], ...]
    beam_loss: bool


@dataclass(frozen=True)
class _SampleResult:
    """The ids a sample's run produced, for the assertions to load by."""

    run_id: UUID
    procedure_id: UUID


# (target_mm, residual_px, direction, converged, reason). Sample A converges to
# a different center than sample B: the per-sample recentering finds each
# sample's position relative to the fixed rotation axis.
_SAMPLE_A = _SamplePlan(
    label="A",
    subject_id=_SUBJECT_A_ID,
    iterations=(
        (0.000, 1.80, None, False, "initial residual 1.80 px; minimum not yet bracketed"),
        (0.030, 0.90, "better", False, "residual improving (0.90 px); minimum not yet bracketed"),
        (
            0.060,
            1.15,
            "worse",
            False,
            "residual rose to 1.15 px; minimum bracketed in [0.030, 0.060] mm",
        ),
        (0.045, 0.25, "minimum", True, None),
    ),
    beam_loss=False,
)
_SAMPLE_B = _SamplePlan(
    label="B",
    subject_id=_SUBJECT_B_ID,
    iterations=(
        (0.000, 2.00, None, False, "initial residual 2.00 px; minimum not yet bracketed"),
        (0.040, 1.05, "better", False, "residual improving (1.05 px); minimum not yet bracketed"),
        (
            0.080,
            1.40,
            "worse",
            False,
            "residual rose to 1.40 px; minimum bracketed in [0.040, 0.080] mm",
        ),
        (0.060, 0.30, "minimum", True, None),
    ),
    beam_loss=True,
)


def _id_queue() -> list[UUID]:
    """Setup ids, then a generous uuid4 pad. Only aggregates the assertions load
    by a fixed id are pinned (assets, recipe ladder, PI actor, subjects,
    campaign). Run and Procedure ids are captured from the handlers at runtime,
    so they are NOT pinned here; the custody + run + procedure + supervisor-tick
    ceremonies draw the rest from the pad."""
    e = uuid4
    ids: list[UUID] = []
    # install_aps_unit: unit + 5 devices (family ids derived from name, not
    # popped) then 5 activate events.
    from tests.integration.scenarios._facility_fixture import facility_id_prefix

    ids += facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=_DEVICES)
    ids += [e() for _ in range(len(_DEVICES))]  # activate_asset events
    ids += recipe_ladder_id_prefix(spec=_RECIPE)
    # Beamtime: PI actor, two subjects, campaign (register + start).
    ids += [_PI_ACTOR_ID, e(), _SUBJECT_A_ID, e(), _SUBJECT_B_ID, e(), _CAMPAIGN_ID, e(), e()]
    # Per-sample runs + procedures + supervisor ticks draw from the pad.
    ids += [e() for _ in range(600)]
    return ids


def _setpoint(*, target_mm: float, role: str, note: str | None = None) -> ActivityInput:
    payload: dict[str, Any] = {
        "channel": "SampleTop_X",
        "target_value": target_mm,
        "units": "mm",
        "role": role,
    }
    if note is not None:
        payload["note"] = note
    return ActivityInput(event_id=uuid4(), step_kind="setpoint", payload=payload, sampled_at=_NOW)


def _acquire(*, purpose: str) -> ActivityInput:
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload={
            "action_name": "acquire_frame",
            "params": {"exposure_ms": 100, "purpose": purpose},
        },
        sampled_at=_NOW,
    )


def _centering_check(
    *, residual_px: float, direction: str | None, passed: bool = False
) -> ActivityInput:
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
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload={"action_name": "fly_scan_prep", "params": {"rearm_pso": True}, "result": "ok"},
        sampled_at=_NOW,
    )


def _write_dataset(*, projections: int) -> ActivityInput:
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload={
            "action_name": "write_dataset",
            "params": {"format": "dxfile-hdf5", "projections": projections},
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
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


async def _drain_operation(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_operation_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


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


async def _run_one_sample(
    deps: Kernel, db_pool: asyncpg.Pool, step_store: PostgresActivityStore, sp: _SamplePlan
) -> _SampleResult:
    """Play one sample's run within the campaign: robot mount, conducted
    alignment, science scan (with a hold/resume on the beam-loss sample), robot
    dismount, run completion. Returns the run + procedure ids captured from the
    handlers."""
    # The robot mounts the sample onto the rotary stage (Subject custody: mount).
    # Mounting precedes Run-start: a Run can only start against a Subject that is
    # already Mounted (RunSubjectNotMountableError otherwise).
    await bind_mount_subject(deps)(
        MountSubject(
            subject_id=sp.subject_id,
            asset_id=_ASSET_AEROTECH_ABRS_ID,
            reason=f"robot sample changer mounts sample {sp.label} onto the rotary stage",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Operator starts the sample's Run, bound to its (now mounted) Subject and
    # the Campaign. The handler returns the new Run id.
    run_id = await bind_start_run(deps)(
        StartRun(
            name=f"2-BM robot-loaded tomography (sample {sp.label})",
            plan_id=_PLAN_ID,
            subject_id=sp.subject_id,
            campaign_id=_CAMPAIGN_ID,
            override_parameters={
                "exposure_ms": 100,
                "n_projections": 1500,
                "angle_range_deg": 180.0,
            },
            trigger_source="operator-manual; robot-loaded lights-out overnight session",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_run(db_pool)

    # CORA conducts the per-sample rotation-axis centering alignment. The handler
    # returns the new Procedure id.
    procedure_id = await bind_register_procedure(deps)(
        RegisterProcedure(
            name=f"2-BM rotation-axis centering (sample {sp.label})",
            kind="alignment",
            target_asset_ids=frozenset(
                {_ASSET_AEROTECH_ABRS_ID, _ASSET_SAMPLE_TOP_X_ID, _ASSET_ORYX_5MP_ID}
            ),
            parent_run_id=run_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start_procedure(deps)(
        StartProcedure(procedure_id=procedure_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    for index, (target_mm, residual, direction, converged, reason) in enumerate(
        sp.iterations, start=1
    ):
        role = "initial" if index == 1 else ("bisect" if converged else "step_positive")
        note = "recenter after mount" if index == 1 else None
        await bind_start_iteration(deps)(
            StartProcedureIteration(procedure_id=procedure_id, iteration_index=index),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        count = await bind_append_step(deps, step_store=step_store)(
            AppendProcedureActivities(
                procedure_id=procedure_id,
                entries=(
                    _setpoint(target_mm=target_mm, role=role, note=note),
                    _acquire(purpose="alignment"),
                    _centering_check(residual_px=residual, direction=direction, passed=converged),
                ),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        assert count == 3
        await bind_end_iteration(deps)(
            EndProcedureIteration(
                procedure_id=procedure_id,
                iteration_index=index,
                converged=converged,
                reason=reason,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Lock at the converged center; command the fly-scan; taxi + arm; acquire.
    converged_center = sp.iterations[-1][0]
    await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(
            procedure_id=procedure_id,
            entries=(
                _setpoint(target_mm=converged_center, role="lock_at_center"),
                _fly_scan_setpoint(),
                _taxi_setpoint(),
                _fly_scan_prep(),
                _projection(index=1, angle_deg=0.0, result="ok"),
                _projection(index=2, angle_deg=30.0, result="ok"),
                _projection(index=3, angle_deg=60.0, result="in_flight" if sp.beam_loss else "ok"),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_run(db_pool)

    if sp.beam_loss:
        # Beam dump: the supervisor holds, then auto-resumes when beam returns.
        memory: dict[UUID, str] = {}
        settle: dict[UUID, int] = {}
        await _supervise_tick(**_tick_kwargs(deps, _BeamDown(), memory, settle))
        assert memory[run_id] == _MEM_HELD
        await _drain_run(db_pool)
        await _supervise_tick(**_tick_kwargs(deps, _BeamOpen(), memory, settle))
        await _drain_run(db_pool)
        # Fly-scan restart, re-acquire the interrupted projection, finish.
        await bind_append_step(deps, step_store=step_store)(
            AppendProcedureActivities(
                procedure_id=procedure_id,
                entries=(
                    _taxi_setpoint(),
                    _fly_scan_prep(),
                    _projection(index=3, angle_deg=60.0, result="ok"),
                    _projection(index=4, angle_deg=90.0, result="ok"),
                    _projection(index=5, angle_deg=120.0, result="ok"),
                    _projection(index=6, angle_deg=150.0, result="ok"),
                    _write_dataset(projections=6),
                ),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    else:
        await bind_append_step(deps, step_store=step_store)(
            AppendProcedureActivities(
                procedure_id=procedure_id,
                entries=(_write_dataset(projections=3),),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    await bind_complete_procedure(deps)(
        CompleteProcedure(procedure_id=procedure_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # The robot dismounts the sample (Subject custody: dismount).
    await bind_dismount_subject(deps)(
        DismountSubject(
            subject_id=sp.subject_id,
            reason=f"robot sample changer dismounts sample {sp.label} after the scan",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_complete_run(deps)(
        CompleteRun(run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return _SampleResult(run_id=run_id, procedure_id=procedure_id)


@pytest.mark.integration
async def test_robot_two_sample_campaign_is_loaded_supervised_and_audited(
    db_pool: asyncpg.Pool,
) -> None:
    """A robot loads two samples in turn under one Campaign; each is mounted,
    recentered, scanned, and dismounted; the second sample's scan is held and
    resumed by the supervisor on beam loss. Assert the full auditable record the
    scrubber visualizes: robot custody per sample, two run lifecycles (one plain,
    one held/resumed), per-sample converged alignments, and the interrupted
    projection caught mid-flight."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())
    step_store = PostgresActivityStore(db_pool)

    await seed_run_supervisor_agent(deps)

    # ----- Facility: the 2-BM imaging chain + the sample-changer robot -----
    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
        unit_name="2-BM",
    )
    for aid in (
        _ASSET_AEROTECH_ABRS_ID,
        _ASSET_SAMPLE_TOP_X_ID,
        _ASSET_ORYX_5MP_ID,
        _ASSET_SCINTILLATOR_LUAG_ID,
        _ASSET_ROBOT_ID,
    ):
        await bind_activate_asset(deps)(
            ActivateAsset(asset_id=aid),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    await define_recipe_ladder(
        deps, principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID, spec=_RECIPE
    )

    # ----- Beamtime: PI, two subjects, one Campaign spanning both samples -----
    from cora.access.features.register_actor import RegisterActor
    from cora.access.features.register_actor import bind as bind_register_actor

    await bind_register_actor(deps, profile_store=make_pg_profile_store(db_pool))(
        RegisterActor(name="Proposal 2026-5678 PI"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_register_subject(deps)(
        RegisterSubject(name="porous sandstone core (Proposal 2026-5678, sample A)"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_register_subject(deps)(
        RegisterSubject(name="porous sandstone core (Proposal 2026-5678, sample B)"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_register_campaign(deps)(
        RegisterCampaign(
            name="Proposal 2026-5678 robot-loaded overnight session",
            intent=CampaignIntent.COORDINATION,
            lead_actor_id=_PI_ACTOR_ID,
            subject_id=_SUBJECT_A_ID,
            description="Two-sample robot-loaded lights-out tomography",
            tags=frozenset({"proposal", "tomography", "robot", "lights_out"}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start_campaign(deps)(
        StartCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- The two samples, in turn, under the campaign -----
    result_a = await _run_one_sample(deps, db_pool, step_store, _SAMPLE_A)
    result_b = await _run_one_sample(deps, db_pool, step_store, _SAMPLE_B)

    # ----- Assert: sample A run is a clean two-beat arc -----
    run_a_events, _ = await deps.event_store.load("Run", result_a.run_id)
    assert [e.event_type for e in run_a_events] == ["RunStarted", "RunCompleted"]

    # ----- Assert: sample B run is the four-beat autonomous arc -----
    run_b_events, _ = await deps.event_store.load("Run", result_b.run_id)
    assert [e.event_type for e in run_b_events] == [
        "RunStarted",
        "RunHeld",
        "RunResumed",
        "RunCompleted",
    ]

    # ----- Assert: both runs carry the campaign id -----
    for events in (run_a_events, run_b_events):
        started = next(e for e in events if e.event_type == "RunStarted")
        assert started.payload["campaign_id"] == str(_CAMPAIGN_ID)

    # ----- Assert: sample B hold + resume were the supervisor's decisions -----
    resumed = next(e for e in run_b_events if e.event_type == "RunResumed")
    decision_id = resumed.payload["decided_by_decision_id"]
    assert decision_id is not None
    decision = await load_decision(deps.event_store, UUID(decision_id))
    assert decision is not None
    assert decision.context.value == "RunSupervision"
    assert decision.choice.value == "Resume"
    assert decision.decided_by == ActorId(RUN_SUPERVISOR_AGENT_ID)

    # ----- Assert: each subject went through the robot custody lifecycle -----
    for subject_id in (_SUBJECT_A_ID, _SUBJECT_B_ID):
        subj_events, _ = await deps.event_store.load("Subject", subject_id)
        types = [e.event_type for e in subj_events]
        assert "SubjectMounted" in types
        assert "SubjectDismounted" in types
        assert types.index("SubjectMounted") < types.index("SubjectDismounted")

    # ----- Assert: both procedures converged on their last iteration -----
    for result in (result_a, result_b):
        proc_events, _ = await deps.event_store.load("Procedure", result.procedure_id)
        assert proc_events[0].payload["parent_run_id"] == str(result.run_id)
        ended = [e for e in proc_events if e.event_type == "ProcedureIterationEnded"]
        assert len(ended) == 4
        assert ended[-1].payload["converged"] is True
        assert all(e.payload["converged"] is False for e in ended[:-1])

    # ----- Assert: sample B's third projection was caught mid-flight -----
    await _drain_operation(db_pool)
    async with db_pool.acquire() as conn:
        proj_rows = await conn.fetch(
            "SELECT payload->'params'->>'index' AS idx, payload->>'result' AS result "
            "FROM entries_operation_procedure_activities WHERE procedure_id = $1 "
            "AND payload->>'action_name' = 'acquire_projection'",
            result_b.procedure_id,
        )
    by_index: dict[str, list[str]] = {}
    for r in proj_rows:
        by_index.setdefault(r["idx"], []).append(r["result"])
    assert sorted(by_index) == ["1", "2", "3", "4", "5", "6"]
    assert sorted(by_index["3"]) == ["in_flight", "ok"]

    # ----- Assert: sample A wrote one clean dataset (no hold, 3 projections) ---
    async with db_pool.acquire() as conn:
        a_proj = await conn.fetch(
            "SELECT payload->>'result' AS result FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1 AND payload->>'action_name' = 'acquire_projection'",
            result_a.procedure_id,
        )
    assert [r["result"] for r in a_proj] == ["ok", "ok", "ok"]
