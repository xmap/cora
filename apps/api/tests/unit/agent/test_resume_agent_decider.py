"""Pure-decider tests for the `resume_agent` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotResumeError,
    AgentKind,
    AgentName,
    AgentNotFoundError,
    AgentResumed,
    AgentStatus,
    AgentVersion,
    ModelRef,
)
from cora.agent.features.resume_agent.command import ResumeAgent
from cora.agent.features.resume_agent.decider import decide
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_RESUMED_BY = ActorId(uuid4())


def _agent(status: AgentStatus, *, agent_id: object | None = None) -> Agent:
    return Agent(
        id=agent_id or uuid4(),  # type: ignore[arg-type]
        kind=AgentKind("RunDebriefer"),
        name=AgentName("Run Debrief"),
        version=AgentVersion("v1"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        status=status,
    )


@pytest.mark.unit
def test_resumes_a_suspended_agent() -> None:
    agent = _agent(AgentStatus.SUSPENDED)
    events = decide(
        state=agent,
        command=ResumeAgent(agent_id=agent.id),
        now=_NOW,
        resumed_by=_RESUMED_BY,
    )
    assert len(events) == 1
    assert isinstance(events[0], AgentResumed)
    assert events[0].resumed_by == _RESUMED_BY
    assert events[0].occurred_at == _NOW


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    with pytest.raises(AgentNotFoundError):
        decide(
            state=None,
            command=ResumeAgent(agent_id=uuid4()),
            now=_NOW,
            resumed_by=_RESUMED_BY,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "status", [AgentStatus.DEFINED, AgentStatus.VERSIONED, AgentStatus.DEPRECATED]
)
def test_cannot_resume_from_non_suspended(status: AgentStatus) -> None:
    agent = _agent(status)
    with pytest.raises(AgentCannotResumeError):
        decide(
            state=agent,
            command=ResumeAgent(agent_id=agent.id),
            now=_NOW,
            resumed_by=_RESUMED_BY,
        )
