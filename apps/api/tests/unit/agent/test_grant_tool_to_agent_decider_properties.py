"""Property-based tests for `grant_tool_to_agent.decide` (Agent BC).

Complements the example-based `test_grant_tool_to_agent_decider.py` with
universal claims across generated inputs. The decider is a pure tool-set
mutation that is IDEMPOTENT

    (state, command, now) -> list[AgentToolGranted]

Load-bearing properties:

  - state=None always raises `AgentNotFoundError` carrying
    command.agent_id (existence guard precedes every other check).
  - The source-state partition is total over `AgentStatus`: granting a
    fresh tool from `{Defined, Versioned, Suspended}` emits exactly one
    `AgentToolGranted` (agent_id=state.id, tool_name threaded,
    occurred_at=now); `Deprecated` always raises
    `AgentCannotGrantToolError` carrying the current status.
  - Idempotent no-op: granting an already-present tool returns `[]`
    regardless of source status, with no cap check.
  - The emitted event's agent_id is `state.id`, never command.agent_id.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.agent.aggregates.agent import (
    AGENT_TOOL_NAME_MAX_LENGTH,
    Agent,
    AgentCannotGrantToolError,
    AgentKind,
    AgentName,
    AgentNotFoundError,
    AgentStatus,
    AgentToolGranted,
    AgentVersion,
    ModelRef,
    ToolName,
)
from cora.agent.features.grant_tool_to_agent.command import GrantToolToAgent
from cora.agent.features.grant_tool_to_agent.decider import decide
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_ALLOWED_SOURCES = (
    AgentStatus.DEFINED,
    AgentStatus.VERSIONED,
    AgentStatus.SUSPENDED,
)
_DISALLOWED_SOURCES = tuple(s for s in AgentStatus if s not in frozenset(_ALLOWED_SOURCES))

_tool_names = printable_ascii_text(max_size=AGENT_TOOL_NAME_MAX_LENGTH)


def _agent(
    *,
    agent_id: UUID,
    status: AgentStatus,
    tools: frozenset[ToolName] = frozenset(),
) -> Agent:
    return Agent(
        id=agent_id,
        kind=AgentKind("RunDebriefer"),
        name=AgentName("Run Debrief"),
        version=AgentVersion("v1"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        status=status,
        tools=tools,
    )


@pytest.mark.unit
@given(agent_id=st.uuids(), tool_name=_tool_names, now=aware_datetimes())
def test_grant_with_none_state_always_raises_not_found(
    agent_id: UUID,
    tool_name: str,
    now: datetime,
) -> None:
    """Empty stream always raises `AgentNotFoundError` carrying command.agent_id."""
    with pytest.raises(AgentNotFoundError) as exc:
        decide(
            state=None,
            command=GrantToolToAgent(agent_id=agent_id, tool_name=tool_name),
            now=now,
        )
    assert exc.value.agent_id == agent_id


@pytest.mark.unit
@given(
    agent_id=st.uuids(),
    source=st.sampled_from(_ALLOWED_SOURCES),
    tool_name=_tool_names,
    now=aware_datetimes(),
)
def test_grant_fresh_tool_from_allowed_source_emits_single_event(
    agent_id: UUID,
    source: AgentStatus,
    tool_name: str,
    now: datetime,
) -> None:
    """A fresh tool from any allowed source emits one AgentToolGranted."""
    events = decide(
        state=_agent(agent_id=agent_id, status=source),
        command=GrantToolToAgent(agent_id=agent_id, tool_name=tool_name),
        now=now,
    )
    assert events == [
        AgentToolGranted(
            agent_id=agent_id,
            tool_name=ToolName(tool_name).value,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    agent_id=st.uuids(),
    source=st.sampled_from(_ALLOWED_SOURCES),
    tool_name=_tool_names,
    now=aware_datetimes(),
)
def test_grant_already_present_tool_is_idempotent_no_op(
    agent_id: UUID,
    source: AgentStatus,
    tool_name: str,
    now: datetime,
) -> None:
    """Granting an already-present tool returns [] from any allowed source."""
    existing = ToolName(tool_name)
    events = decide(
        state=_agent(agent_id=agent_id, status=source, tools=frozenset({existing})),
        command=GrantToolToAgent(agent_id=agent_id, tool_name=tool_name),
        now=now,
    )
    assert events == []


@pytest.mark.unit
@given(
    agent_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    tool_name=_tool_names,
    now=aware_datetimes(),
)
def test_grant_from_disallowed_source_always_raises_cannot_grant(
    agent_id: UUID,
    source: AgentStatus,
    tool_name: str,
    now: datetime,
) -> None:
    """Any source other than the allowed set raises, carrying the current status."""
    with pytest.raises(AgentCannotGrantToolError) as exc:
        decide(
            state=_agent(agent_id=agent_id, status=source),
            command=GrantToolToAgent(agent_id=agent_id, tool_name=tool_name),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_agent_id=st.uuids(),
    command_agent_id=st.uuids(),
    tool_name=_tool_names,
    now=aware_datetimes(),
)
def test_grant_uses_state_id_not_command_agent_id(
    state_agent_id: UUID,
    command_agent_id: UUID,
    tool_name: str,
    now: datetime,
) -> None:
    """The emitted event's agent_id is state.id, not command.agent_id."""
    assume(state_agent_id != command_agent_id)
    events = decide(
        state=_agent(agent_id=state_agent_id, status=AgentStatus.VERSIONED),
        command=GrantToolToAgent(agent_id=command_agent_id, tool_name=tool_name),
        now=now,
    )
    assert events[0].agent_id == state_agent_id


@pytest.mark.unit
@given(agent_id=st.uuids(), tool_name=_tool_names, now=aware_datetimes())
def test_grant_is_pure_same_input_same_output(
    agent_id: UUID,
    tool_name: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _agent(agent_id=agent_id, status=AgentStatus.VERSIONED)
    command = GrantToolToAgent(agent_id=agent_id, tool_name=tool_name)
    first = decide(state=state, command=command, now=now)
    second = decide(state=state, command=command, now=now)
    assert first == second
