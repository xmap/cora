"""E4 scenario: revoke an agent's grant mid-run -> its in-flight run is HELD.

cluster: Advisories
archetype: agent
bc_primary: Run
bc_touches: Trust, Run, Decision

The authority-revocation kill-switch, end to end against real Postgres.
This is the paper's centerpiece (T-ASE E4): "pull the plug on the AI
mid-run and the experiment lands in a defined state."

Chain:
  1. An OPERATOR starts a run (RunStarted, envelope principal = operator).
  2. An AGENT supervises it (a RunSupervision DecisionRegistered).
     -> drain: proj_run_actor_involvement has a starter row (operator) AND
        a supervisor row (agent), both in-flight.
  3. The agent's grant is revoked via the real `revoke_grant` handler
     (PolicyGrantRevoked on the Policy stream).
  4. -> drain with the holder subscriber registered: it looks up the
        agent's in-flight runs and issues HoldRun as SYSTEM.

Asserts the run folds to Held and an AuthorityRevocation Decision was
recorded, and that revoking an UNINVOLVED principal holds nothing.

The compensation is reversible (Held, not Aborted): a human operator can
take the run over or resume it. Symmetric by construction: the same path
would hold a human's in-flight run if a human's grant were revoked.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports.event_store import EventStore, StoredEvent
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.run._projections import register_run_projections
from cora.run.aggregates.run.read import load_run
from cora.run.aggregates.run.state import RunStatus
from cora.run.subscribers import make_authority_revocation_holder_subscriber
from cora.trust.features import revoke_grant
from cora.trust.features.revoke_grant import RevokeGrant
from tests._authz import seed_policy
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_OPERATOR_ID = UUID("01900000-0000-7000-8000-0000feed1001")


async def _append_run_started(store: EventStore, *, run_id: UUID, starter_id: UUID) -> None:
    await store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type="RunStarted",
                payload={
                    "run_id": str(run_id),
                    "name": "lights-out tomography",
                    "plan_id": str(uuid4()),
                    "subject_id": None,
                    "occurred_at": _NOW.isoformat(),
                },
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="StartRun",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=starter_id,
            )
        ],
    )


async def _append_supervision_decision(
    store: EventStore, *, supervisor_id: UUID, run_id: UUID
) -> None:
    decision_id = uuid4()
    await store.append(
        stream_type="Decision",
        stream_id=decision_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type="DecisionRegistered",
                payload={
                    "decision_id": str(decision_id),
                    "decided_by": str(supervisor_id),
                    "context": "RunSupervision",
                    "choice": "Continue",
                    "parent_id": None,
                    "override_kind": None,
                    "rule": "agent:RunSupervisor:v1",
                    "reasoning": None,
                    "confidence": None,
                    "confidence_source": None,
                    "alternatives": [],
                    "inputs": {"run_id": str(run_id)},
                    "reasoning_signature": None,
                    "occurred_at": _NOW.isoformat(),
                },
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="RegisterDecision",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=supervisor_id,
            )
        ],
    )


async def _drain_projections(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_run_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _run_holder_on(deps: object, revoke_event: StoredEvent) -> None:
    """Drive the holder subscriber directly against a PolicyGrantRevoked event.

    The unit-of-behavior tests call `apply(event, conn=None)` directly (the
    canonical Reaction pattern from test_run_debriefer_subscriber_postgres),
    isolating the compensation logic on the real event store + involvement
    projection. The separate worker-driven test below proves the bookmark
    migration wires the subscriber onto the live advance loop."""
    subscriber = make_authority_revocation_holder_subscriber(deps)  # type: ignore[arg-type]
    await subscriber.apply(revoke_event, conn=None)


async def _latest_policy_grant_revoked(store: EventStore, *, policy_id: UUID) -> StoredEvent:
    """Load the PolicyGrantRevoked event just written to the Policy stream."""
    stored, _version = await store.load("Policy", policy_id)
    revoked = [e for e in stored if e.event_type == "PolicyGrantRevoked"]
    assert revoked, "expected a PolicyGrantRevoked on the Policy stream"
    return revoked[-1]


async def _find_authority_revocation_decision(
    db_pool: asyncpg.Pool, *, run_id: UUID
) -> asyncpg.Record | None:
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT payload
              FROM events
             WHERE stream_type = 'Decision'
               AND event_type = 'DecisionRegistered'
               AND payload->>'context' = 'AuthorityRevocation'
               AND payload->'inputs'->>'run_id' = $1
            """,
            str(run_id),
        )


@pytest.mark.integration
async def test_revoking_supervising_agent_holds_its_inflight_run(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(50)])
    store = deps.event_store

    run_id = uuid4()
    agent_id = uuid4()  # the supervising agent
    policy_id = uuid4()

    # 1 + 2: operator starts, agent supervises.
    await _append_run_started(store, run_id=run_id, starter_id=_OPERATOR_ID)
    await _append_supervision_decision(store, supervisor_id=agent_id, run_id=run_id)
    await _drain_projections(db_pool)

    # 3: the agent's grant is revoked (real revoke_grant handler).
    await seed_policy(
        store,
        policy_id=policy_id,
        permitted_principal_ids=[_OPERATOR_ID, agent_id],
        permitted_commands=["HoldRun"],
    )
    await revoke_grant.bind(deps)(
        RevokeGrant(policy_id=policy_id, principal_id=agent_id, reason="agent decommissioned"),
        principal_id=_OPERATOR_ID,
        correlation_id=_CORRELATION_ID,
    )

    # 4: the holder reacts -> the agent's in-flight run is held.
    revoke_event = await _latest_policy_grant_revoked(store, policy_id=policy_id)
    await _run_holder_on(deps, revoke_event)

    run = await load_run(store, run_id)
    assert run is not None
    assert run.status is RunStatus.HELD

    decision = await _find_authority_revocation_decision(db_pool, run_id=run_id)
    assert decision is not None, "expected an AuthorityRevocation Decision for the held run"


@pytest.mark.integration
async def test_revoking_uninvolved_principal_holds_nothing(
    db_pool: asyncpg.Pool,
) -> None:
    """A revocation for a principal behind no in-flight run is inert."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(50)])
    store = deps.event_store

    run_id = uuid4()
    agent_id = uuid4()
    stranger_id = uuid4()  # not behind any run
    policy_id = uuid4()

    await _append_run_started(store, run_id=run_id, starter_id=_OPERATOR_ID)
    await _append_supervision_decision(store, supervisor_id=agent_id, run_id=run_id)
    await _drain_projections(db_pool)

    await seed_policy(
        store,
        policy_id=policy_id,
        permitted_principal_ids=[_OPERATOR_ID, stranger_id],
        permitted_commands=["HoldRun"],
    )
    await revoke_grant.bind(deps)(
        RevokeGrant(policy_id=policy_id, principal_id=stranger_id, reason="role change"),
        principal_id=_OPERATOR_ID,
        correlation_id=_CORRELATION_ID,
    )
    revoke_event = await _latest_policy_grant_revoked(store, policy_id=policy_id)
    await _run_holder_on(deps, revoke_event)

    run = await load_run(store, run_id)
    assert run is not None
    assert run.status is RunStatus.RUNNING  # untouched
    assert await _find_authority_revocation_decision(db_pool, run_id=run_id) is None


@pytest.mark.integration
async def test_holder_fires_via_the_live_worker_bookmark(
    db_pool: asyncpg.Pool,
) -> None:
    """The holder registered on the projection worker holds a revoked
    agent's run WITHOUT a direct apply() call.

    This drives the real advance loop, which reads
    `projection_bookmarks` by subscriber name: it fails with
    MissingBookmarkError unless the bookmark-seed migration landed. It is
    the regression test for the gate-review P0 (the direct-apply() tests
    above never touch the bookmark path)."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(50)])
    store = deps.event_store

    run_id = uuid4()
    agent_id = uuid4()
    policy_id = uuid4()

    await _append_run_started(store, run_id=run_id, starter_id=_OPERATOR_ID)
    await _append_supervision_decision(store, supervisor_id=agent_id, run_id=run_id)
    await _drain_projections(db_pool)

    await seed_policy(
        store,
        policy_id=policy_id,
        permitted_principal_ids=[_OPERATOR_ID, agent_id],
        permitted_commands=["HoldRun"],
    )
    await revoke_grant.bind(deps)(
        RevokeGrant(policy_id=policy_id, principal_id=agent_id, reason="agent decommissioned"),
        principal_id=_OPERATOR_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Drain with the holder registered on the worker (no direct apply()):
    # this is the path that reads the projection_bookmarks row.
    registry = ProjectionRegistry()
    register_run_projections(registry)
    registry.register(make_authority_revocation_holder_subscriber(deps))  # type: ignore[arg-type]
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    run = await load_run(store, run_id)
    assert run is not None
    assert run.status is RunStatus.HELD
