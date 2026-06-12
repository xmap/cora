"""Property-based tests for `revoke_tool_from_agent.decide` (Agent BC).

Complements the example-based `test_revoke_tool_from_agent_decider.py`
with universal claims across generated inputs. The decider is a pure
tool-set mutation with idempotent no-op semantics

    (state, command, now) -> list[AgentToolRevoked]

Load-bearing properties:

  - state=None always raises `AgentNotFoundError` carrying
    command.agent_id.
  - The source-state partition is total over `AgentStatus`: every
    non-`Deprecated` status is a permitted source, and `Deprecated`
    always raises `AgentCannotRevokeToolError` carrying the current
    status.
  - Idempotent no-op: revoking a tool not currently granted returns
    `[]` from any permitted source state.
  - Revoking a present tool emits exactly one `AgentToolRevoked` with
    agent_id=state.id, occurred_at=now, and the threaded tool_name.
  - The emitted event's agent_id is `state.id`, never command.agent_id.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotRevokeToolError,
    AgentKind,
    AgentName,
    AgentNotFoundError,
    AgentStatus,
    AgentToolRevoked,
    AgentVersion,
    ModelRef,
    ToolName,
)
from cora.agent.features.revoke_tool_from_agent.command import RevokeToolFromAgent
from cora.agent.features.revoke_tool_from_agent.decider import decide
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_REVOCABLE_SOURCES = tuple(s for s in AgentStatus if s is not AgentStatus.DEPRECATED)
_DISALLOWED_SOURCES = (AgentStatus.DEPRECATED,)

_TOOL_NAME = "read_run"


def _agent(*, agent_id: UUID, status: AgentStatus, tools: frozenset[ToolName]) -> Agent:
    return Agent(
        id=agent_id,
        kind=AgentKind("RunDebriefer"),
        name=AgentName("Run Debrief"),
        version=AgentVersion("v1"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        status=status,
        tools=tools,
    )


def _command(*, agent_id: UUID, tool_name: str) -> RevokeToolFromAgent:
    return RevokeToolFromAgent(agent_id=agent_id, tool_name=tool_name)


@pytest.mark.unit
@given(agent_id=st.uuids(), now=aware_datetimes())
def test_revoke_with_none_state_always_raises_not_found(
    agent_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `AgentNotFoundError` carrying command.agent_id."""
    with pytest.raises(AgentNotFoundError) as exc:
        decide(
            state=None,
            command=_command(agent_id=agent_id, tool_name=_TOOL_NAME),
            now=now,
        )
    assert exc.value.agent_id == agent_id


@pytest.mark.unit
@given(agent_id=st.uuids(), source=st.sampled_from(_REVOCABLE_SOURCES), now=aware_datetimes())
def test_revoke_present_tool_from_permitted_source_emits_single_event(
    agent_id: UUID,
    source: AgentStatus,
    now: datetime,
) -> None:
    """Every non-Deprecated source revoking a held tool emits one event."""
    events = decide(
        state=_agent(agent_id=agent_id, status=source, tools=frozenset({ToolName(_TOOL_NAME)})),
        command=_command(agent_id=agent_id, tool_name=_TOOL_NAME),
        now=now,
    )
    assert events == [AgentToolRevoked(agent_id=agent_id, tool_name=_TOOL_NAME, occurred_at=now)]


@pytest.mark.unit
@given(agent_id=st.uuids(), source=st.sampled_from(_REVOCABLE_SOURCES), now=aware_datetimes())
def test_revoke_absent_tool_is_idempotent_no_op(
    agent_id: UUID,
    source: AgentStatus,
    now: datetime,
) -> None:
    """Revoking a tool not currently granted returns [] from any permitted source."""
    events = decide(
        state=_agent(agent_id=agent_id, status=source, tools=frozenset()),
        command=_command(agent_id=agent_id, tool_name=_TOOL_NAME),
        now=now,
    )
    assert events == []


@pytest.mark.unit
@given(agent_id=st.uuids(), source=st.sampled_from(_DISALLOWED_SOURCES), now=aware_datetimes())
def test_revoke_from_disallowed_source_always_raises_cannot_revoke(
    agent_id: UUID,
    source: AgentStatus,
    now: datetime,
) -> None:
    """Deprecated source always raises, carrying the current status."""
    with pytest.raises(AgentCannotRevokeToolError) as exc:
        decide(
            state=_agent(agent_id=agent_id, status=source, tools=frozenset({ToolName(_TOOL_NAME)})),
            command=_command(agent_id=agent_id, tool_name=_TOOL_NAME),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    tool_name=printable_ascii_text(max_size=100),
    agent_id=st.uuids(),
    source=st.sampled_from(_REVOCABLE_SOURCES),
    now=aware_datetimes(),
)
def test_revoke_present_tool_emits_event_with_state_tool_name(
    tool_name: str,
    agent_id: UUID,
    source: AgentStatus,
    now: datetime,
) -> None:
    """The emitted event carries the trimmed tool_name held in state."""
    held = ToolName(tool_name)
    events = decide(
        state=_agent(agent_id=agent_id, status=source, tools=frozenset({held})),
        command=_command(agent_id=agent_id, tool_name=tool_name),
        now=now,
    )
    assert len(events) == 1
    assert events[0].tool_name == held.value


@pytest.mark.unit
@given(
    state_agent_id=st.uuids(),
    command_agent_id=st.uuids(),
    now=aware_datetimes(),
)
def test_revoke_uses_state_id_not_command_agent_id(
    state_agent_id: UUID,
    command_agent_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's agent_id is state.id, not command.agent_id."""
    assume(state_agent_id != command_agent_id)
    events = decide(
        state=_agent(
            agent_id=state_agent_id,
            status=AgentStatus.VERSIONED,
            tools=frozenset({ToolName(_TOOL_NAME)}),
        ),
        command=_command(agent_id=command_agent_id, tool_name=_TOOL_NAME),
        now=now,
    )
    assert events[0].agent_id == state_agent_id


@pytest.mark.unit
@given(agent_id=st.uuids(), now=aware_datetimes())
def test_revoke_is_pure_same_input_same_output(
    agent_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _agent(
        agent_id=agent_id, status=AgentStatus.VERSIONED, tools=frozenset({ToolName(_TOOL_NAME)})
    )
    command = _command(agent_id=agent_id, tool_name=_TOOL_NAME)
    first = decide(state=state, command=command, now=now)
    second = decide(state=state, command=command, now=now)
    assert first == second
