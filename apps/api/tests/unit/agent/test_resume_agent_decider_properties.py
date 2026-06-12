"""Property-based tests for `resume_agent.decide` (Agent BC).

Complements the example-based `test_resume_agent_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition with actor attribution

    (state, command, now, resumed_by) -> list[AgentResumed]

Load-bearing properties:

  - state=None always raises `AgentNotFoundError` carrying
    command.agent_id.
  - The source-state partition is total over `AgentStatus`: only
    `Suspended` emits exactly one `AgentResumed` (agent_id=state.id,
    occurred_at=now, resumed_by threaded); every other status raises
    `AgentCannotResumeError` carrying the current status.
  - The emitted event's agent_id is `state.id`, never command.agent_id.
  - Pure: same (state, command, now, resumed_by) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

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
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_RESUMABLE_SOURCES = (AgentStatus.SUSPENDED,)
_DISALLOWED_SOURCES = tuple(s for s in AgentStatus if s not in frozenset(_RESUMABLE_SOURCES))


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
@given(agent_id=st.uuids(), now=aware_datetimes(), resumed_by_uuid=st.uuids())
def test_resume_with_none_state_always_raises_not_found(
    agent_id: UUID,
    now: datetime,
    resumed_by_uuid: UUID,
) -> None:
    """Empty stream always raises `AgentNotFoundError` carrying command.agent_id."""
    with pytest.raises(AgentNotFoundError) as exc:
        decide(
            state=None,
            command=ResumeAgent(agent_id=agent_id),
            now=now,
            resumed_by=ActorId(resumed_by_uuid),
        )
    assert exc.value.agent_id == agent_id


@pytest.mark.unit
@given(agent_id=st.uuids(), now=aware_datetimes(), resumed_by_uuid=st.uuids())
def test_resume_from_suspended_emits_single_event(
    agent_id: UUID,
    now: datetime,
    resumed_by_uuid: UUID,
) -> None:
    """Suspended is the only resumable source; emits one AgentResumed."""
    resumed_by = ActorId(resumed_by_uuid)
    events = decide(
        state=_agent(agent_id=agent_id, status=AgentStatus.SUSPENDED),
        command=ResumeAgent(agent_id=agent_id),
        now=now,
        resumed_by=resumed_by,
    )
    assert events == [AgentResumed(agent_id=agent_id, resumed_by=resumed_by, occurred_at=now)]


@pytest.mark.unit
@given(
    agent_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
    resumed_by_uuid=st.uuids(),
)
def test_resume_from_disallowed_source_always_raises_cannot_resume(
    agent_id: UUID,
    source: AgentStatus,
    now: datetime,
    resumed_by_uuid: UUID,
) -> None:
    """Any source other than Suspended raises, carrying the current status."""
    with pytest.raises(AgentCannotResumeError) as exc:
        decide(
            state=_agent(agent_id=agent_id, status=source),
            command=ResumeAgent(agent_id=agent_id),
            now=now,
            resumed_by=ActorId(resumed_by_uuid),
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_agent_id=st.uuids(),
    command_agent_id=st.uuids(),
    now=aware_datetimes(),
    resumed_by_uuid=st.uuids(),
)
def test_resume_uses_state_id_not_command_agent_id(
    state_agent_id: UUID,
    command_agent_id: UUID,
    now: datetime,
    resumed_by_uuid: UUID,
) -> None:
    """The emitted event's agent_id is state.id, not command.agent_id."""
    assume(state_agent_id != command_agent_id)
    events = decide(
        state=_agent(agent_id=state_agent_id, status=AgentStatus.SUSPENDED),
        command=ResumeAgent(agent_id=command_agent_id),
        now=now,
        resumed_by=ActorId(resumed_by_uuid),
    )
    assert events[0].agent_id == state_agent_id


@pytest.mark.unit
@given(agent_id=st.uuids(), now=aware_datetimes(), resumed_by_uuid=st.uuids())
def test_resume_is_pure_same_input_same_output(
    agent_id: UUID,
    now: datetime,
    resumed_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _agent(agent_id=agent_id, status=AgentStatus.SUSPENDED)
    command = ResumeAgent(agent_id=agent_id)
    resumed_by = ActorId(resumed_by_uuid)
    first = decide(state=state, command=command, now=now, resumed_by=resumed_by)
    second = decide(state=state, command=command, now=now, resumed_by=resumed_by)
    assert first == second
