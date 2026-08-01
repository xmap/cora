"""Pure-decider tests for the `revoke_tool_from_agent` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotRevokeToolError,
    AgentKind,
    AgentName,
    AgentNotFoundError,
    AgentStatus,
    AgentToolRevoked,
    AgentVersion,
    InvalidToolNameError,
    ModelRef,
    ToolName,
)
from cora.agent.features.revoke_tool_from_agent.command import RevokeToolFromAgent
from cora.agent.features.revoke_tool_from_agent.decider import decide

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _agent(
    status: AgentStatus,
    *,
    tools: frozenset[ToolName] = frozenset(),
    agent_id: object | None = None,
) -> Agent:
    return Agent(
        id=agent_id or uuid4(),  # type: ignore[arg-type]
        kind=AgentKind("RunDebriefer"),
        name=AgentName("Run Debrief"),
        version=AgentVersion("v1"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        status=status,
        tools=tools,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "status", [AgentStatus.DEFINED, AgentStatus.VERSIONED, AgentStatus.SUSPENDED]
)
def test_revokes_an_existing_tool_in_each_allowed_source_state(
    status: AgentStatus,
) -> None:
    agent = _agent(status, tools=frozenset({ToolName("read_run")}))
    events = decide(
        state=agent,
        command=RevokeToolFromAgent(
            reason="tool no longer needed", agent_id=agent.id, tool_name="read_run"
        ),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], AgentToolRevoked)
    assert events[0].tool_name == "read_run"


@pytest.mark.unit
def test_idempotent_revoke_of_non_granted_emits_no_event() -> None:
    agent = _agent(AgentStatus.VERSIONED, tools=frozenset())
    events = decide(
        state=agent,
        command=RevokeToolFromAgent(
            reason="tool no longer needed", agent_id=agent.id, tool_name="read_run"
        ),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    with pytest.raises(AgentNotFoundError):
        decide(
            state=None,
            command=RevokeToolFromAgent(
                reason="tool no longer needed", agent_id=uuid4(), tool_name="read_run"
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_cannot_revoke_when_deprecated() -> None:
    agent = _agent(AgentStatus.DEPRECATED, tools=frozenset({ToolName("read_run")}))
    with pytest.raises(AgentCannotRevokeToolError):
        decide(
            state=agent,
            command=RevokeToolFromAgent(
                reason="tool no longer needed", agent_id=agent.id, tool_name="read_run"
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_invalid_tool_name_raises() -> None:
    agent = _agent(AgentStatus.VERSIONED)
    with pytest.raises(InvalidToolNameError):
        decide(
            state=agent,
            command=RevokeToolFromAgent(
                reason="tool no longer needed", agent_id=agent.id, tool_name="   "
            ),
            now=_NOW,
        )
