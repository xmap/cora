"""Property-based tests for `version_agent.decide` (Agent BC).

Complements the example-based `test_version_agent_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, now) -> list[AgentVersioned]

Load-bearing properties:

  - state=None always raises `AgentNotFoundError` carrying command.agent_id.
  - The source-state partition is total over `AgentStatus`: only
    `Defined` emits exactly one `AgentVersioned` (agent_id=state.id,
    occurred_at=now); every other status raises `AgentCannotVersionError`
    carrying the current status, so a future status value cannot
    silently fall through.
  - The emitted event's agent_id is `state.id`, never `command.agent_id`,
    and its version is threaded from `state.version.value`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotVersionError,
    AgentKind,
    AgentName,
    AgentNotFoundError,
    AgentStatus,
    AgentVersion,
    AgentVersioned,
    ModelRef,
)
from cora.agent.features.version_agent.command import VersionAgent
from cora.agent.features.version_agent.decider import decide
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_VERSIONABLE_SOURCES = (AgentStatus.DEFINED,)
_DISALLOWED_SOURCES = tuple(s for s in AgentStatus if s not in frozenset(_VERSIONABLE_SOURCES))


def _agent(*, agent_id: UUID, status: AgentStatus, version: str = "v1") -> Agent:
    return Agent(
        id=agent_id,
        kind=AgentKind("RunDebriefer"),
        name=AgentName("Run Debrief"),
        version=AgentVersion(version),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        status=status,
    )


@pytest.mark.unit
@given(agent_id=st.uuids(), now=aware_datetimes())
def test_version_with_none_state_always_raises_not_found(
    agent_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `AgentNotFoundError` carrying command.agent_id."""
    with pytest.raises(AgentNotFoundError) as exc:
        decide(state=None, command=VersionAgent(agent_id=agent_id), now=now)
    assert exc.value.agent_id == agent_id


@pytest.mark.unit
@given(agent_id=st.uuids(), now=aware_datetimes())
def test_version_from_defined_emits_single_event(agent_id: UUID, now: datetime) -> None:
    """Defined is the only versionable source; emits one AgentVersioned."""
    events = decide(
        state=_agent(agent_id=agent_id, status=AgentStatus.DEFINED),
        command=VersionAgent(agent_id=agent_id),
        now=now,
    )
    assert events == [AgentVersioned(agent_id=agent_id, version="v1", occurred_at=now)]


@pytest.mark.unit
@given(
    agent_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_version_from_disallowed_source_always_raises_cannot_version(
    agent_id: UUID,
    source: AgentStatus,
    now: datetime,
) -> None:
    """Any source other than Defined raises, carrying the current status."""
    with pytest.raises(AgentCannotVersionError) as exc:
        decide(
            state=_agent(agent_id=agent_id, status=source),
            command=VersionAgent(agent_id=agent_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_agent_id=st.uuids(), command_agent_id=st.uuids(), now=aware_datetimes())
def test_version_uses_state_id_not_command_agent_id(
    state_agent_id: UUID,
    command_agent_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's agent_id is state.id, not command.agent_id."""
    assume(state_agent_id != command_agent_id)
    events = decide(
        state=_agent(agent_id=state_agent_id, status=AgentStatus.DEFINED),
        command=VersionAgent(agent_id=command_agent_id),
        now=now,
    )
    assert events[0].agent_id == state_agent_id


@pytest.mark.unit
@given(
    agent_id=st.uuids(),
    version=printable_ascii_text(max_size=50),
    now=aware_datetimes(),
)
def test_version_threads_state_version_onto_event(
    agent_id: UUID,
    version: str,
    now: datetime,
) -> None:
    """The emitted event's version is threaded from state.version.value."""
    events = decide(
        state=_agent(agent_id=agent_id, status=AgentStatus.DEFINED, version=version),
        command=VersionAgent(agent_id=agent_id),
        now=now,
    )
    assert events[0].version == version


@pytest.mark.unit
@given(agent_id=st.uuids(), now=aware_datetimes())
def test_version_is_pure_same_input_same_output(agent_id: UUID, now: datetime) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _agent(agent_id=agent_id, status=AgentStatus.DEFINED)
    command = VersionAgent(agent_id=agent_id)
    first = decide(state=state, command=command, now=now)
    second = decide(state=state, command=command, now=now)
    assert first == second
