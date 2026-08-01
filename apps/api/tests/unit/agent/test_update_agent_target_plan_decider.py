"""Pure-decider tests for the `update_agent_target_plan` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

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

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_PLAN_A = uuid4()
_PLAN_B = uuid4()


def _agent(
    status: AgentStatus,
    *,
    target_plan_id: object | None = None,
    agent_id: object | None = None,
) -> Agent:
    return Agent(
        id=agent_id or uuid4(),  # type: ignore[arg-type]
        kind=AgentKind("RunInitiator"),
        name=AgentName("Run Initiator"),
        version=AgentVersion("v1"),
        model_ref=ModelRef(provider="deterministic", model="agent:RunInitiator:v1"),
        status=status,
        target_plan_id=target_plan_id,  # type: ignore[arg-type]
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "status", [AgentStatus.DEFINED, AgentStatus.VERSIONED, AgentStatus.SUSPENDED]
)
def test_sets_target_plan_from_unset_in_each_allowed_source_state(status: AgentStatus) -> None:
    agent = _agent(status)
    events = decide(
        state=agent,
        command=UpdateAgentTargetPlan(agent_id=agent.id, target_plan_id=_PLAN_A),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], AgentTargetPlanUpdated)
    assert events[0].target_plan_id == _PLAN_A
    assert events[0].occurred_at == _NOW


@pytest.mark.unit
def test_changes_target_plan_to_a_different_plan() -> None:
    agent = _agent(AgentStatus.VERSIONED, target_plan_id=_PLAN_A)
    events = decide(
        state=agent,
        command=UpdateAgentTargetPlan(agent_id=agent.id, target_plan_id=_PLAN_B),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].target_plan_id == _PLAN_B


@pytest.mark.unit
def test_clears_target_plan_to_none() -> None:
    agent = _agent(AgentStatus.VERSIONED, target_plan_id=_PLAN_A)
    events = decide(
        state=agent,
        command=UpdateAgentTargetPlan(agent_id=agent.id, target_plan_id=None),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].target_plan_id is None


@pytest.mark.unit
def test_idempotent_set_to_same_plan_emits_no_event() -> None:
    agent = _agent(AgentStatus.VERSIONED, target_plan_id=_PLAN_A)
    events = decide(
        state=agent,
        command=UpdateAgentTargetPlan(agent_id=agent.id, target_plan_id=_PLAN_A),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_idempotent_clear_when_already_unset() -> None:
    agent = _agent(AgentStatus.VERSIONED, target_plan_id=None)
    events = decide(
        state=agent,
        command=UpdateAgentTargetPlan(agent_id=agent.id, target_plan_id=None),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    with pytest.raises(AgentNotFoundError):
        decide(
            state=None,
            command=UpdateAgentTargetPlan(agent_id=uuid4(), target_plan_id=_PLAN_A),
            now=_NOW,
        )


@pytest.mark.unit
def test_cannot_set_when_deprecated() -> None:
    agent = _agent(AgentStatus.DEPRECATED)
    with pytest.raises(AgentCannotUpdateTargetPlanError):
        decide(
            state=agent,
            command=UpdateAgentTargetPlan(agent_id=agent.id, target_plan_id=_PLAN_A),
            now=_NOW,
        )
