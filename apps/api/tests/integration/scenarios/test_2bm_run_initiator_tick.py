"""RunInitiator selection tick: the autonomous loop's brain at APS 2-BM.

cluster: Staging
archetype: gate
bc_primary: Run
bc_touches: Access, Agent, Decision, Equipment, Recipe, Run, Subject

The autonomous run-start selection for the 19-BM autonomy axis, on the 2-BM
substrate. The RunInitiator tick is the selection brain of the future standing
loop: capped by max-in-flight, it starts the next ready (Mounted) Subject(s) for
a supplied recipe Plan via the `initiate_run` seam, dedup'd by in-process memory.
Driven white-box here exactly as `_supervise_tick` is in the RunSupervisor
scenario; the asyncio daemon, settings, and app wiring come later (the daemon).

One-stage CT serializes (one rotary stage), so the cap is the mechanism that
keeps one scan in flight; the in-process `started` set plus the Running
subject-id exclusion together avoid a double-start across the projection-lag
seam (list_runs reads a projection that lags a just-issued start).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportPrivateUsage=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.seed_run_initiator import RUN_INITIATOR_AGENT_ID, seed_run_initiator_agent
from cora.api._run_initiator import initiate_tick
from cora.campaign.aggregates.campaign import CampaignIntent
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.run._projections import register_run_projections
from cora.run.features.list_runs import bind as bind_list_runs
from cora.subject._projections import register_subject_projections
from cora.subject.features.list_subjects import bind as bind_list_subjects
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.mount_subject import bind as bind_mount_subject
from cora.subject.features.register_subject import RegisterSubject
from cora.subject.features.register_subject import bind as bind_register_subject
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
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000004641bb")

# Scenario tag: 464 (RunInitiator selection tick).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000464501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000464a01")

_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000464a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000464a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000464a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000464a41")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000464b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000464b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000464b21")
_METHOD_ID = UUID("01900000-0000-7000-8000-000000464d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d464")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-000000464d11")
_PLAN_ID = UUID("01900000-0000-7000-8000-000000464d21")

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
    pi_actor_name="Proposal 2026-4641 PI",
    subject_id=_SUBJECT_ID,
    subject_name="porous sandstone core A (Proposal 2026-4641, tick scenario)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="Proposal 2026-4641 beamtime (tick scenario)",
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


def _id_queue(*, with_subjects: bool) -> list[UUID]:
    """FixedIdGenerator queue. Operation order must match _setup exactly:
    install assets, open beamtime, [mount s1, register s2, mount s2], recipe
    ladder, then a pad for the tick's initiate_run calls + drain correlations."""
    e = uuid4
    queue = [
        *tomography_install_id_prefix(asset_ids=_TOMO_ASSETS),
        *beamtime_id_prefix(spec=_BEAMTIME),
    ]
    if with_subjects:
        queue += [
            e(),  # mount subject 1 (SubjectMounted event)
            e(),  # register subject 2 (aggregate id)
            e(),  # register subject 2 (SubjectRegistered event)
            e(),  # mount subject 2 (SubjectMounted event)
        ]
    queue += [
        *recipe_ladder_id_prefix(spec=_RECIPE),
        *[e() for _ in range(60)],  # tick: initiate_run + drains, generous headroom
    ]
    return queue


async def _drain_run(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_run_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _drain_subjects(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_subject_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _setup(
    deps: Kernel,
    db_pool: asyncpg.Pool,
    *,
    with_subjects: bool,
    seed_agent: bool = True,
) -> UUID | None:
    """Install the 2-BM tomography assets + a ready Plan; optionally mount two
    Subjects so the tick has candidates. Returns the second Subject id (or None
    when no subjects were mounted)."""
    if seed_agent:
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
    subject2_id: UUID | None = None
    if with_subjects:
        await bind_mount_subject(deps)(
            MountSubject(
                subject_id=_SUBJECT_ID,
                asset_id=_ASSET_AEROTECH_ABRS_ID,
                reason="tick scenario: mount sample A",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        subject2_id = await bind_register_subject(deps)(
            RegisterSubject(name="porous sandstone core B (Proposal 2026-4641, tick scenario)"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        await bind_mount_subject(deps)(
            MountSubject(
                subject_id=subject2_id,
                asset_id=_ASSET_AEROTECH_ABRS_ID,
                reason="tick scenario: mount sample B",
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
    return subject2_id


async def _run_subject_id(deps: Kernel, run_id: UUID) -> UUID | None:
    events, _ = await deps.event_store.load("Run", run_id)
    started = next(e for e in events if e.event_type == "RunStarted")
    raw = started.payload["subject_id"]
    return UUID(raw) if raw is not None else None


@pytest.mark.integration
async def test_initiator_tick_starts_one_ready_subject_under_cap(db_pool: asyncpg.Pool) -> None:
    """max_in_flight=1, nothing started yet: the tick starts exactly one ready
    Subject and the RunStarted records the agent principal + trigger_source."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue(with_subjects=True))
    await _setup(deps, db_pool, with_subjects=True)
    await _drain_subjects(db_pool)

    started: set[UUID] = set()
    run_ids = await initiate_tick(
        deps=deps,
        list_runs=bind_list_runs(deps),
        list_subjects=bind_list_subjects(deps),
        plan_id=_PLAN_ID,
        max_in_flight=1,
        started=started,
    )

    assert len(run_ids) == 1
    events, _ = await deps.event_store.load("Run", run_ids[0])
    assert [e.event_type for e in events] == ["RunStarted"]
    assert events[0].principal_id == RUN_INITIATOR_AGENT_ID
    assert events[0].payload["trigger_source"] == "RunInitiator"
    # oldest-mounted-first: subject A (registered first) is the one started.
    assert started == {_SUBJECT_ID}
    assert await _run_subject_id(deps, run_ids[0]) == _SUBJECT_ID


@pytest.mark.integration
async def test_initiator_tick_respects_max_in_flight(db_pool: asyncpg.Pool) -> None:
    """With one Run already Running and max_in_flight=1, a second tick starts
    nothing even though a second ready Subject exists (the cap, not exhaustion)."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue(with_subjects=True))
    await _setup(deps, db_pool, with_subjects=True)
    await _drain_subjects(db_pool)

    started: set[UUID] = set()
    first = await initiate_tick(
        deps=deps,
        list_runs=bind_list_runs(deps),
        list_subjects=bind_list_subjects(deps),
        plan_id=_PLAN_ID,
        max_in_flight=1,
        started=started,
    )
    assert len(first) == 1
    await _drain_run(db_pool)  # make the started Run visible as Running

    second = await initiate_tick(
        deps=deps,
        list_runs=bind_list_runs(deps),
        list_subjects=bind_list_subjects(deps),
        plan_id=_PLAN_ID,
        max_in_flight=1,
        started=started,
    )
    assert second == []


@pytest.mark.integration
async def test_initiator_tick_dedups_already_started_subject(db_pool: asyncpg.Pool) -> None:
    """With subject A already in the started memory and max_in_flight=2, the tick
    does NOT restart A and starts the other ready Subject B instead."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue(with_subjects=True))
    subject2_id = await _setup(deps, db_pool, with_subjects=True)
    assert subject2_id is not None
    await _drain_subjects(db_pool)

    started: set[UUID] = {_SUBJECT_ID}
    run_ids = await initiate_tick(
        deps=deps,
        list_runs=bind_list_runs(deps),
        list_subjects=bind_list_subjects(deps),
        plan_id=_PLAN_ID,
        max_in_flight=2,
        started=started,
    )

    assert len(run_ids) == 1
    assert await _run_subject_id(deps, run_ids[0]) == subject2_id
    assert started == {_SUBJECT_ID, subject2_id}


@pytest.mark.integration
async def test_initiator_tick_starts_multiple_under_higher_cap(db_pool: asyncpg.Pool) -> None:
    """max_in_flight=2 with two ready Subjects and an empty started set: the tick
    fills both slots in one pass (the multi-slot loop), one Run per Subject."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue(with_subjects=True))
    subject2_id = await _setup(deps, db_pool, with_subjects=True)
    assert subject2_id is not None
    await _drain_subjects(db_pool)

    started: set[UUID] = set()
    run_ids = await initiate_tick(
        deps=deps,
        list_runs=bind_list_runs(deps),
        list_subjects=bind_list_subjects(deps),
        plan_id=_PLAN_ID,
        max_in_flight=2,
        started=started,
    )

    assert len(run_ids) == 2
    started_subjects = {await _run_subject_id(deps, run_id) for run_id in run_ids}
    assert started_subjects == {_SUBJECT_ID, subject2_id}
    assert started == {_SUBJECT_ID, subject2_id}


@pytest.mark.integration
async def test_initiator_tick_starts_nothing_when_no_subject_ready(db_pool: asyncpg.Pool) -> None:
    """No Subject is Mounted (only Received): the tick stands down, starts nothing."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue(with_subjects=False))
    await _setup(deps, db_pool, with_subjects=False)
    await _drain_subjects(db_pool)

    started: set[UUID] = set()
    run_ids = await initiate_tick(
        deps=deps,
        list_runs=bind_list_runs(deps),
        list_subjects=bind_list_subjects(deps),
        plan_id=_PLAN_ID,
        max_in_flight=1,
        started=started,
    )
    assert run_ids == []
    assert started == set()


@pytest.mark.integration
async def test_initiator_tick_starts_nothing_when_agent_absent(db_pool: asyncpg.Pool) -> None:
    """With the RunInitiator Actor absent, the tick stands down and starts nothing,
    even with ready Subjects: autonomy requires the seeded principal."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue(with_subjects=True))
    await _setup(deps, db_pool, with_subjects=True, seed_agent=False)
    await _drain_subjects(db_pool)

    started: set[UUID] = set()
    run_ids = await initiate_tick(
        deps=deps,
        list_runs=bind_list_runs(deps),
        list_subjects=bind_list_subjects(deps),
        plan_id=_PLAN_ID,
        max_in_flight=1,
        started=started,
    )
    assert run_ids == []
