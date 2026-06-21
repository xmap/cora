"""RunSupervisor autonomously resumes a beam-held Run at APS 2-BM.

cluster: Staging
archetype: gate
bc_primary: Run
bc_touches: Access, Agent, Decision, Equipment, Recipe, Run, Safety, Subject

End-to-end proof of the gated wind-up: the RunSupervisor holds a Run when
the beam drops, then RESUMES it once the full start-safety envelope is good
again (an Active Clearance still covers the scope and the beam is back),
re-checking the SAME `check_safety_envelope` a fresh `start_run` passes,
against the real PostgresClearanceLookup projection.

Two scenarios share the setup:

  - positive: beam returns AND the Clearance is still Active -> the
    supervisor resumes its own held Run (RunResumed carries the Decision
    link; a Decision(choice=Resume) is recorded; the Run is Running again).
  - negative: the covering Clearance EXPIRES during the hold -> the
    envelope re-check fails, so the supervisor leaves the Run Held (no
    RunResumed, no Resume Decision). This is the fail-safe heart of the
    design: resume never re-enters a state a fresh start would refuse.

The supervisor's periodic loop is driven white-box via `_supervise_tick`
(the same pattern as the unit tests), against a real Postgres kernel and
the real list/hold/resume handlers; beam availability is the one injected
fake (down on the first tick, up on the second).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportPrivateUsage=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.seed_run_supervisor import RUN_SUPERVISOR_AGENT_ID, seed_run_supervisor_agent
from cora.api._run_supervisor import _MEM_HELD, ObservationRuleConfig, _supervise_tick
from cora.campaign.aggregates.campaign import CampaignIntent
from cora.decision.aggregates.decision import load_decision
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.beam_availability_lookup import BeamAvailabilityLookupResult
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.run._projections import register_run_projections
from cora.run.features.hold_run import bind as bind_hold_run
from cora.run.features.list_runs import bind as bind_list_runs
from cora.run.features.resume_run import bind as bind_resume_run
from cora.run.features.start_run import StartRun
from cora.run.features.start_run import bind as bind_start_run
from cora.run.ports import InMemoryRunChannelLookup
from cora.safety._projections import register_safety_projections
from cora.safety.adapters import PostgresClearanceLookup
from cora.safety.aggregates.clearance import SubjectBinding
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.features.activate_clearance import ActivateClearance
from cora.safety.features.activate_clearance import bind as bind_activate_clearance
from cora.safety.features.append_clearance_review_step import AppendClearanceReviewStep
from cora.safety.features.append_clearance_review_step import bind as bind_append_review_step
from cora.safety.features.approve_clearance import ApproveClearance
from cora.safety.features.approve_clearance import bind as bind_approve_clearance
from cora.safety.features.expire_clearance import ExpireClearance
from cora.safety.features.expire_clearance import bind as bind_expire_clearance
from cora.safety.features.register_clearance import RegisterClearance
from cora.safety.features.register_clearance import bind as bind_register_clearance
from cora.safety.features.start_clearance_review import StartClearanceReview
from cora.safety.features.start_clearance_review import bind as bind_start_review
from cora.safety.features.submit_clearance import SubmitClearance
from cora.safety.features.submit_clearance import bind as bind_submit_clearance
from cora.shared.identity import ActorId
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.mount_subject import bind as bind_mount_subject
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._beamtime_fixture import (
    BeamtimeSpec,
    beamtime_id_prefix,
    open_beamtime,
)
from tests.integration.scenarios._facility_fixture import (
    BEAMLINE_SCIENTIST_ACTOR_ID,
    operator_for,
)
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

_NOW = datetime(2026, 5, 18, 2, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000004621bb")

# Scenario tag: 462 (RunSupervisor autonomous resume).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000462501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000462a01")

_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000462a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000462a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000462a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000462a41")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000462b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000462b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000462b21")
_CLEARANCE_ID = UUID("01900000-0000-7000-8000-000000462f01")
_ESAF_TEMPLATE_ID = ClearanceTemplateId(clearance_template_stream_id("cora", "ESAF"))
_METHOD_ID = UUID("01900000-0000-7000-8000-000000462d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d462")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-000000462d11")
_PLAN_ID = UUID("01900000-0000-7000-8000-000000462d21")
_RUN_ID = UUID("01900000-0000-7000-8000-000000462f02")

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

_BEAMTIME = BeamtimeSpec(
    pi_actor_id=_PI_ACTOR_ID,
    pi_actor_name="Proposal 2026-1234 PI",
    subject_id=_SUBJECT_ID,
    subject_name="porous sandstone core (Proposal 2026-1234, sample A, auto-resume)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="Proposal 2026-1234 beamtime (auto-resume)",
    campaign_intent=CampaignIntent.COORDINATION,
    campaign_tags=frozenset({"proposal", "tomography", "porous_media"}),
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
    plan_name="2BM_porous_media_tomography_plan",
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
    """Exact setup ids through start_run, then a generous pad: the supervisor
    allocates an unpredictable number of ids per tick (drain correlation ids,
    Decision ids, command correlation + event ids), so over-provide rather
    than count every one."""
    e = uuid4
    return [
        *tomography_install_id_prefix(asset_ids=_TOMO_ASSETS),
        *beamtime_id_prefix(spec=_BEAMTIME),
        e(),  # mount_subject
        *recipe_ladder_id_prefix(spec=_RECIPE),
        # register_clearance + walk to Active (clearance id + 6 events)
        _CLEARANCE_ID,
        e(),  # register
        e(),  # submit
        e(),  # start_review
        e(),  # append_step
        e(),  # approve
        e(),  # activate
        # start_run
        _RUN_ID,
        e(),  # RunStarted event
        # pad for the supervisor ticks + the negative path's expire_clearance
        *[e() for _ in range(300)],
    ]


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


async def _drain_safety(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_safety_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _drain_run(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_run_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _setup_running_run(deps: Kernel, db_pool: asyncpg.Pool) -> None:
    """Full beamtime through a started, projection-visible Run, gated by a real
    Active ESAF Clearance bound to the Subject."""
    deps.clearance_template_lookup.register(  # type: ignore[attr-defined]
        template_id=_ESAF_TEMPLATE_ID,
        facility_code="cora",
        code="ESAF",
        status="Active",
        version=1,
    )
    await seed_run_supervisor_agent(deps)

    await install_and_activate_tomography_assets(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        asset_ids=_TOMO_ASSETS,
    )
    await open_beamtime(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        spec=_BEAMTIME,
    )
    await bind_mount_subject(deps)(
        MountSubject(
            subject_id=_SUBJECT_ID,
            asset_id=_ASSET_AEROTECH_ABRS_ID,
            reason="auto-resume scenario setup",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_recipe_ladder(
        deps,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        spec=_RECIPE,
    )

    # Walk an ESAF Clearance (Subject-bound) to Active so start_run passes
    # AND the supervisor's envelope re-check has a real Active row to read.
    await bind_register_clearance(deps)(
        RegisterClearance(
            template_id=_ESAF_TEMPLATE_ID,
            facility_code="cora",
            title="Proposal 2026-1234 ESAF (porous sandstone tomography)",
            bindings=frozenset({SubjectBinding(subject_id=_SUBJECT_ID)}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_submit_clearance(deps)(
        SubmitClearance(clearance_id=_CLEARANCE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start_review(deps)(
        StartClearanceReview(clearance_id=_CLEARANCE_ID, first_reviewer_role="BeamlineScientist"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_append_review_step(deps)(
        AppendClearanceReviewStep(
            clearance_id=_CLEARANCE_ID,
            step_index=0,
            role="BeamlineScientist",
            actor_id=BEAMLINE_SCIENTIST_ACTOR_ID,
            decision="Approved",
            decided_at=_NOW,
            notes="LGTM",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_approve_clearance(deps)(
        ApproveClearance(clearance_id=_CLEARANCE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_activate_clearance(deps)(
        ActivateClearance(clearance_id=_CLEARANCE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_safety(db_pool)

    await bind_start_run(deps)(
        StartRun(
            name="Proposal 2026-1234 sample A tomography (auto-resume)",
            plan_id=_PLAN_ID,
            subject_id=_SUBJECT_ID,
            override_parameters={
                "exposure_ms": 100,
                "n_projections": 1500,
                "angle_range_deg": 180.0,
            },
            trigger_source="operator-manual; supervisor auto-resume scenario",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_run(db_pool)


async def _run_event_types(deps: Kernel) -> list[str]:
    events, _ = await deps.event_store.load("Run", _RUN_ID)
    return [e.event_type for e in events]


@pytest.mark.integration
async def test_supervisor_auto_resumes_when_envelope_safe(db_pool: asyncpg.Pool) -> None:
    """Beam drops -> supervisor holds; beam returns + Clearance still Active ->
    supervisor resumes its own held Run, linking a Resume Decision."""
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=_id_queue(),
        clearance_lookup=PostgresClearanceLookup(db_pool),
    )
    await _setup_running_run(deps, db_pool)

    list_runs = bind_list_runs(deps)
    hold_run = bind_hold_run(deps)
    resume_run = bind_resume_run(deps)
    memory: dict[UUID, str] = {}
    settle: dict[UUID, int] = {}

    # Tick 1: beam DOWN -> hold.
    await _supervise_tick(
        deps=deps,
        list_runs=list_runs,
        hold_run=hold_run,
        resume_run=resume_run,
        beam_lookup=_BeamDown(),
        memory=memory,
        settle=settle,
        liveness=set(),
        channel_lookup=InMemoryRunChannelLookup(),
        rules_config=_RULES_OFF,
        quality=set(),
        stall=set(),
        stall_streak={},
        feed_dead_warned=set(),
        liveness_ceiling_seconds=None,
        resume_enabled=True,
        resume_settle_ticks=1,
    )
    assert memory[_RUN_ID] == _MEM_HELD
    assert await _run_event_types(deps) == ["RunStarted", "RunHeld"]
    await _drain_run(db_pool)

    # Tick 2: beam UP + Clearance still Active -> resume (settle window = 1).
    await _supervise_tick(
        deps=deps,
        list_runs=list_runs,
        hold_run=hold_run,
        resume_run=resume_run,
        beam_lookup=_BeamOpen(),
        memory=memory,
        settle=settle,
        liveness=set(),
        channel_lookup=InMemoryRunChannelLookup(),
        rules_config=_RULES_OFF,
        quality=set(),
        stall=set(),
        stall_streak={},
        feed_dead_warned=set(),
        liveness_ceiling_seconds=None,
        resume_enabled=True,
        resume_settle_ticks=1,
    )

    events, _ = await deps.event_store.load("Run", _RUN_ID)
    assert [e.event_type for e in events] == ["RunStarted", "RunHeld", "RunResumed"]
    resumed = next(e for e in events if e.event_type == "RunResumed")
    decision_id = resumed.payload["decided_by_decision_id"]
    assert decision_id is not None

    decision = await load_decision(deps.event_store, UUID(decision_id))
    assert decision is not None
    assert decision.context.value == "RunSupervision"
    assert decision.choice.value == "Resume"
    assert decision.decided_by == ActorId(RUN_SUPERVISOR_AGENT_ID)


@pytest.mark.integration
async def test_supervisor_stays_held_when_clearance_expired(db_pool: asyncpg.Pool) -> None:
    """Beam returns but the covering Clearance EXPIRED during the hold: the
    envelope re-check fails, so the supervisor does NOT resume (fail-safe)."""
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=_id_queue(),
        clearance_lookup=PostgresClearanceLookup(db_pool),
    )
    await _setup_running_run(deps, db_pool)

    list_runs = bind_list_runs(deps)
    hold_run = bind_hold_run(deps)
    resume_run = bind_resume_run(deps)
    memory: dict[UUID, str] = {}
    settle: dict[UUID, int] = {}

    # Tick 1: beam DOWN -> hold.
    await _supervise_tick(
        deps=deps,
        list_runs=list_runs,
        hold_run=hold_run,
        resume_run=resume_run,
        beam_lookup=_BeamDown(),
        memory=memory,
        settle=settle,
        liveness=set(),
        channel_lookup=InMemoryRunChannelLookup(),
        rules_config=_RULES_OFF,
        quality=set(),
        stall=set(),
        stall_streak={},
        feed_dead_warned=set(),
        liveness_ceiling_seconds=None,
        resume_enabled=True,
        resume_settle_ticks=1,
    )
    assert memory[_RUN_ID] == _MEM_HELD
    await _drain_run(db_pool)

    # The ESAF window elapses while the Run is held: the Clearance expires.
    await bind_expire_clearance(deps)(
        ExpireClearance(clearance_id=_CLEARANCE_ID, reason="ESAF validity window elapsed mid-hold"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_safety(db_pool)

    # Tick 2: beam UP but no Active Clearance covers the scope -> stay Held.
    await _supervise_tick(
        deps=deps,
        list_runs=list_runs,
        hold_run=hold_run,
        resume_run=resume_run,
        beam_lookup=_BeamOpen(),
        memory=memory,
        settle=settle,
        liveness=set(),
        channel_lookup=InMemoryRunChannelLookup(),
        rules_config=_RULES_OFF,
        quality=set(),
        stall=set(),
        stall_streak={},
        feed_dead_warned=set(),
        liveness_ceiling_seconds=None,
        resume_enabled=True,
        resume_settle_ticks=1,
    )

    assert memory[_RUN_ID] == _MEM_HELD
    event_types = await _run_event_types(deps)
    assert "RunResumed" not in event_types
    assert event_types == ["RunStarted", "RunHeld"]
