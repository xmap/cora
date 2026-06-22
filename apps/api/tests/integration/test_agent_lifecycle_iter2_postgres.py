"""End-to-end PG integration test: Agent lifecycle slices.

Exercises the new transition slices against real Postgres to verify:

  1. Suspend / Resume FSM cycle persists and re-loads correctly.
  2. Tool grants / revocations persist in `Agent.tools`.
  3. AgentBudgetUpdated persists the budget; clearing zeroes the field.
  4. Deprecation source set really does include `Suspended` (the
     widened transition).

Per the project test-infra convention, this is a single Postgres-backed
file that consolidates the lifecycle-widening PG-side coverage. The
unit / contract suites already exhaustively cover deciders, handlers, REST surface,
and MCP surface; this file pins the "everything works through real
PG" contract that the in-memory store can't prove.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.aggregates.agent import (
    AgentBudget,
    AgentStatus,
    ModelRef,
    ToolName,
    load_agent,
)
from cora.agent.features import (
    define_agent,
    deprecate_agent,
    grant_tool_to_agent,
    resume_agent,
    revoke_tool_from_agent,
    suspend_agent,
    update_agent_budget,
    version_agent,
)
from cora.agent.features.define_agent import DefineAgent
from cora.agent.features.deprecate_agent import DeprecateAgent
from cora.agent.features.grant_tool_to_agent import GrantToolToAgent
from cora.agent.features.resume_agent import ResumeAgent
from cora.agent.features.revoke_tool_from_agent import RevokeToolFromAgent
from cora.agent.features.suspend_agent import SuspendAgent
from cora.agent.features.update_agent_budget import UpdateAgentBudget
from cora.agent.features.version_agent import VersionAgent
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000a201")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000a202")


async def _define_and_version(deps, db_pool: asyncpg.Pool) -> UUID:  # type: ignore[no-untyped-def]
    """Common setup: define + version an Agent, return its id."""
    agent_id = await define_agent.bind(deps, profile_store=make_pg_profile_store(db_pool))(
        DefineAgent(
            kind="RunDebriefer",
            name="Run Debrief",
            version="v1",
            model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await version_agent.bind(deps)(
        VersionAgent(agent_id=agent_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return agent_id


@pytest.mark.integration
async def test_suspend_resume_cycle_persists(db_pool: asyncpg.Pool) -> None:
    """Versioned -> Suspended -> Versioned cycle re-loads with correct state."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(8)])
    agent_id = await _define_and_version(deps, db_pool)

    await suspend_agent.bind(deps)(
        SuspendAgent(agent_id=agent_id, reason="cost overrun"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    after_suspend = await load_agent(deps.event_store, agent_id)
    assert after_suspend is not None
    assert after_suspend.status is AgentStatus.SUSPENDED
    assert after_suspend.suspended_at is not None
    assert after_suspend.suspension_reason is not None
    assert after_suspend.suspension_reason.value == "cost overrun"

    await resume_agent.bind(deps)(
        ResumeAgent(agent_id=agent_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    after_resume = await load_agent(deps.event_store, agent_id)
    assert after_resume is not None
    assert after_resume.status is AgentStatus.VERSIONED
    # Historical context preserved.
    assert after_resume.suspended_at == after_suspend.suspended_at
    assert after_resume.suspension_reason is not None
    assert after_resume.suspension_reason.value == "cost overrun"
    assert after_resume.resumed_at is not None


@pytest.mark.integration
async def test_grant_then_revoke_round_trip_persists(db_pool: asyncpg.Pool) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(8)])
    agent_id = await _define_and_version(deps, db_pool)

    await grant_tool_to_agent.bind(deps)(
        GrantToolToAgent(agent_id=agent_id, tool_name="read_run"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await grant_tool_to_agent.bind(deps)(
        GrantToolToAgent(agent_id=agent_id, tool_name="read_dataset"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    after_grants = await load_agent(deps.event_store, agent_id)
    assert after_grants is not None
    assert after_grants.tools == frozenset({ToolName("read_run"), ToolName("read_dataset")})

    await revoke_tool_from_agent.bind(deps)(
        RevokeToolFromAgent(agent_id=agent_id, tool_name="read_run"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    after_revoke = await load_agent(deps.event_store, agent_id)
    assert after_revoke is not None
    assert after_revoke.tools == frozenset({ToolName("read_dataset")})


@pytest.mark.integration
async def test_grant_idempotent_does_not_advance_stream(
    db_pool: asyncpg.Pool,
) -> None:
    """Re-granting the same tool MUST NOT append a new event."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(8)])
    agent_id = await _define_and_version(deps, db_pool)

    await grant_tool_to_agent.bind(deps)(
        GrantToolToAgent(agent_id=agent_id, tool_name="read_run"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _, version_after_first = await deps.event_store.load("Agent", agent_id)

    await grant_tool_to_agent.bind(deps)(
        GrantToolToAgent(agent_id=agent_id, tool_name="read_run"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _, version_after_second = await deps.event_store.load("Agent", agent_id)

    assert version_after_second == version_after_first


@pytest.mark.integration
async def test_budget_set_then_clear_persists(db_pool: asyncpg.Pool) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(8)])
    agent_id = await _define_and_version(deps, db_pool)

    await update_agent_budget.bind(deps)(
        UpdateAgentBudget(agent_id=agent_id, monthly_usd_cap=100.0, daily_token_cap=500_000),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    after_set = await load_agent(deps.event_store, agent_id)
    assert after_set is not None
    assert after_set.budget == AgentBudget(monthly_usd_cap=100.0, daily_token_cap=500_000)

    await update_agent_budget.bind(deps)(
        UpdateAgentBudget(agent_id=agent_id, monthly_usd_cap=None, daily_token_cap=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    after_clear = await load_agent(deps.event_store, agent_id)
    assert after_clear is not None
    assert after_clear.budget is None


@pytest.mark.integration
async def test_deprecate_from_suspended_persists(db_pool: asyncpg.Pool) -> None:
    """Iter 2 widens deprecate's source set to include Suspended."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(8)])
    agent_id = await _define_and_version(deps, db_pool)

    await suspend_agent.bind(deps)(
        SuspendAgent(agent_id=agent_id, reason="needs retirement"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await deprecate_agent.bind(deps)(
        DeprecateAgent(agent_id=agent_id, reason="retired while paused"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    final = await load_agent(deps.event_store, agent_id)
    assert final is not None
    assert final.status is AgentStatus.DEPRECATED
    assert final.deprecation_reason is not None
    assert final.deprecation_reason.value == "retired while paused"
