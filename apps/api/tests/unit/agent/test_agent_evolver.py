"""Evolver tests for the Agent aggregate."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cora.agent.aggregates.agent.events import (
    AgentBudgetUpdated,
    AgentDefined,
    AgentDeprecated,
    AgentResumed,
    AgentSuspended,
    AgentToolGranted,
    AgentToolRevoked,
    AgentVersioned,
)
from cora.agent.aggregates.agent.evolver import fold
from cora.agent.aggregates.agent.state import (
    AgentBudget,
    AgentCapability,
    AgentStatus,
    ModelRef,
    ToolName,
)
from cora.shared.identity import ActorId

_SUSPENDED_BY = ActorId(uuid4())
_RESUMED_BY = ActorId(uuid4())

_T0 = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_T1 = _T0 + timedelta(minutes=10)
_T2 = _T0 + timedelta(minutes=20)


def _genesis(*, agent_id: object | None = None) -> AgentDefined:
    return AgentDefined(
        agent_id=agent_id or uuid4(),  # type: ignore[arg-type]
        kind="RunDebriefer",
        name="Run Debrief",
        version="v1",
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        description="Synthesises terminal Runs.",
        canonical_uri="https://example.org/agents/run-debrief",
        prompt_template_id=None,
        capabilities=frozenset({"summarize"}),
        occurred_at=_T0,
    )


@pytest.mark.unit
def test_empty_stream_folds_to_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_genesis_folds_to_defined_state() -> None:
    e = _genesis()
    state = fold([e])
    assert state is not None
    assert state.id == e.agent_id
    assert state.status is AgentStatus.DEFINED
    assert state.kind.value == "RunDebriefer"
    assert state.name.value == "Run Debrief"
    assert state.version.value == "v1"
    assert state.description is not None
    assert state.description.value == "Synthesises terminal Runs."
    assert state.canonical_uri is not None
    assert state.capabilities == frozenset({AgentCapability("summarize")})
    # Lifecycle timestamps moved to projection; no longer on state.


@pytest.mark.unit
def test_genesis_then_versioned_folds_to_versioned_state() -> None:
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentVersioned(agent_id=agent_id, version="v1", occurred_at=_T1)
    state = fold([e1, e2])
    assert state is not None
    assert state.status is AgentStatus.VERSIONED
    # Other fields preserved.
    assert state.kind.value == "RunDebriefer"
    # Lifecycle timestamps live on the projection; status flip is
    # the assertion that survives at the state level.


@pytest.mark.unit
def test_genesis_then_deprecated_folds_to_deprecated_state() -> None:
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentDeprecated(agent_id=agent_id, reason="model retired", occurred_at=_T1)
    state = fold([e1, e2])
    assert state is not None
    assert state.status is AgentStatus.DEPRECATED
    # Lifecycle timestamps moved to projection.
    assert state.deprecation_reason is not None
    assert state.deprecation_reason.value == "model retired"


@pytest.mark.unit
def test_full_lifecycle_folds_to_deprecated_state() -> None:
    """Genesis -> Versioned -> Deprecated; all three transitions fold."""
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentVersioned(agent_id=agent_id, version="v1", occurred_at=_T1)
    e3 = AgentDeprecated(agent_id=agent_id, reason=None, occurred_at=_T2)
    state = fold([e1, e2, e3])
    assert state is not None
    assert state.status is AgentStatus.DEPRECATED
    # Lifecycle timestamps moved to projection.
    assert state.deprecation_reason is None


@pytest.mark.unit
def test_versioned_applied_to_empty_state_raises() -> None:
    """The shared `require_state` helper raises on transition-before-genesis."""
    e = AgentVersioned(agent_id=uuid4(), version="v1", occurred_at=_T0)
    with pytest.raises(ValueError, match="AgentVersioned"):
        fold([e])


@pytest.mark.unit
def test_deprecated_applied_to_empty_state_raises() -> None:
    e = AgentDeprecated(agent_id=uuid4(), reason=None, occurred_at=_T0)
    with pytest.raises(ValueError, match="AgentDeprecated"):
        fold([e])


# ---------------------------------------------------------------------------
# Suspended FSM + ToolGrant + Budget
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_versioned_then_suspended_folds_to_suspended_state() -> None:
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentVersioned(agent_id=agent_id, version="v1", occurred_at=_T1)
    e3 = AgentSuspended(
        agent_id=agent_id,
        reason="cost overrun",
        suspended_by=_SUSPENDED_BY,
        occurred_at=_T2,
    )
    state = fold([e1, e2, e3])
    assert state is not None
    assert state.status is AgentStatus.SUSPENDED
    assert state.suspended_at == _T2
    assert state.suspended_by == _SUSPENDED_BY
    assert state.suspension_reason is not None
    assert state.suspension_reason.value == "cost overrun"
    # `versioned_at` was previously preserved here as an audit-trail
    # historical record on state. Lifecycle timestamps now live on
    # `proj_agent_summary`, where the audit trail is kept.


@pytest.mark.unit
def test_suspended_then_resumed_folds_to_versioned_state() -> None:
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentVersioned(agent_id=agent_id, version="v1", occurred_at=_T1)
    e3 = AgentSuspended(
        agent_id=agent_id,
        reason="cost overrun",
        suspended_by=_SUSPENDED_BY,
        occurred_at=_T2,
    )
    e4 = AgentResumed(
        agent_id=agent_id,
        resumed_by=_RESUMED_BY,
        occurred_at=_T2 + timedelta(minutes=5),
    )
    state = fold([e1, e2, e3, e4])
    assert state is not None
    assert state.status is AgentStatus.VERSIONED
    # Resume preserves historical suspended_at + suspension_reason for audit.
    assert state.suspended_at == _T2
    assert state.suspended_by == _SUSPENDED_BY
    assert state.suspension_reason is not None
    assert state.suspension_reason.value == "cost overrun"
    assert state.resumed_at == _T2 + timedelta(minutes=5)
    assert state.resumed_by == _RESUMED_BY


@pytest.mark.unit
def test_suspended_then_deprecated_folds_to_deprecated_state() -> None:
    """Deprecated source set includes Suspended."""
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentVersioned(agent_id=agent_id, version="v1", occurred_at=_T1)
    e3 = AgentSuspended(
        agent_id=agent_id,
        reason="x",
        suspended_by=_SUSPENDED_BY,
        occurred_at=_T2,
    )
    e4 = AgentDeprecated(
        agent_id=agent_id, reason="retired while paused", occurred_at=_T2 + timedelta(minutes=10)
    )
    state = fold([e1, e2, e3, e4])
    assert state is not None
    assert state.status is AgentStatus.DEPRECATED


@pytest.mark.unit
def test_tool_granted_folds_into_tools_set() -> None:
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentToolGranted(agent_id=agent_id, tool_name="read_run", occurred_at=_T1)
    e3 = AgentToolGranted(agent_id=agent_id, tool_name="read_dataset", occurred_at=_T2)
    state = fold([e1, e2, e3])
    assert state is not None
    assert state.tools == frozenset({ToolName("read_run"), ToolName("read_dataset")})


@pytest.mark.unit
def test_tool_revoked_removes_from_tools_set() -> None:
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentToolGranted(agent_id=agent_id, tool_name="read_run", occurred_at=_T1)
    e3 = AgentToolRevoked(agent_id=agent_id, tool_name="read_run", occurred_at=_T2)
    state = fold([e1, e2, e3])
    assert state is not None
    assert state.tools == frozenset()


@pytest.mark.unit
def test_budget_updated_sets_budget_field() -> None:
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentBudgetUpdated(
        agent_id=agent_id,
        monthly_usd_cap=100.0,
        daily_token_cap=500_000,
        occurred_at=_T1,
    )
    state = fold([e1, e2])
    assert state is not None
    assert state.budget == AgentBudget(monthly_usd_cap=100.0, daily_token_cap=500_000)


@pytest.mark.unit
def test_budget_updated_with_both_caps_none_clears_budget() -> None:
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentBudgetUpdated(
        agent_id=agent_id,
        monthly_usd_cap=100.0,
        daily_token_cap=500_000,
        occurred_at=_T1,
    )
    e3 = AgentBudgetUpdated(
        agent_id=agent_id,
        monthly_usd_cap=None,
        daily_token_cap=None,
        occurred_at=_T2,
    )
    state = fold([e1, e2, e3])
    assert state is not None
    assert state.budget is None


@pytest.mark.unit
def test_tool_grant_preserves_unrelated_fields() -> None:
    """ToolGrant arm must not silently wipe deprecation_reason / suspended_at.

    Guards the silent-wipe class of bugs caught at gate review.
    (`versioned_at` formerly checked here is now on the projection;
    status + tools cover the silent-wipe guard at state level.)
    """
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentVersioned(agent_id=agent_id, version="v1", occurred_at=_T1)
    e3 = AgentToolGranted(agent_id=agent_id, tool_name="read_run", occurred_at=_T2)
    state = fold([e1, e2, e3])
    assert state is not None
    assert state.status is AgentStatus.VERSIONED
    assert state.tools == frozenset({ToolName("read_run")})


@pytest.mark.unit
def test_suspended_preserves_unrelated_fields() -> None:
    """Suspended arm must carry forward tools/budget/families/description.

    Guards against a future refactor accidentally dropping a field when
    updating the Suspended evolver arm (silent-wipe class of bug)."""
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentVersioned(agent_id=agent_id, version="v1", occurred_at=_T1)
    e3 = AgentToolGranted(agent_id=agent_id, tool_name="read_run", occurred_at=_T1)
    e4 = AgentBudgetUpdated(
        agent_id=agent_id,
        monthly_usd_cap=100.0,
        daily_token_cap=500_000,
        occurred_at=_T1,
    )
    e5 = AgentSuspended(
        agent_id=agent_id,
        reason="x",
        suspended_by=_SUSPENDED_BY,
        occurred_at=_T2,
    )
    state = fold([e1, e2, e3, e4, e5])
    assert state is not None
    assert state.tools == frozenset({ToolName("read_run")})
    assert state.budget == AgentBudget(monthly_usd_cap=100.0, daily_token_cap=500_000)
    assert state.capabilities == frozenset({AgentCapability("summarize")})
    assert state.description is not None
    assert state.description.value == "Synthesises terminal Runs."


@pytest.mark.unit
def test_resumed_preserves_unrelated_fields() -> None:
    """Resumed arm must carry forward tools/budget/historical suspension data."""
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentVersioned(agent_id=agent_id, version="v1", occurred_at=_T1)
    e3 = AgentToolGranted(agent_id=agent_id, tool_name="read_run", occurred_at=_T1)
    e4 = AgentBudgetUpdated(
        agent_id=agent_id,
        monthly_usd_cap=100.0,
        daily_token_cap=500_000,
        occurred_at=_T1,
    )
    e5 = AgentSuspended(
        agent_id=agent_id,
        reason="x",
        suspended_by=_SUSPENDED_BY,
        occurred_at=_T2,
    )
    e6 = AgentResumed(
        agent_id=agent_id,
        resumed_by=_RESUMED_BY,
        occurred_at=_T2 + timedelta(minutes=5),
    )
    state = fold([e1, e2, e3, e4, e5, e6])
    assert state is not None
    assert state.tools == frozenset({ToolName("read_run")})
    assert state.budget == AgentBudget(monthly_usd_cap=100.0, daily_token_cap=500_000)
    assert state.capabilities == frozenset({AgentCapability("summarize")})


@pytest.mark.unit
def test_tool_revoked_preserves_unrelated_fields() -> None:
    """ToolRevoked arm must not silently wipe budget/families/description."""
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentToolGranted(agent_id=agent_id, tool_name="read_run", occurred_at=_T1)
    e3 = AgentBudgetUpdated(
        agent_id=agent_id,
        monthly_usd_cap=50.0,
        daily_token_cap=None,
        occurred_at=_T1,
    )
    e4 = AgentToolRevoked(agent_id=agent_id, tool_name="read_run", occurred_at=_T2)
    state = fold([e1, e2, e3, e4])
    assert state is not None
    assert state.tools == frozenset()
    assert state.budget == AgentBudget(monthly_usd_cap=50.0, daily_token_cap=None)
    assert state.capabilities == frozenset({AgentCapability("summarize")})
    assert state.description is not None


@pytest.mark.unit
def test_budget_updated_preserves_unrelated_fields() -> None:
    """BudgetUpdated arm must not silently wipe tools/families/description."""
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentToolGranted(agent_id=agent_id, tool_name="read_run", occurred_at=_T1)
    e3 = AgentBudgetUpdated(
        agent_id=agent_id,
        monthly_usd_cap=100.0,
        daily_token_cap=500_000,
        occurred_at=_T2,
    )
    state = fold([e1, e2, e3])
    assert state is not None
    assert state.tools == frozenset({ToolName("read_run")})
    assert state.capabilities == frozenset({AgentCapability("summarize")})
    assert state.description is not None
    assert state.budget == AgentBudget(monthly_usd_cap=100.0, daily_token_cap=500_000)


@pytest.mark.unit
def test_suspended_applied_to_empty_state_raises() -> None:
    e = AgentSuspended(
        agent_id=uuid4(),
        reason="x",
        suspended_by=_SUSPENDED_BY,
        occurred_at=_T0,
    )
    with pytest.raises(ValueError, match="AgentSuspended"):
        fold([e])


@pytest.mark.unit
def test_resumed_applied_to_empty_state_raises() -> None:
    e = AgentResumed(agent_id=uuid4(), resumed_by=_RESUMED_BY, occurred_at=_T0)
    with pytest.raises(ValueError, match="AgentResumed"):
        fold([e])


@pytest.mark.unit
def test_tool_granted_applied_to_empty_state_raises() -> None:
    e = AgentToolGranted(agent_id=uuid4(), tool_name="x", occurred_at=_T0)
    with pytest.raises(ValueError, match="AgentToolGranted"):
        fold([e])


@pytest.mark.unit
def test_tool_revoked_applied_to_empty_state_raises() -> None:
    e = AgentToolRevoked(agent_id=uuid4(), tool_name="x", occurred_at=_T0)
    with pytest.raises(ValueError, match="AgentToolRevoked"):
        fold([e])


@pytest.mark.unit
def test_budget_updated_applied_to_empty_state_raises() -> None:
    e = AgentBudgetUpdated(
        agent_id=uuid4(), monthly_usd_cap=10.0, daily_token_cap=None, occurred_at=_T0
    )
    with pytest.raises(ValueError, match="AgentBudgetUpdated"):
        fold([e])
