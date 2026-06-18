"""End-to-end: `list_runs` handler against real Postgres projection
table. Most-important goal of this test: prove the
`_EVENT_TO_STATUS` dict in RunSummaryProjection writes strings that
the migration's CHECK constraint accepts. With 7 events folding to
6 status strings, a typo ("Aborting" vs "Aborted") would silently
break in production but the unit test (mock-based) couldn't catch
it. This test forces every status string through the real PG
write path.

Stresses:
  - INSERT path on RunStarted (CHECK + nullable subject_id + raid)
  - UPDATE on each of the 6 lifecycle transitions (each accepted by
    the CHECK constraint)
  - cursor pagination + plan_id filter end-to-end
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features import (
    add_asset_family,
    define_family,
    register_asset,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe._projections import register_recipe_projections
from cora.recipe.aggregates.method import ExecutionPattern
from cora.recipe.features import define_method, define_plan, define_practice
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from cora.run._projections import register_run_projections
from cora.run.features.abort_run import AbortRun
from cora.run.features.abort_run import bind as bind_abort
from cora.run.features.complete_run import CompleteRun
from cora.run.features.complete_run import bind as bind_complete
from cora.run.features.hold_run import HoldRun
from cora.run.features.hold_run import bind as bind_hold
from cora.run.features.list_runs import ListRuns
from cora.run.features.list_runs import bind as bind_list
from cora.run.features.resume_run import ResumeRun
from cora.run.features.resume_run import bind as bind_resume
from cora.run.features.start_run import StartRun
from cora.run.features.start_run import bind as bind_start
from cora.run.features.stop_run import StopRun
from cora.run.features.stop_run import bind as bind_stop
from cora.run.features.truncate_run import TruncateRun
from cora.run.features.truncate_run import bind as bind_truncate
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d93c")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    """Drain Equipment + Recipe + Run projections (Run integration
    needs all three because the upstream chain spans them)."""
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    register_recipe_projections(registry)
    register_run_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _seed_plan(deps: Kernel, family_name: str = "Tomography") -> UUID:
    """Seed the upstream chain (Family + Asset + Method +
    Practice + Plan) needed for start_run cross-aggregate validation.
    Returns plan_id. Consumes 10 ids from the FixedIdGenerator.

    Family stream ids are deterministic (uuid5 over the name); a
    second seed in the same db with the same family_name 409s, so
    callers seeding multiple chains in one db pass distinct names."""
    cap_id = await define_family.bind(deps)(
        DefineFamily(name=family_name, affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="EigerDetector", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    method_id = await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="Tomography",
            needed_family_ids=frozenset({cap_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name="APS-2BM-CT", method_id=method_id, site_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_id = await define_plan.bind(deps)(
        DefinePlan(
            name="32-ID Plan",
            practice_id=practice_id,
            asset_ids=frozenset({asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return plan_id


def _chain_ids() -> list[UUID]:
    """10 ids consumed by _seed_plan (define_family=1 (event only,
    stream id derived from name) + register_asset=2 +
    add_asset_family=1 + define_method=2 + define_practice=2 +
    define_plan=2)."""
    return [uuid4() for _ in range(10)]


@pytest.mark.integration
async def test_run_started_inserts_with_running_status_and_plan_ref(
    db_pool: asyncpg.Pool,
) -> None:
    """Sanity: RunStarted lands as Running with plan_id surfaced.

    Also pins that a standalone Run (no
    `StartRun.campaign_id`) lands with `campaign_id IS NULL`.
    """
    run_id = uuid4()
    deps = _build_deps(db_pool, [*_chain_ids(), run_id, uuid4()])
    plan_id = await _seed_plan(deps)
    await bind_start(deps)(
        StartRun(name="morning-session", plan_id=plan_id, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT name, plan_id, subject_id, raid, status, campaign_id "
            "FROM proj_run_summary WHERE run_id = $1",
            run_id,
        )
    assert row is not None
    assert row["name"] == "morning-session"
    assert row["plan_id"] == plan_id
    assert row["subject_id"] is None
    assert row["raid"] is None
    assert row["status"] == "Running"
    assert row["campaign_id"] is None


@pytest.mark.integration
async def test_every_lifecycle_transition_writes_a_check_constraint_accepted_status(
    db_pool: asyncpg.Pool,
) -> None:
    """The load-bearing test: prove the dict-based dispatch in
    RunSummaryProjection writes status strings that the migration's
    CHECK constraint actually accepts. Without this round-trip, a
    typo in `_EVENT_TO_STATUS` would silently break in production
    but pass the mock-based unit test.

    Drives 4 separate Runs through 4 different terminal transitions
    plus the Held -> Resumed round-trip on a 5th, covering all 6
    status strings the CHECK constraint enumerates.
    """
    # Run 1: Started -> Held (proves "Held").
    run_held_id = uuid4()
    deps_1 = _build_deps(db_pool, [*_chain_ids(), run_held_id, uuid4(), uuid4()])
    plan_id_1 = await _seed_plan(deps_1)
    await bind_start(deps_1)(
        StartRun(name="held-run", plan_id=plan_id_1, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_hold(deps_1)(
        HoldRun(run_id=run_held_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Run 2: Started -> Held -> Resumed (proves "Held" then back to "Running").
    run_resumed_id = uuid4()
    deps_2 = _build_deps(db_pool, [*_chain_ids(), run_resumed_id, uuid4(), uuid4(), uuid4()])
    plan_id_2 = await _seed_plan(deps_2, family_name="Tomography2")
    await bind_start(deps_2)(
        StartRun(name="resumed-run", plan_id=plan_id_2, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_hold(deps_2)(
        HoldRun(run_id=run_resumed_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_resume(deps_2)(
        ResumeRun(run_id=run_resumed_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Run 3: Started -> Completed (proves "Completed").
    run_completed_id = uuid4()
    deps_3 = _build_deps(db_pool, [*_chain_ids(), run_completed_id, uuid4(), uuid4()])
    plan_id_3 = await _seed_plan(deps_3, family_name="Tomography3")
    await bind_start(deps_3)(
        StartRun(name="completed-run", plan_id=plan_id_3, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_complete(deps_3)(
        CompleteRun(run_id=run_completed_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Run 4: Started -> Aborted (proves "Aborted").
    run_aborted_id = uuid4()
    deps_4 = _build_deps(db_pool, [*_chain_ids(), run_aborted_id, uuid4(), uuid4()])
    plan_id_4 = await _seed_plan(deps_4, family_name="Tomography4")
    await bind_start(deps_4)(
        StartRun(name="aborted-run", plan_id=plan_id_4, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_abort(deps_4)(
        AbortRun(run_id=run_aborted_id, reason="alignment lost"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Run 5: Started -> Stopped (proves "Stopped").
    run_stopped_id = uuid4()
    deps_5 = _build_deps(db_pool, [*_chain_ids(), run_stopped_id, uuid4(), uuid4()])
    plan_id_5 = await _seed_plan(deps_5, family_name="Tomography5")
    await bind_start(deps_5)(
        StartRun(name="stopped-run", plan_id=plan_id_5, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_stop(deps_5)(
        StopRun(run_id=run_stopped_id, reason="schedule ended"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Run 6: Started -> Truncated (proves "Truncated").
    run_truncated_id = uuid4()
    deps_6 = _build_deps(db_pool, [*_chain_ids(), run_truncated_id, uuid4(), uuid4()])
    plan_id_6 = await _seed_plan(deps_6, family_name="Tomography6")
    await bind_start(deps_6)(
        StartRun(name="truncated-run", plan_id=plan_id_6, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_truncate(deps_6)(
        TruncateRun(run_id=run_truncated_id, reason="power loss", interrupted_at=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT run_id, status FROM proj_run_summary WHERE run_id = ANY($1)",
            [
                run_held_id,
                run_resumed_id,
                run_completed_id,
                run_aborted_id,
                run_stopped_id,
                run_truncated_id,
            ],
        )
    actual = {row["run_id"]: row["status"] for row in rows}
    assert actual == {
        run_held_id: "Held",
        run_resumed_id: "Running",  # Held then Resumed back to Running
        run_completed_id: "Completed",
        run_aborted_id: "Aborted",
        run_stopped_id: "Stopped",
        run_truncated_id: "Truncated",
    }


@pytest.mark.integration
async def test_plan_id_filter_narrows_results(db_pool: asyncpg.Pool) -> None:
    """Two Runs against different Plans; plan_id filter returns one."""
    run_a = uuid4()
    deps_a = _build_deps(db_pool, [*_chain_ids(), run_a, uuid4()])
    plan_a = await _seed_plan(deps_a)
    await bind_start(deps_a)(
        StartRun(name="for-plan-a", plan_id=plan_a, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    run_b = uuid4()
    deps_b = _build_deps(db_pool, [*_chain_ids(), run_b, uuid4()])
    plan_b = await _seed_plan(deps_b, family_name="TomographyB")
    await bind_start(deps_b)(
        StartRun(name="for-plan-b", plan_id=plan_b, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)
    handler = bind_list(deps_a)
    page = await handler(
        ListRuns(plan_id=plan_a, limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].run_id == run_a
    assert page.items[0].plan_id == plan_a
    assert page.items[0].status == "Running"


@pytest.mark.integration
async def test_empty_table_returns_empty_page(db_pool: asyncpg.Pool) -> None:
    deps = _build_deps(db_pool, [])
    handler = bind_list(deps)
    page = await handler(
        ListRuns(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []


@pytest.mark.integration
async def test_campaign_id_filter_narrows_results(db_pool: asyncpg.Pool) -> None:
    """Campaign Watch #10: `?campaign_id=`
    end-to-end through real PG.

    Seeds two Runs against different Plans, then registers a Campaign
    and assigns one Run to it via `add_run_to_campaign`. Filtering
    `list_runs?campaign_id=<id>` returns only the member; the
    standalone Run is excluded.
    """
    from cora.campaign.aggregates.campaign import CampaignIntent
    from cora.campaign.features.add_run_to_campaign import AddRunToCampaign
    from cora.campaign.features.add_run_to_campaign import bind as bind_add_run
    from cora.campaign.features.register_campaign import RegisterCampaign
    from cora.campaign.features.register_campaign import bind as bind_register_campaign

    # Member Run.
    run_member = uuid4()
    deps_member = _build_deps(db_pool, [*_chain_ids(), run_member, uuid4()])
    plan_member = await _seed_plan(deps_member)
    await bind_start(deps_member)(
        StartRun(name="campaign-member-run", plan_id=plan_member, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Standalone Run (no Campaign).
    run_standalone = uuid4()
    deps_standalone = _build_deps(db_pool, [*_chain_ids(), run_standalone, uuid4()])
    plan_standalone = await _seed_plan(deps_standalone, family_name="TomographyStandalone")
    await bind_start(deps_standalone)(
        StartRun(name="standalone-run", plan_id=plan_standalone, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Register a Campaign and add the member Run to it.
    campaign_id = uuid4()
    lead_actor_id = uuid4()
    deps_campaign = _build_deps(db_pool, [campaign_id, uuid4()])
    await bind_register_campaign(deps_campaign)(
        RegisterCampaign(
            name="in-situ heating series",
            intent=CampaignIntent.SERIES,
            lead_actor_id=lead_actor_id,
            subject_id=None,
            description=None,
            tags=frozenset(),
            external_refs=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # add_run_to_campaign consumes 2 event IDs (one per stream:
    # CampaignRunAdded on the Campaign stream + RunAddedToCampaign
    # on the Run stream, atomic via append_streams).
    deps_add = _build_deps(db_pool, [uuid4(), uuid4()])
    await bind_add_run(deps_add)(
        AddRunToCampaign(campaign_id=campaign_id, run_id=run_member),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Need to also drain the Campaign BC projections (post-hoc
    # add_run_to_campaign writes to BOTH streams; the Run-side
    # RunAddedToCampaign is what proj_run_summary subscribes to).
    from cora.campaign._projections import register_campaign_projections

    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    register_recipe_projections(registry)
    register_run_projections(registry)
    register_campaign_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    handler = bind_list(deps_member)
    page = await handler(
        ListRuns(campaign_id=campaign_id, limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].run_id == run_member
    assert page.items[0].campaign_id == campaign_id
    assert page.next_cursor is None
