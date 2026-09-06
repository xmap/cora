"""Property-based tests for `restate_agent_definition.decide` (Agent BC).

Complements the example-based `test_restate_agent_definition_decider.py` with
universal claims across generated inputs. The decider is a pure partial-update
transition with no actor kwarg (the restating identity lives on the event
envelope):

    (state, command, now) -> list[AgentDefinitionRestated]

Load-bearing properties, chosen for what the examples CANNOT cover:

  - state=None always raises `AgentNotFoundError` carrying command.agent_id,
    for every generated command.
  - The source-state partition is total over `AgentStatus`: only `Deprecated`
    is disallowed; `{Defined, Versioned, Suspended}` are all restatable. A
    widened enum lands in one branch or the other rather than falling through.
  - A command naming neither field always raises, whatever the state.
  - The emitted event's agent_id is `state.id`, never `command.agent_id`. The
    two are equal in practice, so an example test cannot distinguish them;
    generating them independently can.
  - Emitted fields are exactly the SUPPLIED ones: an omitted field is None on
    the event, never back-filled from current state. Back-filling would make
    the event claim the caller restated something they never mentioned.
  - Pure: the same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotRestateDefinitionError,
    AgentKind,
    AgentName,
    AgentNotFoundError,
    AgentStatus,
    AgentVersion,
    BrainRef,
    InvalidAgentDefinitionRestatementError,
    ModelRef,
)
from cora.agent.features.restate_agent_definition.command import RestateAgentDefinition
from cora.agent.features.restate_agent_definition.decider import decide
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_NAMES = st.text(min_size=1, max_size=40).filter(lambda s: bool(s.strip()))
_RULES = st.text(min_size=1, max_size=40).filter(lambda s: bool(s.strip()))
_REASONS = st.text(min_size=1, max_size=60).filter(lambda s: bool(s.strip()))


def _agent(status: AgentStatus, *, name: str = "Seeded Agent", rule: str = "Seeded:v1") -> Agent:
    return Agent(
        id=uuid4(),
        kind=AgentKind("ProcedureWatcher"),
        name=AgentName(name),
        version=AgentVersion("1.0.0"),
        model_ref=ModelRef(provider="deterministic", model="agent:ProcedureWatcher:v1"),
        brain=BrainRef.for_rule(rule),
        status=status,
    )


@given(reason=_REASONS, name=_NAMES, now=aware_datetimes())
def test_absent_state_always_raises_not_found(reason: str, name: str, now: datetime) -> None:
    agent_id = uuid4()
    with pytest.raises(AgentNotFoundError):
        decide(None, RestateAgentDefinition(agent_id, reason, name=name), now=now)


@given(status=st.sampled_from(AgentStatus), reason=_REASONS, name=_NAMES, now=aware_datetimes())
def test_the_status_partition_is_total(
    status: AgentStatus, reason: str, name: str, now: datetime
) -> None:
    """Every status lands in exactly one branch: refused or restated."""
    state = _agent(status)
    command = RestateAgentDefinition(state.id, reason, name=name)

    if status is AgentStatus.DEPRECATED:
        with pytest.raises(AgentCannotRestateDefinitionError):
            decide(state, command, now=now)
        return

    events = decide(state, command, now=now)
    assert len(events) <= 1


@given(status=st.sampled_from(AgentStatus), reason=_REASONS, now=aware_datetimes())
def test_restating_neither_field_always_raises(
    status: AgentStatus, reason: str, now: datetime
) -> None:
    state = _agent(status)
    command = RestateAgentDefinition(state.id, reason)

    with pytest.raises((AgentCannotRestateDefinitionError, InvalidAgentDefinitionRestatementError)):
        decide(state, command, now=now)


@given(reason=_REASONS, rule=_RULES, now=aware_datetimes())
def test_the_event_carries_state_id_not_command_id(reason: str, rule: str, now: datetime) -> None:
    """Equal in practice, so only generated-apart ids can tell them apart."""
    state = _agent(AgentStatus.VERSIONED, rule="Seeded:v1")
    other_id = uuid4()
    command = RestateAgentDefinition(other_id, reason, brain=BrainRef.for_rule(rule + "x"))

    events = decide(state, command, now=now)

    assert len(events) == 1
    assert events[0].agent_id == state.id


@given(reason=_REASONS, rule=_RULES, now=aware_datetimes())
def test_an_omitted_field_is_never_back_filled(reason: str, rule: str, now: datetime) -> None:
    """A brain-only restatement must not claim a name was restated too."""
    state = _agent(AgentStatus.VERSIONED, name="Original Name", rule="Seeded:v1")
    command = RestateAgentDefinition(state.id, reason, brain=BrainRef.for_rule(rule + "x"))

    events = decide(state, command, now=now)

    assert len(events) == 1
    assert events[0].name is None


@given(reason=_REASONS, name=_NAMES, now=aware_datetimes())
def test_decide_is_pure(reason: str, name: str, now: datetime) -> None:
    state = _agent(AgentStatus.VERSIONED)
    command = RestateAgentDefinition(state.id, reason, name=name)

    assert decide(state, command, now=now) == decide(state, command, now=now)
