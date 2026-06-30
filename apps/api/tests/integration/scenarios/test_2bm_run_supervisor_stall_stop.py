"""RunSupervisor autonomously stops a stalled Run at APS 2-BM (Rule R act rung).

cluster: Staging
archetype: gate
bc_primary: Run
bc_touches: Access, Agent, Decision, Equipment, Recipe, Run, Safety, Subject

End-to-end proof of the stall act rung: a live observation channel stops arriving
(beam up, feeder heartbeat fresh) for the settle window, so the supervisor issues
StopRun (the controlled-exit terminal that keeps data to the cutoff), linking a
Stop Decision.

Everything is real Postgres: the Run is walked to Running through the real
start_run + projections, the per-Run expected_observation_interval_seconds flows
from RunStarted.effective_parameters through the real RunSummaryProjection +
list_runs drain, and the stop is the real bind_stop_run handler writing a real
RunStopped + Decision stream. The one injected fake is the observation
channel-feed (a hand-seeded InMemoryRunChannelLookup, the same seam the
auto-resume scenario uses for beam availability): the supervisor tick runs on a
FakeClock, while the Postgres observation table stamps recorded_at via DEFAULT
now() (real wall clock), so a frozen-clock test controls channel freshness +
heartbeat through the in-memory lookup. The PostgresRunChannelLookup read path
itself is covered by test_run_channel_lookup_postgres.py and
test_feed_heartbeats_postgres.py.

Rule R is two-stage anti-flap: a hysteresis streak to FLAG (set to 1 here so the
first stalled tick confirms), then the ACT settle window on top before StopRun.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportPrivateUsage=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.seed_run_supervisor import RUN_SUPERVISOR_AGENT_ID, seed_run_supervisor_agent
from cora.api._run_supervisor import ObservationRuleConfig, _supervise_tick
from cora.campaign.aggregates.campaign import CampaignIntent
from cora.decision.aggregates.decision import load_decision
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.beam_availability_lookup import BeamAvailabilityLookupResult
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.run._projections import register_run_projections
from cora.run.features.abort_run import bind as bind_abort_run
from cora.run.features.hold_run import bind as bind_hold_run
from cora.run.features.list_runs import bind as bind_list_runs
from cora.run.features.resume_run import bind as bind_resume_run
from cora.run.features.start_run import StartRun
from cora.run.features.start_run import bind as bind_start_run
from cora.run.features.stop_run import bind as bind_stop_run
from cora.run.features.truncate_run import bind as bind_truncate_run
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

_NOW = datetime(2026, 5, 18, 2, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000004671bb")

_STALL_CHANNEL = "projection_index"
_EXPECTED_INTERVAL = 10.0
_FEED_CEILING = 120.0

# Scenario tag: 467 (RunSupervisor stall -> stop).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000467501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000467a01")

_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000467a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000467a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000467a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000467a41")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000467b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000467b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000467b21")
_CLEARANCE_ID = UUID("01900000-0000-7000-8000-000000467f01")
_ESAF_TEMPLATE_ID = ClearanceTemplateId(clearance_template_stream_id("cora", "ESAF"))
_METHOD_ID = UUID("01900000-0000-7000-8000-000000467d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d467")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-000000467d11")
_PLAN_ID = UUID("01900000-0000-7000-8000-000000467d21")
_RUN_ID = UUID("01900000-0000-7000-8000-000000467f02")

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
    pi_actor_name="Proposal 2026-4671 PI",
    subject_id=_SUBJECT_ID,
    subject_name="porous sandstone core (Proposal 2026-4671, sample A, stall-stop)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="Proposal 2026-4671 beamtime (stall-stop)",
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
            "expected_observation_interval_seconds": {"type": "number", "minimum": 0},
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

_RULES_STALL = ObservationRuleConfig(
    quality_channel_name=None,
    stall_channel_name=_STALL_CHANNEL,
    stall_window_factor=3.0,
    stall_hysteresis_ticks=1,  # flag on the first stalled tick (the act settle is the anti-flap)
    feed_heartbeat_ceiling_seconds=_FEED_CEILING,
)


def _id_queue() -> list[UUID]:
    """Setup ids through start_run, then a generous pad for the supervisor ticks
    (drain correlations, the Decision id, the StopRun command correlation)."""
    e = uuid4
    return [
        *tomography_install_id_prefix(asset_ids=_TOMO_ASSETS),
        *beamtime_id_prefix(spec=_BEAMTIME),
        e(),  # mount_subject
        *recipe_ladder_id_prefix(spec=_RECIPE),
        _CLEARANCE_ID,
        e(),  # register
        e(),  # submit
        e(),  # start_review
        e(),  # append_step
        e(),  # approve
        e(),  # activate
        _RUN_ID,
        e(),  # RunStarted event
        *[e() for _ in range(300)],
    ]


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
    """Full beamtime through a started, projection-visible Run carrying an
    expected_observation_interval_seconds, gated by a real Active ESAF Clearance."""
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
            reason="stall-stop scenario setup",
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
    await bind_register_clearance(deps)(
        RegisterClearance(
            template_id=_ESAF_TEMPLATE_ID,
            facility_code="cora",
            title="Proposal 2026-4671 ESAF (porous sandstone tomography)",
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
            name="Proposal 2026-4671 sample A tomography (stall-stop)",
            plan_id=_PLAN_ID,
            subject_id=_SUBJECT_ID,
            override_parameters={
                "exposure_ms": 100,
                "n_projections": 1500,
                "angle_range_deg": 180.0,
                "expected_observation_interval_seconds": _EXPECTED_INTERVAL,
            },
            trigger_source="operator-manual; supervisor stall-stop scenario",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_run(db_pool)


async def _tick(
    deps: Kernel,
    channel_lookup: InMemoryRunChannelLookup,
    *,
    stall: set[UUID],
    stall_streak: dict[UUID, int],
    stall_act_settle: dict[UUID, int],
) -> None:
    """Drive one supervision pass with real list/abort/stop handlers and the
    stall act rung enabled; all non-stall rungs off."""
    await _supervise_tick(
        deps=deps,
        list_runs=bind_list_runs(deps),
        hold_run=bind_hold_run(deps),
        resume_run=bind_resume_run(deps),
        truncate_run=bind_truncate_run(deps),
        abort_run=bind_abort_run(deps),
        stop_run=bind_stop_run(deps),
        beam_lookup=_BeamOpen(),
        channel_lookup=channel_lookup,
        rules_config=_RULES_STALL,
        memory={},
        settle={},
        liveness=set(),
        truncate_settle={},
        quality=set(),
        stall=stall,
        stall_streak=stall_streak,
        feed_dead_warned=set(),
        quality_act_settle={},
        stall_act_settle=stall_act_settle,
        resume_enabled=False,
        resume_settle_ticks=1,
        liveness_ceiling_seconds=None,
        truncate_enabled=False,
        truncate_settle_ticks=3,
        quality_act_enabled=False,
        quality_settle_ticks=2,
        stall_act_enabled=True,
        stall_settle_ticks=2,
        advise_enabled=False,
    )


@pytest.mark.integration
async def test_supervisor_stops_run_after_observation_stall_settles(
    db_pool: asyncpg.Pool,
) -> None:
    """A live channel stalled (fresh heartbeat, zero arrivals) for the settle
    window -> the supervisor stops the Run, linking a Stop Decision; the Run
    reaches Stopped."""
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=_id_queue(),
        clearance_lookup=PostgresClearanceLookup(db_pool),
    )
    await _setup_running_run(deps, db_pool)

    lookup = InMemoryRunChannelLookup()
    lookup.register_heartbeat(run_id=_RUN_ID, recorded_at=_NOW)  # feeder alive, no data arrivals
    stall: set[UUID] = set()
    stall_streak: dict[UUID, int] = {}
    stall_act_settle: dict[UUID, int] = {}

    # Tick 1: confirmed stall (hysteresis 1), act settle (2) not met -> no stop yet.
    await _tick(
        deps, lookup, stall=stall, stall_streak=stall_streak, stall_act_settle=stall_act_settle
    )
    events, _ = await deps.event_store.load("Run", _RUN_ID)
    assert [e.event_type for e in events] == ["RunStarted"]
    assert stall == {_RUN_ID}
    assert stall_act_settle[_RUN_ID] == 1

    # Tick 2: still stalled, act settle met -> stop fires.
    await _tick(
        deps, lookup, stall=stall, stall_streak=stall_streak, stall_act_settle=stall_act_settle
    )
    events, _ = await deps.event_store.load("Run", _RUN_ID)
    assert [e.event_type for e in events] == ["RunStarted", "RunStopped"]
    stopped = next(e for e in events if e.event_type == "RunStopped")
    decision_id = stopped.payload["decided_by_decision_id"]
    assert decision_id is not None

    decision = await load_decision(deps.event_store, UUID(decision_id))
    assert decision is not None
    assert decision.context.value == "RunSupervision"
    assert decision.choice.value == "Stop"
    assert decision.decided_by == ActorId(RUN_SUPERVISOR_AGENT_ID)


@pytest.mark.integration
async def test_supervisor_does_not_stop_when_data_resumes_before_settle(
    db_pool: asyncpg.Pool,
) -> None:
    """Arrivals resume before the act settle window: the Run stays Running."""
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=_id_queue(),
        clearance_lookup=PostgresClearanceLookup(db_pool),
    )
    await _setup_running_run(deps, db_pool)

    lookup = InMemoryRunChannelLookup()
    lookup.register_heartbeat(run_id=_RUN_ID, recorded_at=_NOW)
    stall: set[UUID] = set()
    stall_streak: dict[UUID, int] = {}
    stall_act_settle: dict[UUID, int] = {}

    # Tick 1: stalled (zero arrivals) -> confirmed, act counter -> 1.
    await _tick(
        deps, lookup, stall=stall, stall_streak=stall_streak, stall_act_settle=stall_act_settle
    )
    assert stall_act_settle[_RUN_ID] == 1

    # Data resumes within the window before the act settle: arrival inside the
    # window clears the stall -> counter resets, no stop.
    lookup.register(
        run_id=_RUN_ID,
        channel_name=_STALL_CHANNEL,
        value=1.0,
        recorded_at=_NOW,
    )
    await _tick(
        deps, lookup, stall=stall, stall_streak=stall_streak, stall_act_settle=stall_act_settle
    )

    events, _ = await deps.event_store.load("Run", _RUN_ID)
    assert [e.event_type for e in events] == ["RunStarted"]
    assert _RUN_ID not in stall_act_settle
