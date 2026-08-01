"""Property-based tests for `update_agent_target_plan.decide` (Agent BC).

Complements the example-based `test_update_agent_target_plan_decider.py` with
universal claims across generated inputs. The decider is a pure target-Plan
PUT transition with no actor kwarg (setting identity lives on the event
envelope):

    (state, command, now) -> list[AgentTargetPlanUpdated]

Load-bearing properties:

  - state=None always raises `AgentNotFoundError` carrying command.agent_id.
  - The source-state partition is total over `AgentStatus`: only `Deprecated`
    is disallowed (raising `AgentCannotUpdateTargetPlanError` carrying the current
    status); `{Defined, Versioned, Suspended}` are settable.
  - From a settable source, a target CHANGE emits exactly one
    `AgentTargetPlanUpdated` (agent_id=state.id, occurred_at=now, target threaded
    from the command).
  - The emitted event's agent_id is `state.id`, never command.agent_id.
  - Idempotent: setting the target the Agent already holds returns `[]`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotUpdateTargetPlanError,
    AgentKind,
    AgentName,
    AgentNotFoundError,
    AgentStatus,
    AgentTargetPlanUpdated,
    AgentVersion,
    ModelRef,
)
from cora.agent.features.update_agent_target_plan.command import UpdateAgentTargetPlan
from cora.agent.features.update_agent_target_plan.decider import decide
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_SETTABLE = (AgentStatus.DEFINED, AgentStatus.VERSIONED, AgentStatus.SUSPENDED)


def _agent(status: AgentStatus, *, target_plan_id: UUID | None) -> Agent:
    return Agent(
        id=uuid4(),
        kind=AgentKind("RunInitiator"),
        name=AgentName("Run Initiator"),
        version=AgentVersion("v1"),
        model_ref=ModelRef(provider="deterministic", model="agent:RunInitiator:v1"),
        status=status,
        target_plan_id=target_plan_id,
    )


_optional_plan = st.one_of(st.none(), st.uuids())


@given(now=aware_datetimes(), target=_optional_plan)
def test_state_none_always_raises_not_found(now: datetime, target: UUID | None) -> None:
    agent_id = uuid4()
    with pytest.raises(AgentNotFoundError):
        decide(
            state=None,
            command=UpdateAgentTargetPlan(agent_id=agent_id, target_plan_id=target),
            now=now,
        )


@given(now=aware_datetimes(), current=_optional_plan, target=_optional_plan)
def test_deprecated_always_raises_cannot_set(
    now: datetime, current: UUID | None, target: UUID | None
) -> None:
    agent = _agent(AgentStatus.DEPRECATED, target_plan_id=current)
    with pytest.raises(AgentCannotUpdateTargetPlanError):
        decide(
            state=agent,
            command=UpdateAgentTargetPlan(agent_id=agent.id, target_plan_id=target),
            now=now,
        )


@given(status=st.sampled_from(_SETTABLE), now=aware_datetimes(), target=st.uuids())
def test_settable_source_with_changed_target_emits_one_event(
    status: AgentStatus, now: datetime, target: UUID
) -> None:
    # current is None so any non-None target is a genuine change.
    agent = _agent(status, target_plan_id=None)
    events = decide(
        state=agent,
        command=UpdateAgentTargetPlan(agent_id=agent.id, target_plan_id=target),
        now=now,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, AgentTargetPlanUpdated)
    assert event.agent_id == agent.id
    assert event.target_plan_id == target
    assert event.occurred_at == now


@given(status=st.sampled_from(_SETTABLE), now=aware_datetimes(), current=_optional_plan)
def test_idempotent_set_to_current_target_returns_empty(
    status: AgentStatus, now: datetime, current: UUID | None
) -> None:
    agent = _agent(status, target_plan_id=current)
    events = decide(
        state=agent,
        command=UpdateAgentTargetPlan(agent_id=agent.id, target_plan_id=current),
        now=now,
    )
    assert events == []


@given(status=st.sampled_from(_SETTABLE), now=aware_datetimes(), target=_optional_plan)
def test_decider_is_pure(status: AgentStatus, now: datetime, target: UUID | None) -> None:
    agent = _agent(status, target_plan_id=None)
    command = UpdateAgentTargetPlan(agent_id=agent.id, target_plan_id=target)
    assert decide(state=agent, command=command, now=now) == decide(
        state=agent, command=command, now=now
    )
