"""Property-based tests for `suspend_agent.decide` (Agent BC).

Complements the example-based `test_suspend_agent_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition with actor attribution

    (state, command, now, suspended_by) -> list[AgentSuspended]

Load-bearing properties:

  - state=None always raises `AgentNotFoundError` carrying
    command.agent_id.
  - The source-state partition is total over `AgentStatus`: only
    `Versioned` emits exactly one `AgentSuspended` (agent_id=state.id,
    occurred_at=now, suspended_by threaded); every other status raises
    `AgentCannotSuspendError` carrying the current status.
  - The emitted event's agent_id is `state.id`, never command.agent_id.
  - Pure: same (state, command, now, suspended_by) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotSuspendError,
    AgentKind,
    AgentName,
    AgentNotFoundError,
    AgentStatus,
    AgentSuspended,
    AgentVersion,
    ModelRef,
)
from cora.agent.features.suspend_agent.command import SuspendAgent
from cora.agent.features.suspend_agent.decider import decide
from cora.shared.identity import ActorId
from cora.shared.text_bounds import REASON_MAX_LENGTH
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_SUSPENDABLE_SOURCES = (AgentStatus.VERSIONED,)
_DISALLOWED_SOURCES = tuple(s for s in AgentStatus if s not in frozenset(_SUSPENDABLE_SOURCES))


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
@given(
    agent_id=st.uuids(),
    reason=printable_ascii_text(max_size=REASON_MAX_LENGTH),
    now=aware_datetimes(),
    suspended_by_uuid=st.uuids(),
)
def test_suspend_with_none_state_always_raises_not_found(
    agent_id: UUID,
    reason: str,
    now: datetime,
    suspended_by_uuid: UUID,
) -> None:
    """Empty stream always raises `AgentNotFoundError` carrying command.agent_id."""
    with pytest.raises(AgentNotFoundError) as exc:
        decide(
            state=None,
            command=SuspendAgent(agent_id=agent_id, reason=reason),
            now=now,
            suspended_by=ActorId(suspended_by_uuid),
        )
    assert exc.value.agent_id == agent_id


@pytest.mark.unit
@given(
    agent_id=st.uuids(),
    reason=printable_ascii_text(max_size=REASON_MAX_LENGTH),
    now=aware_datetimes(),
    suspended_by_uuid=st.uuids(),
)
def test_suspend_from_versioned_emits_single_event(
    agent_id: UUID,
    reason: str,
    now: datetime,
    suspended_by_uuid: UUID,
) -> None:
    """Versioned is the only suspendable source; emits one AgentSuspended."""
    suspended_by = ActorId(suspended_by_uuid)
    events = decide(
        state=_agent(agent_id=agent_id, status=AgentStatus.VERSIONED),
        command=SuspendAgent(agent_id=agent_id, reason=reason),
        now=now,
        suspended_by=suspended_by,
    )
    assert events == [
        AgentSuspended(
            agent_id=agent_id,
            reason=reason,
            suspended_by=suspended_by,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    agent_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    reason=printable_ascii_text(max_size=REASON_MAX_LENGTH),
    now=aware_datetimes(),
    suspended_by_uuid=st.uuids(),
)
def test_suspend_from_disallowed_source_always_raises_cannot_suspend(
    agent_id: UUID,
    source: AgentStatus,
    reason: str,
    now: datetime,
    suspended_by_uuid: UUID,
) -> None:
    """Any source other than Versioned raises, carrying the current status."""
    with pytest.raises(AgentCannotSuspendError) as exc:
        decide(
            state=_agent(agent_id=agent_id, status=source),
            command=SuspendAgent(agent_id=agent_id, reason=reason),
            now=now,
            suspended_by=ActorId(suspended_by_uuid),
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_agent_id=st.uuids(),
    command_agent_id=st.uuids(),
    reason=printable_ascii_text(max_size=REASON_MAX_LENGTH),
    now=aware_datetimes(),
    suspended_by_uuid=st.uuids(),
)
def test_suspend_uses_state_id_not_command_agent_id(
    state_agent_id: UUID,
    command_agent_id: UUID,
    reason: str,
    now: datetime,
    suspended_by_uuid: UUID,
) -> None:
    """The emitted event's agent_id is state.id, not command.agent_id."""
    assume(state_agent_id != command_agent_id)
    events = decide(
        state=_agent(agent_id=state_agent_id, status=AgentStatus.VERSIONED),
        command=SuspendAgent(agent_id=command_agent_id, reason=reason),
        now=now,
        suspended_by=ActorId(suspended_by_uuid),
    )
    assert events[0].agent_id == state_agent_id


@pytest.mark.unit
@given(
    agent_id=st.uuids(),
    reason=printable_ascii_text(max_size=REASON_MAX_LENGTH),
    now=aware_datetimes(),
    suspended_by_uuid=st.uuids(),
)
def test_suspend_threads_suspended_by_attribution(
    agent_id: UUID,
    reason: str,
    now: datetime,
    suspended_by_uuid: UUID,
) -> None:
    """The injected suspended_by lands on the event payload verbatim."""
    suspended_by = ActorId(suspended_by_uuid)
    events = decide(
        state=_agent(agent_id=agent_id, status=AgentStatus.VERSIONED),
        command=SuspendAgent(agent_id=agent_id, reason=reason),
        now=now,
        suspended_by=suspended_by,
    )
    assert events[0].suspended_by == suspended_by


@pytest.mark.unit
@given(
    agent_id=st.uuids(),
    reason=printable_ascii_text(max_size=REASON_MAX_LENGTH),
    now=aware_datetimes(),
    suspended_by_uuid=st.uuids(),
)
def test_suspend_is_pure_same_input_same_output(
    agent_id: UUID,
    reason: str,
    now: datetime,
    suspended_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _agent(agent_id=agent_id, status=AgentStatus.VERSIONED)
    command = SuspendAgent(agent_id=agent_id, reason=reason)
    suspended_by = ActorId(suspended_by_uuid)
    first = decide(state=state, command=command, now=now, suspended_by=suspended_by)
    second = decide(state=state, command=command, now=now, suspended_by=suspended_by)
    assert first == second
