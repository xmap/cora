"""Pure-decider tests for the `deprecate_agent` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotDeprecateError,
    AgentDeprecated,
    AgentKind,
    AgentName,
    AgentNotFoundError,
    AgentStatus,
    AgentVersion,
    InvalidAgentDeprecationReasonError,
    ModelRef,
)
from cora.agent.features.deprecate_agent.command import DeprecateAgent
from cora.agent.features.deprecate_agent.decider import decide
from cora.shared.text_bounds import REASON_MAX_LENGTH

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)


def _agent(status: AgentStatus, *, agent_id: object | None = None) -> Agent:
    base = Agent(
        id=agent_id or uuid4(),  # type: ignore[arg-type]
        kind=AgentKind("RunDebriefer"),
        name=AgentName("Run Debrief"),
        version=AgentVersion("v1"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        status=status,
    )
    return base


@pytest.mark.unit
def test_deprecates_a_defined_agent_with_reason() -> None:
    agent = _agent(AgentStatus.DEFINED)
    events = decide(
        state=agent, command=DeprecateAgent(agent_id=agent.id, reason="retired"), now=_NOW
    )
    assert len(events) == 1
    assert isinstance(events[0], AgentDeprecated)
    assert events[0].reason == "retired"


@pytest.mark.unit
def test_deprecates_a_versioned_agent_with_no_reason() -> None:
    agent = _agent(AgentStatus.VERSIONED)
    events = decide(state=agent, command=DeprecateAgent(agent_id=agent.id, reason=None), now=_NOW)
    assert events[0].reason is None


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    with pytest.raises(AgentNotFoundError):
        decide(state=None, command=DeprecateAgent(agent_id=uuid4()), now=_NOW)


@pytest.mark.unit
def test_cannot_deprecate_a_deprecated_agent() -> None:
    agent = _agent(AgentStatus.DEPRECATED)
    with pytest.raises(AgentCannotDeprecateError):
        decide(state=agent, command=DeprecateAgent(agent_id=agent.id), now=_NOW)


@pytest.mark.unit
def test_invalid_reason_raises() -> None:
    agent = _agent(AgentStatus.DEFINED)
    with pytest.raises(InvalidAgentDeprecationReasonError):
        decide(
            state=agent,
            command=DeprecateAgent(agent_id=agent.id, reason="x" * (REASON_MAX_LENGTH + 1)),
            now=_NOW,
        )


@pytest.mark.unit
def test_reason_trims_via_value_object() -> None:
    agent = _agent(AgentStatus.DEFINED)
    events = decide(
        state=agent,
        command=DeprecateAgent(agent_id=agent.id, reason="  model retired  "),
        now=_NOW,
    )
    assert events[0].reason == "model retired"
