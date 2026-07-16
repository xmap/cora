"""End-to-end integration: the consequence gate (Gate IV) against real Postgres.

Drives the whole refuse -> request -> hold -> grant -> release -> re-stop -> admit
flow through the real handlers, subscribers, and coverage projection:

  1. seed a Running run started by an operator;
  2. stop_run REFUSED (RunRequiresRatificationError): StopRun is consequence-classed
     and no Granted Ratification covers it (real PostgresConsequenceLookup, no stub);
  3. request_ratification(target_action_id=run_id, command_name="StopRun");
  4. drain -> RatificationHoldSubscriber holds the run (RunHeld);
  5. grant_ratification by a SECOND, independent principal;
  6. drain -> coverage projection marks Granted + RatificationReleaseSubscriber
     resumes the run (RunResumed -> Running);
  7. stop_run now ADMITTED (coverage present) -> Run is Stopped.

Also pins the refuse path leaves the run Running (no premature stop).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.seed_ratification_enforcer import seed_ratification_enforcer_agent
from cora.agent.subscribers.ratification_hold import make_ratification_hold_subscriber
from cora.agent.subscribers.ratification_release import make_ratification_release_subscriber
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features import add_asset_family, define_family, register_asset
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import UUIDv7Generator
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.infrastructure.projection.bookmark import ensure_bookmarks
from cora.recipe.aggregates.method import ExecutionPattern
from cora.recipe.features import define_method, define_plan, define_practice
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from cora.run.aggregates.run import RunRequiresRatificationError, RunStatus, load_run
from cora.run.features import start_run, stop_run
from cora.run.features.start_run import StartRun
from cora.run.features.stop_run import StopRun
from cora.subject.features import mount_subject, register_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from cora.trust.adapters import PostgresConsequenceLookup
from cora.trust.features import deny_ratification, grant_ratification, request_ratification
from cora.trust.features.deny_ratification import DenyRatification
from cora.trust.features.grant_ratification import GrantRatification
from cora.trust.features.request_ratification import RequestRatification
from cora.trust.projections import RatificationCoverageProjection
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres
from tests.unit.subject._helpers import seed_active_asset

_NOW = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_OPERATOR = UUID("01900000-0000-7000-8000-0000000000b1")
_CO_SIGNER = UUID("01900000-0000-7000-8000-0000000000b2")


def _deps(db_pool: asyncpg.Pool) -> Kernel:
    """Kernel with the REAL Postgres consequence lookup (not the AlwaysRatified
    stub), so the gate actually consults the coverage projection."""
    return build_postgres_deps(
        db_pool,
        now=_NOW,
        id_generator=UUIDv7Generator(),
        consequence_lookup=PostgresConsequenceLookup(db_pool),
    )


async def _start_run_as(deps: Kernel, *, starter: UUID) -> UUID:
    family_id = await define_family.bind(deps)(
        DefineFamily(name="FlyMotion-cg", affordances=frozenset()),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="Eiger-cg", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )
    cap_event_id = uuid4()
    await seed_capability_postgres(deps.event_store, cap_event_id)
    method_id = await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=cap_event_id,
            name="XRF cg",
            needed_family_ids=frozenset({family_id}),
        ),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name="APS cg", method_id=method_id, site_id=uuid4()),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )
    plan_id = await define_plan.bind(deps)(
        DefinePlan(name="cg plan", practice_id=practice_id, asset_ids=frozenset({asset_id})),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )
    subject_id = await register_subject.bind(deps)(
        RegisterSubject(name="Sample-cg"),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )
    mount_asset_id = await seed_active_asset(
        deps.event_store, asset_id=uuid4(), now=_NOW, correlation_id=_CORRELATION_ID
    )
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=mount_asset_id, reason=""),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )
    return await start_run.bind(deps)(
        StartRun(name="cg session", plan_id=plan_id, subject_id=subject_id),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )


async def _drain(db_pool: asyncpg.Pool, deps: Kernel) -> None:
    """Drain the coverage projection + both enforcer subscribers together.

    Seeds bookmarks via the production `ensure_bookmarks` helper (the same one the
    projection worker lifespan runs at startup) so the Reactions have a cursor: the
    coverage projection's row comes from its migration, the two subscribers' rows
    from ensure_bookmarks. The bare `drain_projections` helper does not seed (only
    the lifespan does), so the test invokes the seam explicitly.
    """
    registry = ProjectionRegistry()
    registry.register(RatificationCoverageProjection())
    registry.register(make_ratification_hold_subscriber(deps))
    registry.register(make_ratification_release_subscriber(deps))
    await ensure_bookmarks(db_pool, registry.names())
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _status(deps: Kernel, run_id: UUID) -> RunStatus:
    """Load a run and return its status, asserting it exists (test convenience)."""
    state = await load_run(deps.event_store, run_id)
    assert state is not None
    return state.status


@pytest.mark.integration
async def test_consequence_gate_full_cosign_flow(db_pool: asyncpg.Pool) -> None:
    deps = _deps(db_pool)
    await seed_ratification_enforcer_agent(deps)
    run_id = await _start_run_as(deps, starter=_OPERATOR)

    # 1. Uncovered stop is REFUSED.
    with pytest.raises(RunRequiresRatificationError):
        await stop_run.bind(deps)(
            StopRun(run_id=run_id, reason="end early"),
            principal_id=_OPERATOR,
            correlation_id=_CORRELATION_ID,
        )
    assert await _status(deps, run_id) is RunStatus.RUNNING

    # 2. Operator requests a ratification for this action (caller-supplied id).
    ratification_id = uuid4()
    await request_ratification.bind(deps)(
        RequestRatification(
            ratification_id=ratification_id,
            target_action_id=run_id,
            command_name="StopRun",
            consequence_class="irreversible",
        ),
        principal_id=_OPERATOR,
        correlation_id=_CORRELATION_ID,
    )

    # 3. Drain -> hold subscriber parks the run.
    await _drain(db_pool, deps)
    assert await _status(deps, run_id) is RunStatus.HELD

    # 4. A SECOND, independent principal grants the co-signature.
    await grant_ratification.bind(deps)(
        GrantRatification(ratification_id=ratification_id),
        principal_id=_CO_SIGNER,
        correlation_id=_CORRELATION_ID,
    )

    # 5. Drain -> coverage marked Granted + release subscriber resumes the run.
    await _drain(db_pool, deps)
    assert await _status(deps, run_id) is RunStatus.RUNNING

    # 6. Re-issue stop_run: now covered, so it is ADMITTED.
    await stop_run.bind(deps)(
        StopRun(run_id=run_id, reason="end early"),
        principal_id=_OPERATOR,
        correlation_id=_CORRELATION_ID,
    )
    assert await _status(deps, run_id) is RunStatus.STOPPED


@pytest.mark.integration
async def test_coverage_projection_replay_is_idempotent(db_pool: asyncpg.Pool) -> None:
    """Re-draining the coverage projection from a reset bookmark (a rebuild) yields
    one row in its final state: the INSERT's ON CONFLICT DO NOTHING + set-to-value
    UPDATE make the fold idempotent, so a replayed RatificationRequested+Granted
    does not double-insert or crash."""
    deps = _deps(db_pool)
    await seed_ratification_enforcer_agent(deps)
    run_id = await _start_run_as(deps, starter=_OPERATOR)
    ratification_id = uuid4()
    await request_ratification.bind(deps)(
        RequestRatification(
            ratification_id=ratification_id,
            target_action_id=run_id,
            command_name="StopRun",
            consequence_class="irreversible",
        ),
        principal_id=_OPERATOR,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool, deps)
    await grant_ratification.bind(deps)(
        GrantRatification(ratification_id=ratification_id),
        principal_id=_CO_SIGNER,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool, deps)

    # Force a full replay of the coverage projection from zero.
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE projection_bookmarks SET last_transaction_id = '0'::xid8, last_position = 0 "
            "WHERE name = 'proj_trust_ratification_coverage'"
        )
    await _drain(db_pool, deps)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT status FROM proj_trust_ratification_coverage WHERE ratification_id = $1",
            ratification_id,
        )
    assert len(rows) == 1
    assert rows[0]["status"] == "Granted"


@pytest.mark.integration
async def test_requested_not_yet_granted_still_refuses(db_pool: asyncpg.Pool) -> None:
    """The ConsequenceLookup Granted-only filter: a merely Requested (pending)
    ratification does NOT count as coverage. After request + drain (run Held,
    coverage=Requested), a re-issued stop still REFUSES."""
    deps = _deps(db_pool)
    await seed_ratification_enforcer_agent(deps)
    run_id = await _start_run_as(deps, starter=_OPERATOR)

    with pytest.raises(RunRequiresRatificationError):
        await stop_run.bind(deps)(
            StopRun(run_id=run_id, reason="end early"),
            principal_id=_OPERATOR,
            correlation_id=_CORRELATION_ID,
        )

    ratification_id = uuid4()
    await request_ratification.bind(deps)(
        RequestRatification(
            ratification_id=ratification_id,
            target_action_id=run_id,
            command_name="StopRun",
            consequence_class="irreversible",
        ),
        principal_id=_OPERATOR,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool, deps)
    assert await _status(deps, run_id) is RunStatus.HELD

    # Coverage is only Requested, not Granted -> the gate still refuses. (The run
    # is Held so this raise happens after the gate, but the point is the gate does
    # not admit on a pending request.)
    with pytest.raises(RunRequiresRatificationError):
        await stop_run.bind(deps)(
            StopRun(run_id=run_id, reason="end early"),
            principal_id=_OPERATOR,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
async def test_denied_resumes_run_and_leaves_coverage_absent(db_pool: asyncpg.Pool) -> None:
    """Denial un-parks the run (back to Running) and never grants coverage, so a
    re-issued stop still refuses. The reversible hold stays reversible."""
    deps = _deps(db_pool)
    await seed_ratification_enforcer_agent(deps)
    run_id = await _start_run_as(deps, starter=_OPERATOR)

    with pytest.raises(RunRequiresRatificationError):
        await stop_run.bind(deps)(
            StopRun(run_id=run_id, reason="end early"),
            principal_id=_OPERATOR,
            correlation_id=_CORRELATION_ID,
        )
    ratification_id = uuid4()
    await request_ratification.bind(deps)(
        RequestRatification(
            ratification_id=ratification_id,
            target_action_id=run_id,
            command_name="StopRun",
            consequence_class="irreversible",
        ),
        principal_id=_OPERATOR,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool, deps)
    assert await _status(deps, run_id) is RunStatus.HELD

    # A second independent principal DENIES the co-signature.
    await deny_ratification.bind(deps)(
        DenyRatification(ratification_id=ratification_id, reason="not this time"),
        principal_id=_CO_SIGNER,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool, deps)

    # Run un-parked (Running again), and coverage never became Granted so a
    # re-issued stop refuses.
    assert await _status(deps, run_id) is RunStatus.RUNNING
    with pytest.raises(RunRequiresRatificationError):
        await stop_run.bind(deps)(
            StopRun(run_id=run_id, reason="end early"),
            principal_id=_OPERATOR,
            correlation_id=_CORRELATION_ID,
        )
