"""Property-based tests for `deprecate_agent.decide` (Agent BC).

Complements the example-based `test_deprecate_agent_decider.py` with
universal claims across generated inputs. The decider is a pure
single-command FSM terminal

    (state, command, now) -> list[AgentDeprecated]

Load-bearing properties:

  - state=None always raises `AgentNotFoundError` carrying command.agent_id.
  - The source-state partition is total over `AgentStatus`: every
    status in `{Defined, Versioned, Suspended}` emits exactly one
    `AgentDeprecated` (agent_id=state.id, occurred_at=now); every other
    status raises `AgentCannotDeprecateError` carrying the current
    status, so a future status value cannot silently fall through.
  - The emitted event's agent_id is `state.id`, never `command.agent_id`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotDeprecateError,
    AgentDeprecated,
    AgentKind,
    AgentName,
    AgentNotFoundError,
    AgentStatus,
    AgentVersion,
    ModelRef,
)
from cora.agent.features.deprecate_agent.command import DeprecateAgent
from cora.agent.features.deprecate_agent.decider import decide
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_REASON_MAX = 500

_DEPRECATABLE_SOURCES = (
    AgentStatus.DEFINED,
    AgentStatus.VERSIONED,
    AgentStatus.SUSPENDED,
)
_DISALLOWED_SOURCES = tuple(s for s in AgentStatus if s not in frozenset(_DEPRECATABLE_SOURCES))


def _agent(*, agent_id: UUID, status: AgentStatus) -> Agent:
    return Agent(
        id=agent_id,
        kind=AgentKind("RunDebriefer"),
        name=AgentName("Run Debrief"),
        version=AgentVersion("v1"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        status=status,
    )


@pytest.mark.unit
@given(agent_id=st.uuids(), now=aware_datetimes())
def test_deprecate_with_none_state_always_raises_not_found(
    agent_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `AgentNotFoundError` carrying command.agent_id."""
    with pytest.raises(AgentNotFoundError) as exc:
        decide(state=None, command=DeprecateAgent(agent_id=agent_id), now=now)
    assert exc.value.agent_id == agent_id


@pytest.mark.unit
@given(
    agent_id=st.uuids(),
    source=st.sampled_from(_DEPRECATABLE_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_from_permitted_source_emits_single_event(
    agent_id: UUID,
    source: AgentStatus,
    now: datetime,
) -> None:
    """Every permitted source emits exactly one AgentDeprecated with state.id."""
    events = decide(
        state=_agent(agent_id=agent_id, status=source),
        command=DeprecateAgent(agent_id=agent_id),
        now=now,
    )
    assert events == [AgentDeprecated(agent_id=agent_id, reason=None, occurred_at=now)]


@pytest.mark.unit
@given(
    agent_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_from_disallowed_source_always_raises_cannot_deprecate(
    agent_id: UUID,
    source: AgentStatus,
    now: datetime,
) -> None:
    """Any source outside the permitted set raises, carrying the current status."""
    with pytest.raises(AgentCannotDeprecateError) as exc:
        decide(
            state=_agent(agent_id=agent_id, status=source),
            command=DeprecateAgent(agent_id=agent_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    agent_id=st.uuids(),
    source=st.sampled_from(_DEPRECATABLE_SOURCES),
    reason=printable_ascii_text(max_size=_REASON_MAX),
    now=aware_datetimes(),
)
def test_deprecate_threads_reason_through_trimmed(
    agent_id: UUID,
    source: AgentStatus,
    reason: str,
    now: datetime,
) -> None:
    """A valid reason threads through to the event after VO trimming."""
    events = decide(
        state=_agent(agent_id=agent_id, status=source),
        command=DeprecateAgent(agent_id=agent_id, reason=reason),
        now=now,
    )
    assert events[0].reason == reason.strip()


@pytest.mark.unit
@given(state_agent_id=st.uuids(), command_agent_id=st.uuids(), now=aware_datetimes())
def test_deprecate_uses_state_id_not_command_agent_id(
    state_agent_id: UUID,
    command_agent_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's agent_id is state.id, not command.agent_id."""
    assume(state_agent_id != command_agent_id)
    events = decide(
        state=_agent(agent_id=state_agent_id, status=AgentStatus.DEFINED),
        command=DeprecateAgent(agent_id=command_agent_id),
        now=now,
    )
    assert events[0].agent_id == state_agent_id


@pytest.mark.unit
@given(agent_id=st.uuids(), now=aware_datetimes())
def test_deprecate_is_pure_same_input_same_output(agent_id: UUID, now: datetime) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _agent(agent_id=agent_id, status=AgentStatus.DEFINED)
    command = DeprecateAgent(agent_id=agent_id)
    first = decide(state=state, command=command, now=now)
    second = decide(state=state, command=command, now=now)
    assert first == second
