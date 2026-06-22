"""Property-based tests for `update_agent_budget.decide` (Agent BC).

Complements the example-based `test_update_agent_budget_decider.py` with
universal claims across generated inputs. The decider is a pure
budget-update transition with PUT semantics and no actor kwarg
(updating identity lives on the event envelope)

    (state, command, now) -> list[AgentBudgetUpdated]

Load-bearing properties:

  - state=None always raises `AgentNotFoundError` carrying
    command.agent_id.
  - The source-state partition is total over `AgentStatus`: only
    `Deprecated` is disallowed, raising `AgentCannotUpdateBudgetError`
    carrying the current status; `{Defined, Versioned, Suspended}` are
    updatable.
  - From a updatable source, a budget change emits exactly one
    `AgentBudgetUpdated` (agent_id=state.id, occurred_at=now, caps
    threaded from the command).
  - The emitted event's agent_id is `state.id`, never command.agent_id.
  - Idempotent: updating to the budget the Agent already holds returns
    `[]`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.agent.aggregates.agent import (
    Agent,
    AgentBudget,
    AgentBudgetUpdated,
    AgentCannotUpdateBudgetError,
    AgentKind,
    AgentName,
    AgentNotFoundError,
    AgentStatus,
    AgentVersion,
    ModelRef,
)
from cora.agent.features.update_agent_budget.command import UpdateAgentBudget
from cora.agent.features.update_agent_budget.decider import decide
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_UPDATABLE_SOURCES = (
    AgentStatus.DEFINED,
    AgentStatus.VERSIONED,
    AgentStatus.SUSPENDED,
)
_DISALLOWED_SOURCES = tuple(s for s in AgentStatus if s not in frozenset(_UPDATABLE_SOURCES))

_VALID_MONTHLY_CAP = 100.0
_VALID_DAILY_CAP = 1_000_000


def _agent(
    status: AgentStatus,
    *,
    budget: AgentBudget | None = None,
    agent_id: object | None = None,
) -> Agent:
    return Agent(
        id=agent_id or uuid4(),  # type: ignore[arg-type]
        kind=AgentKind("RunDebriefer"),
        name=AgentName("Run Debrief"),
        version=AgentVersion("v1"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        status=status,
        budget=budget,
    )


@pytest.mark.unit
@given(agent_id=st.uuids(), now=aware_datetimes())
def test_update_budget_with_none_state_always_raises_not_found(
    agent_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `AgentNotFoundError` carrying command.agent_id."""
    with pytest.raises(AgentNotFoundError) as exc:
        decide(
            state=None,
            command=UpdateAgentBudget(
                agent_id=agent_id,
                monthly_usd_cap=_VALID_MONTHLY_CAP,
                daily_token_cap=_VALID_DAILY_CAP,
            ),
            now=now,
        )
    assert exc.value.agent_id == agent_id


@pytest.mark.unit
@given(
    agent_id=st.uuids(),
    source=st.sampled_from(_UPDATABLE_SOURCES),
    now=aware_datetimes(),
)
def test_update_budget_from_updatable_source_emits_single_event(
    agent_id: UUID,
    source: AgentStatus,
    now: datetime,
) -> None:
    """Each updatable source emits one AgentBudgetUpdated with threaded caps."""
    events = decide(
        state=_agent(source, agent_id=agent_id),
        command=UpdateAgentBudget(
            agent_id=agent_id,
            monthly_usd_cap=_VALID_MONTHLY_CAP,
            daily_token_cap=_VALID_DAILY_CAP,
        ),
        now=now,
    )
    assert events == [
        AgentBudgetUpdated(
            agent_id=agent_id,
            monthly_usd_cap=_VALID_MONTHLY_CAP,
            daily_token_cap=_VALID_DAILY_CAP,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    agent_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_update_budget_from_disallowed_source_always_raises_cannot_update(
    agent_id: UUID,
    source: AgentStatus,
    now: datetime,
) -> None:
    """Any source other than the updatable set raises, carrying the current status."""
    with pytest.raises(AgentCannotUpdateBudgetError) as exc:
        decide(
            state=_agent(source, agent_id=agent_id),
            command=UpdateAgentBudget(
                agent_id=agent_id,
                monthly_usd_cap=_VALID_MONTHLY_CAP,
                daily_token_cap=_VALID_DAILY_CAP,
            ),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_agent_id=st.uuids(),
    command_agent_id=st.uuids(),
    now=aware_datetimes(),
)
def test_update_budget_uses_state_id_not_command_agent_id(
    state_agent_id: UUID,
    command_agent_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's agent_id is state.id, not command.agent_id."""
    assume(state_agent_id != command_agent_id)
    events = decide(
        state=_agent(AgentStatus.VERSIONED, agent_id=state_agent_id),
        command=UpdateAgentBudget(
            agent_id=command_agent_id,
            monthly_usd_cap=_VALID_MONTHLY_CAP,
            daily_token_cap=_VALID_DAILY_CAP,
        ),
        now=now,
    )
    assert events[0].agent_id == state_agent_id


@pytest.mark.unit
@given(
    agent_id=st.uuids(),
    source=st.sampled_from(_UPDATABLE_SOURCES),
    now=aware_datetimes(),
)
def test_update_budget_to_current_budget_emits_no_event(
    agent_id: UUID,
    source: AgentStatus,
    now: datetime,
) -> None:
    """Updating to the budget the Agent already holds is an idempotent no-op."""
    budget = AgentBudget(
        monthly_usd_cap=_VALID_MONTHLY_CAP,
        daily_token_cap=_VALID_DAILY_CAP,
    )
    events = decide(
        state=_agent(source, budget=budget, agent_id=agent_id),
        command=UpdateAgentBudget(
            agent_id=agent_id,
            monthly_usd_cap=_VALID_MONTHLY_CAP,
            daily_token_cap=_VALID_DAILY_CAP,
        ),
        now=now,
    )
    assert events == []


@pytest.mark.unit
@given(
    agent_id=st.uuids(),
    source=st.sampled_from(_UPDATABLE_SOURCES),
    now=aware_datetimes(),
)
def test_update_budget_clear_when_already_cleared_emits_no_event(
    agent_id: UUID,
    source: AgentStatus,
    now: datetime,
) -> None:
    """Clearing an already-cleared budget is an idempotent no-op."""
    events = decide(
        state=_agent(source, budget=None, agent_id=agent_id),
        command=UpdateAgentBudget(
            agent_id=agent_id,
            monthly_usd_cap=None,
            daily_token_cap=None,
        ),
        now=now,
    )
    assert events == []


@pytest.mark.unit
@given(agent_id=st.uuids(), now=aware_datetimes())
def test_update_budget_is_pure_same_input_same_output(
    agent_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _agent(AgentStatus.VERSIONED, agent_id=agent_id)
    command = UpdateAgentBudget(
        agent_id=agent_id,
        monthly_usd_cap=_VALID_MONTHLY_CAP,
        daily_token_cap=_VALID_DAILY_CAP,
    )
    first = decide(state=state, command=command, now=now)
    second = decide(state=state, command=command, now=now)
    assert first == second
