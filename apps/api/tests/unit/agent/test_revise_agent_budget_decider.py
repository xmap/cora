"""Pure-decider tests for the `revise_agent_budget` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.agent.aggregates.agent import (
    Agent,
    AgentBudget,
    AgentBudgetRevised,
    AgentCannotReviseBudgetError,
    AgentKind,
    AgentName,
    AgentNotFoundError,
    AgentStatus,
    AgentVersion,
    InvalidAgentBudgetError,
    ModelRef,
)
from cora.agent.features.revise_agent_budget.command import ReviseAgentBudget
from cora.agent.features.revise_agent_budget.decider import decide

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _agent(
    status: AgentStatus,
    *,
    budget: AgentBudget | None = None,
    agent_id: object | None = None,
) -> Agent:
    return Agent(
        id=agent_id or uuid4(),  # type: ignore[arg-type]
        kind=AgentKind("RunDebriefer"),
        name=AgentName("Run Debrief"),
        version=AgentVersion("v1"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        status=status,
        budget=budget,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "status", [AgentStatus.DEFINED, AgentStatus.VERSIONED, AgentStatus.SUSPENDED]
)
def test_sets_budget_from_unset_in_each_allowed_source_state(
    status: AgentStatus,
) -> None:
    agent = _agent(status)
    events = decide(
        state=agent,
        command=ReviseAgentBudget(
            agent_id=agent.id,
            monthly_usd_cap=100.0,
            daily_token_cap=1_000_000,
        ),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], AgentBudgetRevised)
    assert events[0].monthly_usd_cap == 100.0
    assert events[0].daily_token_cap == 1_000_000


@pytest.mark.unit
def test_sets_only_monthly_cap_leaving_daily_unset() -> None:
    agent = _agent(AgentStatus.VERSIONED)
    events = decide(
        state=agent,
        command=ReviseAgentBudget(agent_id=agent.id, monthly_usd_cap=50.0, daily_token_cap=None),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].monthly_usd_cap == 50.0
    assert events[0].daily_token_cap is None


@pytest.mark.unit
def test_clears_budget_when_both_caps_none() -> None:
    agent = _agent(
        AgentStatus.VERSIONED,
        budget=AgentBudget(monthly_usd_cap=100.0, daily_token_cap=500_000),
    )
    events = decide(
        state=agent,
        command=ReviseAgentBudget(agent_id=agent.id, monthly_usd_cap=None, daily_token_cap=None),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].monthly_usd_cap is None
    assert events[0].daily_token_cap is None


@pytest.mark.unit
def test_idempotent_revise_to_same_budget_emits_no_event() -> None:
    agent = _agent(
        AgentStatus.VERSIONED,
        budget=AgentBudget(monthly_usd_cap=100.0, daily_token_cap=500_000),
    )
    events = decide(
        state=agent,
        command=ReviseAgentBudget(
            agent_id=agent.id, monthly_usd_cap=100.0, daily_token_cap=500_000
        ),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_idempotent_clear_when_already_cleared() -> None:
    agent = _agent(AgentStatus.VERSIONED, budget=None)
    events = decide(
        state=agent,
        command=ReviseAgentBudget(agent_id=agent.id, monthly_usd_cap=None, daily_token_cap=None),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    with pytest.raises(AgentNotFoundError):
        decide(
            state=None,
            command=ReviseAgentBudget(agent_id=uuid4(), monthly_usd_cap=10.0, daily_token_cap=None),
            now=_NOW,
        )


@pytest.mark.unit
def test_cannot_revise_when_deprecated() -> None:
    agent = _agent(AgentStatus.DEPRECATED)
    with pytest.raises(AgentCannotReviseBudgetError):
        decide(
            state=agent,
            command=ReviseAgentBudget(
                agent_id=agent.id, monthly_usd_cap=10.0, daily_token_cap=None
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_negative_monthly_cap_raises_invalid_budget() -> None:
    """VO invariant fires before idempotency short-circuiting."""
    agent = _agent(AgentStatus.VERSIONED)
    with pytest.raises(InvalidAgentBudgetError):
        decide(
            state=agent,
            command=ReviseAgentBudget(
                agent_id=agent.id, monthly_usd_cap=-1.0, daily_token_cap=None
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_zero_caps_allowed() -> None:
    """Zero caps are recorded as the 'no spend' intent, not enforced
    today (declaration-only until the Budget BC lands)."""
    agent = _agent(AgentStatus.VERSIONED)
    events = decide(
        state=agent,
        command=ReviseAgentBudget(agent_id=agent.id, monthly_usd_cap=0.0, daily_token_cap=0),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].monthly_usd_cap == 0.0
    assert events[0].daily_token_cap == 0
