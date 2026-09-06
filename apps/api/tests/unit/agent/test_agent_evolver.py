"""Evolver tests for the Agent aggregate."""

import dataclasses
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cora.agent.aggregates.agent.events import (
    AgentBudgetUpdated,
    AgentDefined,
    AgentDefinitionRestated,
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
    BrainKind,
    BrainRef,
    ModelRef,
    ToolName,
)
from cora.shared.identity import ActorId

# The sentinel exactly as eighteen seeds once wrote it. A literal rather than
# an import, because no seed constructs it any more: it survives only in
# streams written before `brain` existed, which is precisely why the fold that
# reads it still has to work.
_SEEDED_SENTINEL = ModelRef(
    provider="deterministic", model="agent:RunSupervisor:v1", snapshot_pin=None
)

_AGENT_ID = uuid4()
_SUSPENDED_BY = ActorId(uuid4())
_RESUMED_BY = ActorId(uuid4())

_T0 = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_T1 = _T0 + timedelta(minutes=10)
_T2 = _T0 + timedelta(minutes=20)


_DEFAULT_MODEL_REF = ModelRef(provider="anthropic", model="claude-sonnet-4-6")


def _genesis(
    *,
    agent_id: object | None = None,
    # Sentinel-defaulted rather than None-defaulted: `model_ref=None` is a
    # case under test (the post-seed era), so it cannot also mean "give me the
    # default".
    model_ref: ModelRef | None = _DEFAULT_MODEL_REF,
    brain: BrainRef | None = None,
) -> AgentDefined:
    return AgentDefined(
        agent_id=agent_id or uuid4(),  # type: ignore[arg-type]
        kind="RunDebriefer",
        name="Run Debrief",
        version="v1",
        model_ref=model_ref,
        brain=brain,
        description="Synthesises terminal Runs.",
        canonical_uri="https://example.org/agents/run-debrief",
        prompt_template_id=None,
        capabilities=frozenset({"summarize"}),
        occurred_at=_T0,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("label", "follow_on"),
    [
        ("versioned", AgentVersioned(agent_id=_AGENT_ID, version="v2", occurred_at=_T1)),
        (
            "suspended",
            AgentSuspended(
                agent_id=_AGENT_ID, reason="paused", suspended_by=_SUSPENDED_BY, occurred_at=_T1
            ),
        ),
        (
            "tool_granted",
            AgentToolGranted(agent_id=_AGENT_ID, tool_name="list_runs", occurred_at=_T1),
        ),
        (
            "budget_updated",
            AgentBudgetUpdated(
                agent_id=_AGENT_ID, monthly_usd_cap=5.0, daily_token_cap=None, occurred_at=_T1
            ),
        ),
        (
            "identity_restated",
            AgentDefinitionRestated(
                agent_id=_AGENT_ID,
                name="Renamed",
                brain=BrainRef.for_rule("Restated:v2"),
                reason="restated for the carry-forward guard",
                occurred_at=_T1,
            ),
        ),
    ],
)
def test_every_follow_on_event_carries_forward_every_field(label: str, follow_on: object) -> None:
    """No evolver arm silently wipes a field it does not itself change.

    The module docstring already claims this, and the claim was untestable:
    each arm rebuilds `Agent(...)` by hand from `prior`, so adding a field to
    the aggregate means editing eight call sites and the suite stays green if
    you miss one. `brain` was added across exactly those eight.

    This compares the whole aggregate before and after, excluding only the
    fields the event under test is SUPPOSED to change, so a newly added field
    is covered the moment it exists rather than when someone remembers to
    assert it.
    """
    genesis = _genesis(agent_id=_AGENT_ID)
    before = fold([genesis])
    assert before is not None
    after = fold([genesis, follow_on])  # type: ignore[list-item]
    assert after is not None

    changed_by_design = {
        "versioned": {"version", "status"},
        "suspended": {"status", "suspended_at", "suspension_reason", "suspended_by"},
        "tool_granted": {"tools"},
        "budget_updated": {"budget"},
        "identity_restated": {"name", "brain"},
    }[label]

    carried = {
        f.name
        for f in dataclasses.fields(before)
        if f.name not in changed_by_design and getattr(before, f.name) != getattr(after, f.name)
    }
    assert carried == set(), f"{label} arm wiped: {sorted(carried)}"


@pytest.mark.unit
def test_pre_brain_llm_stream_folds_to_a_language_model_brain() -> None:
    """A stream written before `brain` existed still folds to a brain.

    Folded state always carries one, so a reader never has to know which era
    the stream came from.
    """
    state = fold([_genesis()])
    assert state is not None
    assert state.brain is not None
    assert state.brain.kind is BrainKind.LANGUAGE_MODEL
    assert state.brain.model_ref == ModelRef(provider="anthropic", model="claude-sonnet-4-6")


@pytest.mark.unit
def test_pre_brain_deterministic_sentinel_folds_to_a_rule_brain() -> None:
    """The deterministic sentinel folds to the Rule it always was.

    Eighteen seeded agents run no model and had to satisfy a required,
    LLM-shaped `model_ref`, so they all carried the same deliberate sentinel.
    Reading that as a LanguageModel brain would assert they think with a model
    that does not exist and was never approved, and because seeds are
    idempotent that claim would never be corrected on an existing deployment.

    The two eras have to agree: a deployment first booted before `brain`
    existed folds its RunSupervisor through here, and one booted after reads
    the brain the seed now declares. Both must land on
    `Rule("RunSupervisor:v1")`. This test pins the legacy half; the
    architecture-tier `test_rule_brain_is_named_for_its_own_agent_kind` pins
    the other half by requiring each seed's rule to be named for its own
    agent kind, which is what the sentinel encoded.
    """
    state = fold([_genesis(model_ref=_SEEDED_SENTINEL)])
    assert state is not None
    assert state.brain is not None
    assert state.brain.kind is BrainKind.RULE
    assert state.brain.rule == "RunSupervisor:v1"


@pytest.mark.unit
def test_seed_era_stream_folds_to_the_brain_the_seed_declares() -> None:
    """The other era of the same agent, and it must land in the same place.

    A deployment first booted after the seeds moved over has no `model_ref`
    at all. If this and the sentinel fold disagreed, the same agent would
    report a different brain depending only on when its deployment started.
    """
    state = fold([_genesis(model_ref=None, brain=BrainRef.for_rule("RunSupervisor:v1"))])
    assert state is not None
    assert state.model_ref is None
    assert state.brain == BrainRef.for_rule("RunSupervisor:v1")


@pytest.mark.unit
def test_genesis_carrying_neither_brain_nor_model_ref_refuses_to_fold() -> None:
    """No writer has ever been able to produce this, so folding it would mean
    inventing a brain for a stream that names none."""
    with pytest.raises(ValueError, match="neither brain nor model_ref"):
        fold([_genesis(model_ref=None)])


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
    e2 = AgentDeprecated(agent_id=agent_id, reason="Superseded", occurred_at=_T1)
    state = fold([e1, e2])
    assert state is not None
    assert state.status is AgentStatus.DEPRECATED
    # Lifecycle timestamps moved to projection.
    assert state.deprecation_reason is not None
    assert state.deprecation_reason == "Superseded"


@pytest.mark.unit
def test_full_lifecycle_folds_to_deprecated_state() -> None:
    """Genesis -> Versioned -> Deprecated; all three transitions fold."""
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentVersioned(agent_id=agent_id, version="v1", occurred_at=_T1)
    e3 = AgentDeprecated(agent_id=agent_id, reason="Superseded", occurred_at=_T2)
    state = fold([e1, e2, e3])
    assert state is not None
    assert state.status is AgentStatus.DEPRECATED
    # Lifecycle timestamps moved to projection.
    assert state.deprecation_reason == "Superseded"


@pytest.mark.unit
def test_versioned_applied_to_empty_state_raises() -> None:
    """The shared `require_state` helper raises on transition-before-genesis."""
    e = AgentVersioned(agent_id=uuid4(), version="v1", occurred_at=_T0)
    with pytest.raises(ValueError, match="AgentVersioned"):
        fold([e])


@pytest.mark.unit
def test_deprecated_applied_to_empty_state_raises() -> None:
    e = AgentDeprecated(agent_id=uuid4(), reason="Superseded", occurred_at=_T0)
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
        agent_id=agent_id, reason="Superseded", occurred_at=_T2 + timedelta(minutes=10)
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
    e3 = AgentToolRevoked(
        reason="tool no longer needed", agent_id=agent_id, tool_name="read_run", occurred_at=_T2
    )
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
    e4 = AgentToolRevoked(
        reason="tool no longer needed", agent_id=agent_id, tool_name="read_run", occurred_at=_T2
    )
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
    e = AgentToolRevoked(
        reason="tool no longer needed", agent_id=uuid4(), tool_name="x", occurred_at=_T0
    )
    with pytest.raises(ValueError, match="AgentToolRevoked"):
        fold([e])


@pytest.mark.unit
def test_budget_updated_applied_to_empty_state_raises() -> None:
    e = AgentBudgetUpdated(
        agent_id=uuid4(), monthly_usd_cap=10.0, daily_token_cap=None, occurred_at=_T0
    )
    with pytest.raises(ValueError, match="AgentBudgetUpdated"):
        fold([e])
