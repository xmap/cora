"""RunInitiator autonomously starts a Run at APS 2-BM (the run-start seam).

cluster: Staging
archetype: gate
bc_primary: Run
bc_touches: Access, Agent, Decision, Equipment, Recipe, Run, Safety, Subject

Slice 1 of the 19-BM autonomy axis, proven on the 2-BM substrate (the mechanism
is beamline-agnostic; 19-BM is pre-build and has no installed-asset test harness).
The RunInitiator agent starts a Run through the SAME authorized path a human
operator uses: it records one Decision(context=RunInitiation, choice=Start) and
issues StartRun as the agent principal, attributed via trigger_source and linked
via decided_by_decision_id.

Four cases pin the seam:

  - attribution: under AllowAllAuthorize the agent starts an eligible Run; the
    RunStarted event records the AGENT as principal_id, trigger_source, and a
    Decision link, and the Decision records the agent as decided_by.
  - deny: under real TrustAuthorize, an agent NOT granted StartRun is denied; the
    start is a logged no-op (no Run created), no bypass.
  - allow: under real TrustAuthorize, an agent granted StartRun starts the Run.
  - safety-gate: with the real Postgres clearance lookup and NO Active clearance,
    the start is refused by the safety envelope regardless of actor kind, so agent
    initiation never weakens the gate.

The runtime entry point `initiate_run` is driven white-box (the same pattern the
RunSupervisor scenario uses for `_supervise_tick`), against a real Postgres kernel
and the real start_run handler.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportPrivateUsage=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.seed_run_initiator import RUN_INITIATOR_AGENT_ID, seed_run_initiator_agent
from cora.api._run_initiator import initiate_run
from cora.campaign.aggregates.campaign import CampaignIntent
from cora.decision.aggregates.decision import load_decision
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.run._projections import register_run_projections
from cora.run.aggregates.run import RunRequiresActiveClearanceError
from cora.run.features.list_runs import ListRuns
from cora.run.features.list_runs import bind as bind_list_runs
from cora.safety.adapters import PostgresClearanceLookup
from cora.shared.identity import ActorId
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.mount_subject import bind as bind_mount_subject
from cora.trust.authorize import TrustAuthorize
from tests._authz import seed_policy
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._beamtime_fixture import (
    BeamtimeSpec,
    beamtime_id_prefix,
    open_beamtime,
)
from tests.integration.scenarios._facility_fixture import operator_for
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
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000004631bb")
_POLICY_ID = UUID("01900000-0000-7000-8000-0000004631c0")

# Scenario tag: 463 (RunInitiator autonomous start).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000463501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000463a01")

_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000463a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000463a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000463a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000463a41")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000463b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000463b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000463b21")
_METHOD_ID = UUID("01900000-0000-7000-8000-000000463d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d463")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-000000463d11")
_PLAN_ID = UUID("01900000-0000-7000-8000-000000463d21")

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
    pi_actor_name="Proposal 2026-4631 PI",
    subject_id=_SUBJECT_ID,
    subject_name="porous sandstone core (Proposal 2026-4631, sample A, agent-start)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="Proposal 2026-4631 beamtime (agent-start)",
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

_OVERRIDE_PARAMETERS = {"exposure_ms": 100, "n_projections": 1500, "angle_range_deg": 180.0}


def _setup_id_queue() -> list[UUID]:
    """Setup ids through the recipe ladder, then a generous pad for the
    initiate_run call (Decision id + correlations + run id + RunStarted event)."""
    e = uuid4
    return [
        *tomography_install_id_prefix(asset_ids=_TOMO_ASSETS),
        *beamtime_id_prefix(spec=_BEAMTIME),
        e(),  # mount_subject
        *recipe_ladder_id_prefix(spec=_RECIPE),
        *[e() for _ in range(50)],  # initiate_run + headroom
    ]


async def _drain_run(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_run_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _setup_ready_to_start(deps: Kernel, db_pool: asyncpg.Pool) -> None:
    """Beamtime through a Mounted Subject and a ready Plan, but NOT started:
    the agent does the start. Clearance coverage is the deps' clearance_lookup
    (AlwaysCovered by default; the safety-gate test injects the real one)."""
    await seed_run_initiator_agent(deps)
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
            reason="agent-start scenario setup",
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


@pytest.mark.integration
async def test_run_initiator_starts_eligible_run_records_agent_principal(
    db_pool: asyncpg.Pool,
) -> None:
    """The agent starts an eligible Run; RunStarted records the agent principal +
    trigger_source + Decision link, and the Decision records the agent."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_setup_id_queue())
    await _setup_ready_to_start(deps, db_pool)

    run_id = await initiate_run(
        deps,
        plan_id=_PLAN_ID,
        subject_id=_SUBJECT_ID,
        name="Proposal 2026-4631 sample A tomography (agent-start)",
        override_parameters=_OVERRIDE_PARAMETERS,
    )
    assert run_id is not None

    events, _ = await deps.event_store.load("Run", run_id)
    assert [e.event_type for e in events] == ["RunStarted"]
    started = events[0]
    assert started.principal_id == RUN_INITIATOR_AGENT_ID
    assert started.payload["trigger_source"] == "RunInitiator"
    decision_id = started.payload["decided_by_decision_id"]
    assert decision_id is not None

    decision = await load_decision(deps.event_store, UUID(decision_id))
    assert decision is not None
    assert decision.context.value == "RunInitiation"
    assert decision.choice.value == "Start"
    assert decision.rule is not None
    assert decision.rule.value == "agent:RunInitiator:v1"
    assert decision.decided_by == ActorId(RUN_INITIATOR_AGENT_ID)


@pytest.mark.integration
async def test_run_initiator_without_start_grant_is_denied_no_run(
    db_pool: asyncpg.Pool,
) -> None:
    """Real TrustAuthorize: an agent not granted StartRun is denied; the start is a
    logged no-op (no Run created), no bypass of the authorized path."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(20)])
    await seed_run_initiator_agent(deps)
    store = deps.event_store
    await seed_policy(
        store,
        policy_id=_POLICY_ID,
        permitted_principal_ids=[RUN_INITIATOR_AGENT_ID],
        permitted_commands=["ListRuns"],  # deliberately NOT StartRun
    )
    gated = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[uuid4() for _ in range(20)],
        event_store=store,
        authz=TrustAuthorize(store, policy_id=_POLICY_ID),
    )

    result = await initiate_run(
        gated,
        plan_id=uuid4(),
        subject_id=None,
        name="denied agent start",
        override_parameters={},
    )
    assert result is None

    await _drain_run(db_pool)
    audit = build_postgres_deps(db_pool, now=_NOW, ids=[], event_store=store)
    page = await bind_list_runs(audit)(
        ListRuns(status="Running"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []


@pytest.mark.integration
async def test_run_initiator_with_start_grant_starts_run(db_pool: asyncpg.Pool) -> None:
    """Real TrustAuthorize: an agent granted StartRun starts the Run through the
    same authorized path a human uses."""
    setup_deps = build_postgres_deps(db_pool, now=_NOW, ids=_setup_id_queue())
    await _setup_ready_to_start(setup_deps, db_pool)
    store = setup_deps.event_store
    await seed_policy(
        store,
        policy_id=_POLICY_ID,
        permitted_principal_ids=[RUN_INITIATOR_AGENT_ID],
        permitted_commands=["StartRun"],
    )
    gated = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[uuid4() for _ in range(50)],
        event_store=store,
        authz=TrustAuthorize(store, policy_id=_POLICY_ID),
    )

    run_id = await initiate_run(
        gated,
        plan_id=_PLAN_ID,
        subject_id=_SUBJECT_ID,
        name="Proposal 2026-4631 sample A tomography (granted agent-start)",
        override_parameters=_OVERRIDE_PARAMETERS,
    )
    assert run_id is not None

    events, _ = await store.load("Run", run_id)
    assert [e.event_type for e in events] == ["RunStarted"]
    assert events[0].principal_id == RUN_INITIATOR_AGENT_ID


@pytest.mark.integration
async def test_run_initiator_without_active_clearance_refused(db_pool: asyncpg.Pool) -> None:
    """The agent start is refused by the safety envelope when no Active clearance
    covers the scope: agent initiation does not weaken the start-safety gate."""
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=_setup_id_queue(),
        clearance_lookup=PostgresClearanceLookup(db_pool),
    )
    await _setup_ready_to_start(deps, db_pool)

    with pytest.raises(RunRequiresActiveClearanceError):
        await initiate_run(
            deps,
            plan_id=_PLAN_ID,
            subject_id=_SUBJECT_ID,
            name="agent start without clearance",
            override_parameters=_OVERRIDE_PARAMETERS,
        )

    await _drain_run(db_pool)
    page = await bind_list_runs(deps)(
        ListRuns(status="Running"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
