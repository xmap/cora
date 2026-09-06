"""End-to-end PG integration test: `define_agent` cross-BC atomic write.

Pins the cross-BC, two-stream atomic-write contract under real
Postgres. `define_agent` writes BOTH an `ActorRegistered(kind="agent")`
event on the Access stream AND an `AgentDefined` event on the Agent
stream in ONE transaction via `EventStore.append_streams`.

This is the first cross-BC atomic write in CORA (prior `append_streams`
consumers in Safety and Caution were intra-BC). The integration test
verifies:

  1. Happy-path: both streams advance to version 1 in a single
     transaction (shared xid8), Decision.actor_id semantics survive
     because the agent's id is queryable as an Actor.
  2. The co-written Actor carries `kind="agent"` per the design lock.

Concurrency-rollback test (id collision on either stream rolls back
the whole batch) is implicit in the `append_streams` infra tests
already at `tests/integration/test_append_streams_postgres.py` and is
not re-tested here; this file focuses on the cross-BC seam.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.access.aggregates.actor import ActorKind, load_actor
from cora.agent.aggregates.agent import AgentStatus, BrainRef, ModelRef, load_agent
from cora.agent.features import define_agent
from cora.agent.features.define_agent import DefineAgent
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000e001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000e002")


@pytest.mark.integration
async def test_define_agent_writes_both_streams_atomically(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(5)])
    profile_store = make_pg_profile_store(db_pool)

    agent_id = await define_agent.bind(deps, profile_store=profile_store)(
        DefineAgent(
            kind="RunDebriefer",
            name="Run Debrief",
            version="v1",
            model_ref=ModelRef(
                provider="anthropic",
                model="claude-sonnet-4-6",
                snapshot_pin="20251001",
            ),
            description="Synthesises terminal Runs.",
            canonical_uri="https://example.org/agents/run-debrief",
            capabilities=frozenset({"summarize"}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Agent stream is populated.
    agent = await load_agent(deps.event_store, agent_id)
    assert agent is not None
    assert agent.id == agent_id
    assert agent.kind.value == "RunDebriefer"
    assert agent.status is AgentStatus.DEFINED
    # A wire-defined agent still records `model_ref`, and its brain derives
    # from it: only the seeds have moved to declaring `brain` directly.
    assert agent.model_ref is not None
    assert agent.model_ref.snapshot_pin == "20251001"
    assert agent.brain == BrainRef.for_model(agent.model_ref)
    assert agent.canonical_uri is not None
    assert agent.canonical_uri.value == "https://example.org/agents/run-debrief"

    # Access stream is populated with the SAME id and kind=agent. PII
    # vault: the display name lives in actor_profile (not on the
    # aggregate); verified via profile_store below.
    actor = await load_actor(deps.event_store, agent_id)
    assert actor is not None
    assert actor.id == agent_id
    assert actor.kind is ActorKind.AGENT
    assert actor.active is True

    profile = await profile_store.get(agent_id)
    assert profile is not None
    assert profile.name == "Run Debrief"


@pytest.mark.integration
async def test_define_agent_shared_xid8_across_streams(
    db_pool: asyncpg.Pool,
) -> None:
    """Both events MUST land in the same transaction (shared xid8).

    The events table has a `transaction_id xid8` column populated by
    `pg_current_xact_id()` on insert. A successful `append_streams`
    call inserts all events in ONE transaction, so both the Agent
    and Actor events share the same `transaction_id` value.
    """
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(5)])
    profile_store = make_pg_profile_store(db_pool)

    agent_id = await define_agent.bind(deps, profile_store=profile_store)(
        DefineAgent(
            kind="RunDebriefer",
            name="Run Debrief",
            version="v1",
            model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT stream_type, transaction_id::text AS xid
              FROM events
             WHERE stream_id = $1
             ORDER BY position
            """,
            agent_id,
        )

    # Both Actor and Agent events present.
    stream_types = {r["stream_type"] for r in rows}
    assert stream_types == {"Actor", "Agent"}, stream_types
    # Single shared transaction.
    xids = {r["xid"] for r in rows}
    assert len(xids) == 1, f"expected shared xid8 across streams, got {xids}"
