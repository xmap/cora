"""Unit tests for Decision aggregate state, value objects, and domain errors."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from cora.decision.aggregates.decision import (
    DECISION_ALTERNATIVE_ENTRY_MAX_LENGTH,
    DECISION_ALTERNATIVES_MAX_ENTRIES,
    DECISION_CHOICE_MAX_LENGTH,
    DECISION_CONTEXT_MAX_LENGTH,
    DECISION_INPUTS_KEY_MAX_LENGTH,
    DECISION_INPUTS_MAX_ENTRIES,
    DECISION_REASONING_MAX_LENGTH,
    DECISION_REASONING_SIGNATURE_MAX_LENGTH,
    DECISION_RULE_MAX_LENGTH,
    DeciderActorNotFoundError,
    Decision,
    DecisionAlreadyExistsError,
    DecisionChoice,
    DecisionConfidenceSource,
    DecisionContext,
    DecisionNotFoundError,
    DecisionParentNotFoundError,
    DecisionRule,
    InvalidDecisionAlternativesError,
    InvalidDecisionChoiceError,
    InvalidDecisionConfidenceError,
    InvalidDecisionContextError,
    InvalidDecisionInputsError,
    InvalidDecisionReasoningError,
    InvalidDecisionRuleError,
    InvalidReasoningSignatureError,
    validate_alternatives,
    validate_confidence,
    validate_inputs,
    validate_reasoning,
    validate_reasoning_signature,
)
from cora.decision.errors import OverrideKindRequiresParentError
from cora.shared.identity import ActorId

# ---------- DecisionChoice / DecisionContext / DecisionRule ----------


@pytest.mark.unit
def test_decision_choice_accepts_normal_string() -> None:
    c = DecisionChoice("Approved with conditions")
    assert c.value == "Approved with conditions"


@pytest.mark.unit
def test_decision_choice_trims_whitespace() -> None:
    c = DecisionChoice("  Approved  ")
    assert c.value == "Approved"


@pytest.mark.unit
@pytest.mark.parametrize("value", ["", "   "])
def test_decision_choice_rejects_blank(value: str) -> None:
    with pytest.raises(InvalidDecisionChoiceError):
        DecisionChoice(value)


@pytest.mark.unit
def test_decision_choice_rejects_too_long() -> None:
    with pytest.raises(InvalidDecisionChoiceError):
        DecisionChoice("a" * (DECISION_CHOICE_MAX_LENGTH + 1))


@pytest.mark.unit
def test_decision_context_accepts_well_known_value() -> None:
    c = DecisionContext("RecipeApproval")
    assert c.value == "RecipeApproval"


@pytest.mark.unit
def test_decision_context_accepts_arbitrary_string() -> None:
    """Open-string per Q5: new contexts arrive without schema migration."""
    c = DecisionContext("FacilityCustomContext_v3")
    assert c.value == "FacilityCustomContext_v3"


@pytest.mark.unit
@pytest.mark.parametrize("value", ["", "   "])
def test_decision_context_rejects_blank(value: str) -> None:
    with pytest.raises(InvalidDecisionContextError):
        DecisionContext(value)


@pytest.mark.unit
def test_decision_context_rejects_too_long() -> None:
    with pytest.raises(InvalidDecisionContextError):
        DecisionContext("a" * (DECISION_CONTEXT_MAX_LENGTH + 1))


@pytest.mark.unit
def test_rule_accepts_iso17025_style_id() -> None:
    r = DecisionRule("iso17025:7.1.3:simple_acceptance")
    assert r.value == "iso17025:7.1.3:simple_acceptance"


@pytest.mark.unit
def test_rule_rejects_blank() -> None:
    with pytest.raises(InvalidDecisionRuleError):
        DecisionRule("")


@pytest.mark.unit
def test_rule_rejects_too_long() -> None:
    with pytest.raises(InvalidDecisionRuleError):
        DecisionRule("a" * (DECISION_RULE_MAX_LENGTH + 1))


# ---------- validate_reasoning ----------


@pytest.mark.unit
def test_validate_reasoning_returns_none_for_none() -> None:
    assert validate_reasoning(None) is None


@pytest.mark.unit
@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_validate_reasoning_returns_none_for_blank(value: str) -> None:
    """Operator UIs send empty strings for unset optional fields; fold to None."""
    assert validate_reasoning(value) is None


@pytest.mark.unit
def test_validate_reasoning_trims_and_returns() -> None:
    assert validate_reasoning("  some text  ") == "some text"


@pytest.mark.unit
def test_validate_reasoning_rejects_too_long() -> None:
    with pytest.raises(InvalidDecisionReasoningError):
        validate_reasoning("a" * (DECISION_REASONING_MAX_LENGTH + 1))


# ---------- validate_confidence ----------


@pytest.mark.unit
def test_validate_confidence_returns_none_for_none() -> None:
    assert validate_confidence(None) is None


@pytest.mark.unit
@pytest.mark.parametrize("value", [0.0, 0.5, 1.0])
def test_validate_confidence_accepts_in_range(value: float) -> None:
    assert validate_confidence(value) == value


@pytest.mark.unit
@pytest.mark.parametrize("value", [-0.01, 1.01, -1.0, 2.0])
def test_validate_confidence_rejects_out_of_range(value: float) -> None:
    with pytest.raises(InvalidDecisionConfidenceError):
        validate_confidence(value)


@pytest.mark.unit
def test_validate_confidence_rejects_nan() -> None:
    with pytest.raises(InvalidDecisionConfidenceError):
        validate_confidence(float("nan"))


@pytest.mark.unit
def test_decision_confidence_source_enum_values() -> None:
    assert DecisionConfidenceSource.SELF_REPORTED == "self_reported"
    assert DecisionConfidenceSource.LOGPROB == "logprob"
    assert DecisionConfidenceSource.ENSEMBLE == "ensemble"
    assert DecisionConfidenceSource.HUMAN == "human"


# ---------- validate_alternatives ----------


@pytest.mark.unit
def test_validate_alternatives_accepts_empty() -> None:
    assert validate_alternatives(()) == ()


@pytest.mark.unit
def test_validate_alternatives_preserves_order() -> None:
    """Top-k ordering matters for AI deciders + Cedar PolicyGrant."""
    result = validate_alternatives(("Hold", "Stop", "Abort"))
    assert result == ("Hold", "Stop", "Abort")


@pytest.mark.unit
def test_validate_alternatives_trims_entries() -> None:
    assert validate_alternatives(("  Hold  ", " Stop")) == ("Hold", "Stop")


@pytest.mark.unit
def test_validate_alternatives_rejects_blank_entry() -> None:
    with pytest.raises(InvalidDecisionAlternativesError):
        validate_alternatives(("Hold", "", "Stop"))


@pytest.mark.unit
def test_validate_alternatives_rejects_too_long_entry() -> None:
    too_long = "x" * (DECISION_ALTERNATIVE_ENTRY_MAX_LENGTH + 1)
    with pytest.raises(InvalidDecisionAlternativesError):
        validate_alternatives((too_long,))


@pytest.mark.unit
def test_validate_alternatives_rejects_too_many_entries() -> None:
    too_many = tuple(f"alt{i}" for i in range(DECISION_ALTERNATIVES_MAX_ENTRIES + 1))
    with pytest.raises(InvalidDecisionAlternativesError):
        validate_alternatives(too_many)


# ---------- validate_inputs ----------


@pytest.mark.unit
def test_validate_inputs_returns_none_for_none() -> None:
    assert validate_inputs(None) is None


@pytest.mark.unit
def test_validate_inputs_accepts_well_formed() -> None:
    inputs: dict[str, Any] = {
        "measured_value": 1.234,
        "uncertainty": 0.05,
        "limit": 1.5,
        "instrument_id": "DET-32A",
    }
    assert validate_inputs(inputs) == inputs


@pytest.mark.unit
def test_validate_inputs_rejects_too_many_keys() -> None:
    inputs: dict[str, Any] = {f"k{i}": i for i in range(DECISION_INPUTS_MAX_ENTRIES + 1)}
    with pytest.raises(InvalidDecisionInputsError):
        validate_inputs(inputs)


@pytest.mark.unit
def test_validate_inputs_rejects_blank_key() -> None:
    with pytest.raises(InvalidDecisionInputsError):
        validate_inputs({"": 1})


@pytest.mark.unit
def test_validate_inputs_rejects_too_long_key() -> None:
    too_long = "k" * (DECISION_INPUTS_KEY_MAX_LENGTH + 1)
    with pytest.raises(InvalidDecisionInputsError):
        validate_inputs({too_long: 1})


@pytest.mark.unit
def test_validate_inputs_rejects_non_json_roundtrippable_datetime() -> None:
    """Defensive: non-JSON values fail at the BC boundary rather
    than deep at jsonb serialization time."""
    from datetime import datetime as dt

    with pytest.raises(InvalidDecisionInputsError) as exc_info:
        validate_inputs({"timestamp": dt.now()})
    assert "JSON-roundtrippable" in str(exc_info.value)


@pytest.mark.unit
def test_validate_inputs_rejects_set_value() -> None:
    with pytest.raises(InvalidDecisionInputsError):
        validate_inputs({"items": {1, 2, 3}})


@pytest.mark.unit
def test_validate_inputs_accepts_nested_json_value() -> None:
    """Nested dicts/lists of primitives round-trip cleanly."""
    inputs: dict[str, Any] = {
        "outer": {"inner_list": [1, 2, 3], "inner_dict": {"k": "v"}},
        "scalar": 42,
    }
    assert validate_inputs(inputs) == inputs


# ---------- validate_reasoning_signature ----------


@pytest.mark.unit
def test_validate_reasoning_signature_returns_none_for_none() -> None:
    assert validate_reasoning_signature(None) is None


@pytest.mark.unit
def test_validate_reasoning_signature_returns_none_for_blank() -> None:
    assert validate_reasoning_signature("   ") is None


@pytest.mark.unit
def test_validate_reasoning_signature_trims() -> None:
    assert validate_reasoning_signature("  abc123  ") == "abc123"


@pytest.mark.unit
def test_validate_reasoning_signature_rejects_too_long() -> None:
    too_long = "a" * (DECISION_REASONING_SIGNATURE_MAX_LENGTH + 1)
    with pytest.raises(InvalidReasoningSignatureError):
        validate_reasoning_signature(too_long)


# ---------- Decision aggregate root ----------


@pytest.mark.unit
def test_decision_default_optionals_are_none_or_empty() -> None:
    d = Decision(
        id=uuid4(),
        decided_by=ActorId(uuid4()),
        decided_at=datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC),
        context=DecisionContext("RecipeApproval"),
        choice=DecisionChoice("Approved"),
    )
    assert d.parent_id is None
    assert d.override_kind is None
    assert d.rule is None
    assert d.reasoning is None
    assert d.confidence is None
    assert d.confidence_source is None
    assert d.alternatives == ()
    assert d.inputs is None
    assert d.reasoning_signature is None


# ---------- Error classes ----------


@pytest.mark.unit
def test_decision_already_exists_error_carries_decision_id() -> None:
    decision_id = uuid4()
    err = DecisionAlreadyExistsError(decision_id)
    assert err.decision_id == decision_id
    assert str(decision_id) in str(err)


@pytest.mark.unit
def test_decision_not_found_error_carries_decision_id() -> None:
    decision_id = uuid4()
    err = DecisionNotFoundError(decision_id)
    assert err.decision_id == decision_id
    assert str(decision_id) in str(err)


@pytest.mark.unit
def test_decider_actor_missing_error_carries_decided_by() -> None:
    decided_by = uuid4()
    err = DeciderActorNotFoundError(decided_by)
    assert err.decided_by == decided_by
    assert str(decided_by) in str(err)


@pytest.mark.unit
def test_parent_decision_missing_error_carries_parent_id() -> None:
    parent_id = uuid4()
    err = DecisionParentNotFoundError(parent_id)
    assert err.parent_id == parent_id
    assert str(parent_id) in str(err)


@pytest.mark.unit
def test_override_kind_requires_parent_error_carries_kind() -> None:
    err = OverrideKindRequiresParentError("correction")
    assert err.override_kind == "correction"
    assert "correction" in str(err)
