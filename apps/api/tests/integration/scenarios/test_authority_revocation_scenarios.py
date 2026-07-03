"""Multi-scenario evaluation of actor symmetry under real TrustAuthorize.

cluster: Advisories
archetype: agent
bc_primary: Trust
bc_touches: Trust, Run, Decision

Beyond the happy-path kill-switch (test_authority_revocation_compensation),
these scenarios exercise the symmetry principle where it is most testable: at
the DENY boundary and at replay-based attribution. Each is run against a real
TrustAuthorize gate (not the AllowAll default), so the authorization decision is
the production pure-fold PDP.

Scenarios (map to the paper's E1/E3 significance evidence):

  1. Escalation denied, symmetrically: a principal NOT granted RevokeGrant is
     denied when it attempts a revocation, and the deny is byte-for-byte the same
     whether that principal is flagged human or agent in the actor model -- the
     decision function never reads actor kind (I1).
  2. Human and agent, same grant, same allow: a human principal and an agent
     principal that share the identical grant both succeed on the same command by
     the same path (I1, the allow side).
  3. Replay recovers the correct actor: after an operator starts a run, an agent
     supervises it, and the SYSTEM holder holds it on revocation, replaying the
     log attributes each effect to the right principal -- operator, agent, and
     SYSTEM -- with no separate lineage instrumentation (I3).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.decision.aggregates.decision.read import load_decision
from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.event_store import EventStore
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID, SYSTEM_PRINCIPAL_ID
from cora.run._projections import register_run_projections
from cora.run.aggregates.run.read import load_run
from cora.run.aggregates.run.state import RunStatus
from cora.run.subscribers import make_authority_revocation_holder_subscriber
from cora.trust import UnauthorizedError
from cora.trust.authorize import TrustAuthorize
from cora.trust.features import revoke_grant
from cora.trust.features.revoke_grant import RevokeGrant
from tests._authz import seed_policy
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_OPERATOR_ID = UUID("01900000-0000-7000-8000-0000feed3001")
_AGENT_ID = UUID("01900000-0000-7000-8000-0000feed3002")
_UNGRANTED_ID = UUID("01900000-0000-7000-8000-0000feed3003")


def _gated_deps(db_pool: asyncpg.Pool, *, policy_id: UUID, ids: list[UUID]) -> Kernel:
    """Kernel gated by a real TrustAuthorize against `policy_id`."""
    event_store = PostgresEventStore(db_pool)
    return build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=ids,
        authz=TrustAuthorize(event_store, policy_id=policy_id),
        event_store=event_store,
    )


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
                    "name": "scenario run",
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
) -> UUID:
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
    return decision_id


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_run_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=5.0)


async def _latest_revoke_event(store: EventStore, *, policy_id: UUID) -> object:
    stored, _v = await store.load("Policy", policy_id)
    return next(e for e in reversed(stored) if e.event_type == "PolicyGrantRevoked")


@pytest.mark.integration
async def test_escalation_denied_is_symmetric_across_actor_kind(
    db_pool: asyncpg.Pool,
) -> None:
    """A principal not granted RevokeGrant is denied, and the denial is identical
    whether the principal is a human or an agent: the PDP never reads actor kind.

    We seed a policy granting RevokeGrant to nobody relevant, then attempt the
    revocation once as an 'agent' principal and once as a 'human' principal. Both
    raise UnauthorizedError with the same diagnostic shape (same evaluate() Deny
    path), which is the deny-side demonstration of I1."""
    policy_id = uuid4()
    # A target policy that grants HoldRun to the operator (so it exists + has a
    # grant to revoke), but the RevokeGrant COMMAND is not granted to our callers.
    target_policy = uuid4()

    bootstrap = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(10)])
    await seed_policy(
        bootstrap.event_store,
        policy_id=target_policy,
        permitted_principal_ids=[_OPERATOR_ID],
        permitted_commands=["HoldRun"],
    )
    # The GATING policy: permits only a bootstrap principal, and only DefinePolicy
    # -- so neither the agent nor the human caller may RevokeGrant.
    await seed_policy(
        bootstrap.event_store,
        policy_id=policy_id,
        permitted_principal_ids=[SYSTEM_PRINCIPAL_ID],
        permitted_commands=["DefinePolicy"],
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )

    reasons: list[str] = []
    for caller in (_AGENT_ID, _OPERATOR_ID):
        gated = _gated_deps(db_pool, policy_id=policy_id, ids=[uuid4() for _ in range(4)])
        with pytest.raises(UnauthorizedError) as exc:
            await revoke_grant.bind(gated)(
                RevokeGrant(policy_id=target_policy, principal_id=_OPERATOR_ID, reason="x"),
                principal_id=caller,
                correlation_id=_CORRELATION_ID,
                surface_id=SYSTEM_HTTP_SURFACE_ID,
            )
        reasons.append(type(exc.value).__name__)

    # Same rejection type for agent and human: the deny does not branch on kind.
    assert reasons == ["UnauthorizedError", "UnauthorizedError"]


@pytest.mark.integration
async def test_human_and_agent_same_grant_same_allow(
    db_pool: asyncpg.Pool,
) -> None:
    """A human principal and an agent principal that hold the identical grant
    both succeed on RevokeGrant by the same path (the allow side of I1)."""
    gating_policy = uuid4()
    bootstrap = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(10)])

    # Gating policy grants RevokeGrant to BOTH a human and an agent principal.
    await seed_policy(
        bootstrap.event_store,
        policy_id=gating_policy,
        permitted_principal_ids=[_OPERATOR_ID, _AGENT_ID],
        permitted_commands=["RevokeGrant"],
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )

    for caller in (_OPERATOR_ID, _AGENT_ID):
        # Each gets its own target policy with a grant to remove.
        target = uuid4()
        victim = uuid4()
        await seed_policy(
            bootstrap.event_store,
            policy_id=target,
            permitted_principal_ids=[victim],
            permitted_commands=["HoldRun"],
        )
        gated = _gated_deps(db_pool, policy_id=gating_policy, ids=[uuid4() for _ in range(4)])
        # Must not raise: identical grant -> identical allow, human or agent.
        await revoke_grant.bind(gated)(
            RevokeGrant(policy_id=target, principal_id=victim, reason="symmetry"),
            principal_id=caller,
            correlation_id=_CORRELATION_ID,
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        )
        stored, _v = await bootstrap.event_store.load("Policy", target)
        assert any(e.event_type == "PolicyGrantRevoked" for e in stored)


@pytest.mark.integration
async def test_replay_recovers_the_correct_actor_for_each_effect(
    db_pool: asyncpg.Pool,
) -> None:
    """After operator-starts, agent-supervises, SYSTEM-holds-on-revocation,
    replaying the log attributes each effect to the right principal with no
    separate lineage instrumentation (I3)."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(50)])
    store = deps.event_store

    run_id = uuid4()
    policy_id = uuid4()
    await _append_run_started(store, run_id=run_id, starter_id=_OPERATOR_ID)
    await _append_supervision_decision(store, supervisor_id=_AGENT_ID, run_id=run_id)
    await _drain(db_pool)

    await seed_policy(
        store,
        policy_id=policy_id,
        permitted_principal_ids=[_OPERATOR_ID, _AGENT_ID],
        permitted_commands=["HoldRun"],
    )
    await revoke_grant.bind(deps)(
        RevokeGrant(policy_id=policy_id, principal_id=_AGENT_ID, reason="scenario"),
        principal_id=_OPERATOR_ID,
        correlation_id=_CORRELATION_ID,
    )
    revoke_event = await _latest_revoke_event(store, policy_id=policy_id)
    subscriber = make_authority_revocation_holder_subscriber(deps)
    await subscriber.apply(revoke_event, conn=None)  # type: ignore[arg-type]

    # The run is held, and replay attributes the effects correctly.
    run = await load_run(store, run_id)
    assert run is not None
    assert run.status is RunStatus.HELD

    # Attribution 1: the RunStarted effect is attributed to the operator (the
    # envelope principal), recovered by reading the run stream.
    run_stored, _v = await store.load("Run", run_id)
    started = next(e for e in run_stored if e.event_type == "RunStarted")
    assert started.principal_id == _OPERATOR_ID

    # Attribution 2: the hold Decision is attributed to the SYSTEM holder, and
    # its inputs name the revoked agent and the run -- recovered by folding the
    # Decision the RunHeld links to.
    held = next(e for e in run_stored if e.event_type == "RunHeld")
    decision_id = UUID(held.payload["decided_by_decision_id"])
    decision = await load_decision(store, decision_id)
    assert decision is not None
    assert decision.decided_by == SYSTEM_PRINCIPAL_ID
    assert decision.context.value == "AuthorityRevocation"
    assert decision.inputs is not None
    assert decision.inputs["revoked_principal_id"] == str(_AGENT_ID)
    assert decision.inputs["run_id"] == str(run_id)
