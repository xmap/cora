"""VO / enum / error tests for the Agent aggregate."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.agent.aggregates.agent import (
    AGENT_CANONICAL_URI_MAX_LENGTH,
    AGENT_CAPABILITIES_MAX_COUNT,
    AGENT_CAPABILITY_MAX_LENGTH,
    AGENT_DESCRIPTION_MAX_LENGTH,
    AGENT_KIND_MAX_LENGTH,
    AGENT_NAME_MAX_LENGTH,
    AGENT_VERSION_MAX_LENGTH,
    MODEL_REF_MODEL_MAX_LENGTH,
    MODEL_REF_PROVIDER_MAX_LENGTH,
    MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH,
    Agent,
    AgentCanonicalUri,
    AgentCapability,
    AgentDeprecationReason,
    AgentDescription,
    AgentKind,
    AgentName,
    AgentStatus,
    AgentVersion,
    InvalidAgentCanonicalUriError,
    InvalidAgentCapabilityError,
    InvalidAgentDeprecationReasonError,
    InvalidAgentDescriptionError,
    InvalidAgentKindError,
    InvalidAgentNameError,
    InvalidAgentVersionError,
    InvalidModelRefError,
    ModelRef,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)


# ---------- AgentKind / AgentName / AgentVersion / AgentDescription (bounded text) ----------


@pytest.mark.unit
def test_agent_kind_accepts_normal_string() -> None:
    kind = AgentKind("RunDebriefer")
    assert kind.value == "RunDebriefer"


@pytest.mark.unit
def test_agent_kind_trims_whitespace() -> None:
    assert AgentKind("  RunDebriefer  ").value == "RunDebriefer"


@pytest.mark.unit
def test_agent_kind_rejects_empty() -> None:
    with pytest.raises(InvalidAgentKindError):
        AgentKind("")


@pytest.mark.unit
def test_agent_kind_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidAgentKindError):
        AgentKind("   ")


@pytest.mark.unit
def test_agent_kind_rejects_over_cap() -> None:
    with pytest.raises(InvalidAgentKindError):
        AgentKind("x" * (AGENT_KIND_MAX_LENGTH + 1))


@pytest.mark.unit
def test_agent_name_accepts_normal_string() -> None:
    assert AgentName("Run debrief agent").value == "Run debrief agent"


@pytest.mark.unit
def test_agent_name_rejects_empty() -> None:
    with pytest.raises(InvalidAgentNameError):
        AgentName("")


@pytest.mark.unit
def test_agent_name_rejects_over_cap() -> None:
    with pytest.raises(InvalidAgentNameError):
        AgentName("x" * (AGENT_NAME_MAX_LENGTH + 1))


@pytest.mark.unit
def test_agent_version_accepts_semver_like() -> None:
    assert AgentVersion("v1").value == "v1"
    assert AgentVersion("1.0.0").value == "1.0.0"
    assert AgentVersion("2026-05-16").value == "2026-05-16"


@pytest.mark.unit
def test_agent_version_rejects_empty() -> None:
    with pytest.raises(InvalidAgentVersionError):
        AgentVersion("")


@pytest.mark.unit
def test_agent_version_rejects_over_cap() -> None:
    with pytest.raises(InvalidAgentVersionError):
        AgentVersion("x" * (AGENT_VERSION_MAX_LENGTH + 1))


@pytest.mark.unit
def test_agent_description_accepts_normal_string() -> None:
    assert AgentDescription("Synthesises what happened on terminal Runs.").value.startswith(
        "Synthesises"
    )


@pytest.mark.unit
def test_agent_description_rejects_empty() -> None:
    with pytest.raises(InvalidAgentDescriptionError):
        AgentDescription("")


@pytest.mark.unit
def test_agent_description_rejects_over_cap() -> None:
    with pytest.raises(InvalidAgentDescriptionError):
        AgentDescription("x" * (AGENT_DESCRIPTION_MAX_LENGTH + 1))


# ---------- AgentCanonicalUri (https + no fragment) ----------


@pytest.mark.unit
def test_agent_canonical_uri_accepts_https() -> None:
    uri = AgentCanonicalUri("https://example.org/agents/run-debrief")
    assert uri.value == "https://example.org/agents/run-debrief"


@pytest.mark.unit
def test_agent_canonical_uri_trims_whitespace() -> None:
    assert AgentCanonicalUri("  https://example.org  ").value == "https://example.org"


@pytest.mark.unit
def test_agent_canonical_uri_rejects_http() -> None:
    with pytest.raises(InvalidAgentCanonicalUriError, match="must start with `https://`"):
        AgentCanonicalUri("http://example.org")


@pytest.mark.unit
def test_agent_canonical_uri_rejects_fragment() -> None:
    with pytest.raises(InvalidAgentCanonicalUriError, match="must not contain a fragment"):
        AgentCanonicalUri("https://example.org/agents#frag")


@pytest.mark.unit
def test_agent_canonical_uri_rejects_empty() -> None:
    with pytest.raises(InvalidAgentCanonicalUriError):
        AgentCanonicalUri("")


@pytest.mark.unit
def test_agent_canonical_uri_rejects_over_cap() -> None:
    with pytest.raises(InvalidAgentCanonicalUriError):
        AgentCanonicalUri("https://" + "x" * AGENT_CANONICAL_URI_MAX_LENGTH)


# ---------- AgentCapability + AgentDeprecationReason ----------


@pytest.mark.unit
def test_agent_capability_accepts_normal_string() -> None:
    assert AgentCapability("summarize").value == "summarize"


@pytest.mark.unit
def test_agent_capability_rejects_empty() -> None:
    with pytest.raises(InvalidAgentCapabilityError):
        AgentCapability("")


@pytest.mark.unit
def test_agent_capability_rejects_over_cap() -> None:
    with pytest.raises(InvalidAgentCapabilityError):
        AgentCapability("x" * (AGENT_CAPABILITY_MAX_LENGTH + 1))


@pytest.mark.unit
def test_agent_deprecation_reason_accepts_normal_string() -> None:
    assert AgentDeprecationReason("model fingerprint changed").value == "model fingerprint changed"


@pytest.mark.unit
def test_agent_deprecation_reason_rejects_empty() -> None:
    with pytest.raises(InvalidAgentDeprecationReasonError):
        AgentDeprecationReason("")


@pytest.mark.unit
def test_agent_deprecation_reason_rejects_over_cap() -> None:
    with pytest.raises(InvalidAgentDeprecationReasonError):
        AgentDeprecationReason("x" * (REASON_MAX_LENGTH + 1))


# ---------- ModelRef ----------


@pytest.mark.unit
def test_model_ref_accepts_full_triple() -> None:
    m = ModelRef(provider="anthropic", model="claude-sonnet-4-6", snapshot_pin="20251001")
    assert m.provider == "anthropic"
    assert m.model == "claude-sonnet-4-6"
    assert m.snapshot_pin == "20251001"


@pytest.mark.unit
def test_model_ref_accepts_null_snapshot_pin() -> None:
    m = ModelRef(provider="openai", model="o4-mini", snapshot_pin=None)
    assert m.snapshot_pin is None


@pytest.mark.unit
def test_model_ref_trims_provider_and_model() -> None:
    m = ModelRef(provider="  anthropic  ", model="  claude-sonnet-4-6  ", snapshot_pin=None)
    assert m.provider == "anthropic"
    assert m.model == "claude-sonnet-4-6"


@pytest.mark.unit
def test_model_ref_rejects_empty_provider() -> None:
    with pytest.raises(InvalidModelRefError, match="provider must be non-empty"):
        ModelRef(provider="", model="claude-sonnet-4-6")


@pytest.mark.unit
def test_model_ref_rejects_whitespace_provider() -> None:
    with pytest.raises(InvalidModelRefError, match="provider must be non-empty"):
        ModelRef(provider="   ", model="claude-sonnet-4-6")


@pytest.mark.unit
def test_model_ref_rejects_empty_model() -> None:
    with pytest.raises(InvalidModelRefError, match="model must be non-empty"):
        ModelRef(provider="anthropic", model="")


@pytest.mark.unit
def test_model_ref_rejects_whitespace_snapshot_pin() -> None:
    """Whitespace-only snapshot_pin is rejected; callers must pass None to omit."""
    with pytest.raises(InvalidModelRefError, match="snapshot_pin must be non-empty"):
        ModelRef(provider="anthropic", model="claude-sonnet-4-6", snapshot_pin="   ")


@pytest.mark.unit
def test_model_ref_rejects_over_cap_provider() -> None:
    with pytest.raises(InvalidModelRefError, match="provider exceeds"):
        ModelRef(provider="x" * (MODEL_REF_PROVIDER_MAX_LENGTH + 1), model="claude-sonnet-4-6")


@pytest.mark.unit
def test_model_ref_rejects_over_cap_model() -> None:
    with pytest.raises(InvalidModelRefError, match="model exceeds"):
        ModelRef(provider="anthropic", model="x" * (MODEL_REF_MODEL_MAX_LENGTH + 1))


@pytest.mark.unit
def test_model_ref_rejects_over_cap_snapshot_pin() -> None:
    with pytest.raises(InvalidModelRefError, match="snapshot_pin exceeds"):
        ModelRef(
            provider="anthropic",
            model="claude-sonnet-4-6",
            snapshot_pin="x" * (MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH + 1),
        )


# ---------- AgentStatus enum ----------


@pytest.mark.unit
def test_agent_status_values() -> None:
    assert AgentStatus.DEFINED.value == "Defined"
    assert AgentStatus.VERSIONED.value == "Versioned"
    assert AgentStatus.SUSPENDED.value == "Suspended"
    assert AgentStatus.DEPRECATED.value == "Deprecated"


# ---------- Agent aggregate construction ----------


@pytest.mark.unit
def test_agent_defaults_to_defined_status_and_empty_capabilities() -> None:
    agent = Agent(
        id=uuid4(),
        kind=AgentKind("RunDebriefer"),
        name=AgentName("Run Debrief"),
        version=AgentVersion("v1"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
    )
    assert agent.status is AgentStatus.DEFINED
    assert agent.capabilities == frozenset()
    assert agent.description is None
    assert agent.canonical_uri is None
    assert agent.prompt_template_id is None
    assert agent.deprecation_reason is None


@pytest.mark.unit
def test_agent_capabilities_cap_is_enforced_at_decider_not_state() -> None:
    """Aggregate-level: frozenset can be any size; decider enforces the cap.

    This documents that the cardinality cap is a write-side invariant
    (enforced by `define_agent.decider`); the aggregate state itself
    does not police it. This separation lets the read path fold any
    valid past payload regardless of future cap-tightening.
    """
    over_cap_count = AGENT_CAPABILITIES_MAX_COUNT + 5
    agent = Agent(
        id=uuid4(),
        kind=AgentKind("RunDebriefer"),
        name=AgentName("Run Debrief"),
        version=AgentVersion("v1"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        capabilities=frozenset(AgentCapability(f"cap-{i}") for i in range(over_cap_count)),
    )
    assert len(agent.capabilities) == over_cap_count


# ---------- lifecycle widening: AgentSuspensionReason / ToolName / AgentBudget ----------


@pytest.mark.unit
def test_agent_suspension_reason_accepts_normal_string() -> None:
    from cora.agent.aggregates.agent import AgentSuspensionReason

    assert AgentSuspensionReason("cost overrun").value == "cost overrun"


@pytest.mark.unit
def test_agent_suspension_reason_trims_whitespace() -> None:
    from cora.agent.aggregates.agent import AgentSuspensionReason

    assert AgentSuspensionReason("  cost overrun  ").value == "cost overrun"


@pytest.mark.unit
def test_agent_suspension_reason_rejects_empty() -> None:
    from cora.agent.aggregates.agent import (
        AgentSuspensionReason,
        InvalidAgentSuspensionReasonError,
    )

    with pytest.raises(InvalidAgentSuspensionReasonError):
        AgentSuspensionReason("   ")


@pytest.mark.unit
def test_agent_suspension_reason_rejects_over_cap() -> None:
    from cora.agent.aggregates.agent import (
        AgentSuspensionReason,
        InvalidAgentSuspensionReasonError,
    )

    with pytest.raises(InvalidAgentSuspensionReasonError):
        AgentSuspensionReason("x" * (REASON_MAX_LENGTH + 1))


@pytest.mark.unit
def test_tool_name_accepts_normal_string_and_trims() -> None:
    from cora.agent.aggregates.agent import ToolName

    assert ToolName("read_run").value == "read_run"
    assert ToolName("  read_run  ").value == "read_run"


@pytest.mark.unit
def test_tool_name_rejects_empty_and_over_cap() -> None:
    from cora.agent.aggregates.agent import (
        AGENT_TOOL_NAME_MAX_LENGTH,
        InvalidToolNameError,
        ToolName,
    )

    with pytest.raises(InvalidToolNameError):
        ToolName("   ")
    with pytest.raises(InvalidToolNameError):
        ToolName("x" * (AGENT_TOOL_NAME_MAX_LENGTH + 1))


@pytest.mark.unit
def test_agent_budget_accepts_both_caps_set() -> None:
    from cora.agent.aggregates.agent import AgentBudget

    b = AgentBudget(monthly_usd_cap=100.0, daily_token_cap=500_000)
    assert b.monthly_usd_cap == 100.0
    assert b.daily_token_cap == 500_000


@pytest.mark.unit
def test_agent_budget_accepts_one_cap_set() -> None:
    from cora.agent.aggregates.agent import AgentBudget

    assert AgentBudget(monthly_usd_cap=50.0, daily_token_cap=None).daily_token_cap is None
    assert AgentBudget(monthly_usd_cap=None, daily_token_cap=10_000).monthly_usd_cap is None


@pytest.mark.unit
def test_agent_budget_accepts_zero_caps() -> None:
    """Zero caps are allowed (interpretation: 'no spend permitted today')."""
    from cora.agent.aggregates.agent import AgentBudget

    b = AgentBudget(monthly_usd_cap=0.0, daily_token_cap=0)
    assert b.monthly_usd_cap == 0.0
    assert b.daily_token_cap == 0


@pytest.mark.unit
def test_agent_budget_rejects_both_none() -> None:
    """Both None is the no-budget shape (Agent.budget = None directly)."""
    from cora.agent.aggregates.agent import AgentBudget, InvalidAgentBudgetError

    with pytest.raises(InvalidAgentBudgetError):
        AgentBudget(monthly_usd_cap=None, daily_token_cap=None)


@pytest.mark.unit
def test_agent_budget_rejects_negative_monthly() -> None:
    from cora.agent.aggregates.agent import AgentBudget, InvalidAgentBudgetError

    with pytest.raises(InvalidAgentBudgetError):
        AgentBudget(monthly_usd_cap=-0.01, daily_token_cap=None)


@pytest.mark.unit
def test_agent_budget_rejects_negative_daily() -> None:
    from cora.agent.aggregates.agent import AgentBudget, InvalidAgentBudgetError

    with pytest.raises(InvalidAgentBudgetError):
        AgentBudget(monthly_usd_cap=None, daily_token_cap=-1)


@pytest.mark.unit
def test_agent_defaults_to_empty_tools_and_none_budget() -> None:
    """Aggregate-level: additive fields default appropriately."""
    agent = Agent(
        id=uuid4(),
        kind=AgentKind("RunDebriefer"),
        name=AgentName("Run Debrief"),
        version=AgentVersion("v1"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
    )
    assert agent.tools == frozenset()
    assert agent.budget is None
    assert agent.suspended_at is None
    assert agent.resumed_at is None
    assert agent.suspension_reason is None
