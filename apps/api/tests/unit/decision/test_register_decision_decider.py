"""Unit tests for the `register_decision` slice's pure decider."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from cora.access.aggregates.actor import Actor, ActorKind
from cora.decision.aggregates.decision import (
    Decision,
    DecisionAlreadyExistsError,
    DecisionChoice,
    DecisionConfidenceSource,
    DecisionContext,
    DecisionParentNotFoundError,
    InvalidDecisionAlternativesError,
    InvalidDecisionChoiceError,
    InvalidDecisionConfidenceError,
    InvalidDecisionContextError,
    InvalidDecisionInputsError,
    InvalidDecisionReasoningError,
    InvalidDecisionRuleError,
)
from cora.decision.errors import (
    InvalidActorKindForDecisionError,
    OverrideKindRequiresParentError,
)
from cora.decision.features import register_decision
from cora.decision.features.register_decision import (
    DecisionRegistrationContext,
    RegisterDecision,
)
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _actor() -> Actor:
    return Actor(id=uuid4())


def _good_command(**overrides: Any) -> RegisterDecision:
    base: dict[str, Any] = {
        "decided_by": ActorId(uuid4()),
        "context": "RecipeApproval",
        "choice": "Approved",
        "parent_id": None,
        "override_kind": None,
        "rule": None,
        "reasoning": None,
        "confidence": None,
        "confidence_source": None,
        "alternatives": (),
        "inputs": None,
        "reasoning_signature": None,
    }
    base.update(overrides)
    return RegisterDecision(**base)


def _existing_decision() -> Decision:
    return Decision(
        id=uuid4(),
        decided_by=ActorId(uuid4()),
        decided_at=_NOW,
        context=DecisionContext("RecipeApproval"),
        choice=DecisionChoice("Approved"),
    )


# ---------- Happy path ----------


@pytest.mark.unit
def test_decide_emits_decision_registered_with_minimum_fields() -> None:
    new_id = uuid4()
    decided_by = ActorId(uuid4())
    cmd = _good_command(decided_by=decided_by)
    events = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=_actor()),
        now=_NOW,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert event.decision_id == new_id
    assert event.decided_by == decided_by
    assert event.context == "RecipeApproval"
    assert event.choice == "Approved"
    assert event.parent_id is None
    assert event.override_kind is None
    assert event.alternatives == ()
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decide_trims_choice_via_value_object() -> None:
    cmd = _good_command(choice="  trimmed  ")
    events = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=_actor()),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].choice == "trimmed"


@pytest.mark.unit
def test_decide_passes_optional_fields_through() -> None:
    parent_id = uuid4()
    cmd = _good_command(
        parent_id=parent_id,
        override_kind="exception",
        rule="iso17025:7.1.3:simple_acceptance",
        reasoning="Operator override after re-check.",
        confidence=0.85,
        confidence_source=DecisionConfidenceSource.HUMAN,
        alternatives=("Approve", "Reject", "Re-measure"),
        inputs={"measured": 1.2, "limit": 1.5},
        reasoning_signature="sha256:abc",
    )
    events = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=_actor(), parent=_existing_decision()),
        now=_NOW,
        new_id=uuid4(),
    )
    e = events[0]
    assert e.parent_id == parent_id
    assert e.override_kind == "exception"
    assert e.rule == "iso17025:7.1.3:simple_acceptance"
    assert e.reasoning == "Operator override after re-check."
    assert e.confidence == 0.85
    assert e.confidence_source is DecisionConfidenceSource.HUMAN
    assert e.alternatives == ("Approve", "Reject", "Re-measure")
    assert e.inputs == {"measured": 1.2, "limit": 1.5}
    assert e.reasoning_signature == "sha256:abc"


# ---------- Field validation ----------


@pytest.mark.unit
def test_decide_raises_invalid_choice_for_blank() -> None:
    cmd = _good_command(choice="   ")
    with pytest.raises(InvalidDecisionChoiceError):
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_context_for_blank() -> None:
    cmd = _good_command(context="")
    with pytest.raises(InvalidDecisionContextError):
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_rule_for_blank() -> None:
    cmd = _good_command(rule="   ")
    with pytest.raises(InvalidDecisionRuleError):
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_reasoning_for_too_long() -> None:
    cmd = _good_command(reasoning="a" * 6000)
    with pytest.raises(InvalidDecisionReasoningError):
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_confidence_out_of_range() -> None:
    cmd = _good_command(confidence=1.5)
    with pytest.raises(InvalidDecisionConfidenceError):
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_alternatives_for_blank_entry() -> None:
    cmd = _good_command(alternatives=("Hold", "", "Stop"))
    with pytest.raises(InvalidDecisionAlternativesError):
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_inputs_for_blank_key() -> None:
    cmd = _good_command(inputs={"": 1})
    with pytest.raises(InvalidDecisionInputsError):
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )


# ---------- override_kind / parent_id consistency ----------


@pytest.mark.unit
def test_decide_raises_override_kind_requires_parent_when_no_parent() -> None:
    cmd = _good_command(override_kind="correction")
    with pytest.raises(OverrideKindRequiresParentError) as exc_info:
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.override_kind == "correction"


@pytest.mark.unit
def test_decide_accepts_parent_without_override_kind() -> None:
    """Parent without override_kind is valid (vague chain reference)."""
    parent_id = uuid4()
    cmd = _good_command(parent_id=parent_id)
    events = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=_actor(), parent=_existing_decision()),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].override_kind is None


@pytest.mark.unit
def test_decide_accepts_invalidation_override_kind() -> None:
    """`invalidation` is the 5th override_kind value (post-Q4 compensation
    primitive; see [[project-dataset-demote-design]] + Decision state.py).
    Maps to PROV-O `wasInvalidatedBy` on the activity side. Used when a
    new Decision's authorized action UNDOES the effect of the parent
    Decision (for example, demote_dataset paired with a Decision that points
    back at the prior promote-driving Decision)."""
    parent_id = uuid4()
    cmd = _good_command(parent_id=parent_id, override_kind="invalidation")
    events = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=_actor(), parent=_existing_decision()),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].override_kind == "invalidation"
    assert events[0].parent_id == parent_id


@pytest.mark.unit
def test_decide_raises_invalidation_without_parent() -> None:
    """`invalidation` follows the same parent_id-required rule as the
    other 4 override_kind values: a Decision claiming to invalidate
    another must reference WHICH Decision it invalidates."""
    cmd = _good_command(override_kind="invalidation")
    with pytest.raises(OverrideKindRequiresParentError) as exc_info:
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.override_kind == "invalidation"


# ---------- Codified design choices (lax stances; intentional non-enforcement) ----------


@pytest.mark.unit
def test_decide_accepts_confidence_without_confidence_source() -> None:
    """The BC does NOT enforce the confidence + confidence_source
    pairing convention. Either field can be set independently;
    auditors flag bare-confidence-without-source records at
    projection time."""
    cmd = _good_command(confidence=0.92, confidence_source=None)
    events = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=_actor()),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].confidence == 0.92
    assert events[0].confidence_source is None


@pytest.mark.unit
def test_decide_accepts_confidence_source_without_confidence() -> None:
    """Inverse pairing-not-enforced case: source without numeric value."""
    cmd = _good_command(confidence=None, confidence_source=DecisionConfidenceSource.ENSEMBLE)
    events = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=_actor()),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].confidence is None
    assert events[0].confidence_source is DecisionConfidenceSource.ENSEMBLE


@pytest.mark.unit
def test_decide_accepts_rule_none_for_procedure_execution_context() -> None:
    """The BC does NOT enforce 'rule required for
    ProcedureExecution / RecipeApproval'. Context-conditional
    requiredness is a projection-time audit-policy concern."""
    cmd = _good_command(context="ProcedureExecution", rule=None)
    events = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=_actor()),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].rule is None


@pytest.mark.unit
def test_decide_accepts_arbitrary_context_value() -> None:
    """Q5 lock A: context is open-string. New contexts arrive
    without schema migration; well-known-value validation is a
    projection-time concern."""
    cmd = _good_command(context="FacilityCustom_v3")
    events = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=_actor()),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].context == "FacilityCustom_v3"


# ---------- Actor-kind invariant ----------


@pytest.mark.unit
def test_decide_raises_when_actor_kind_is_agent() -> None:
    """Agent-emitted Decisions go through the signed subscriber path
    (CautionDrafter, RunDebriefer) per [[project_signed_events_design]].
    The operator-driven register_decision slice refuses kind=AGENT so it
    cannot become a signing-bypass route."""
    agent_actor = Actor(id=uuid4(), kind=ActorKind.AGENT)
    cmd = _good_command(decided_by=ActorId(agent_actor.id))
    with pytest.raises(InvalidActorKindForDecisionError) as exc_info:
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=agent_actor),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.kind == "agent"


@pytest.mark.unit
def test_decide_accepts_service_account_actor() -> None:
    """Service-account Actors are first-class register_decision principals
    (machine callers like CI bridges); only AGENT is refused here."""
    sa_actor = Actor(id=uuid4(), kind=ActorKind.SERVICE_ACCOUNT)
    cmd = _good_command(decided_by=ActorId(sa_actor.id))
    events = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=sa_actor),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].decided_by == sa_actor.id


# ---------- Cross-aggregate validation ----------


@pytest.mark.unit
def test_decide_raises_when_parent_id_set_but_context_missing() -> None:
    """Defensive: if handler skipped its load, decider raises."""
    parent_id = uuid4()
    cmd = _good_command(parent_id=parent_id)
    with pytest.raises(DecisionParentNotFoundError):
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor(), parent=None),
            now=_NOW,
            new_id=uuid4(),
        )


# ---------- Strict-not-idempotent ----------


@pytest.mark.unit
def test_decide_raises_already_exists_when_state_not_none() -> None:
    existing = _existing_decision()
    with pytest.raises(DecisionAlreadyExistsError) as exc_info:
        register_decision.decide(
            state=existing,
            command=_good_command(),
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.decision_id == existing.id


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    cmd = _good_command()
    actor = _actor()
    first = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=actor),
        now=_NOW,
        new_id=new_id,
    )
    second = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=actor),
        now=_NOW,
        new_id=new_id,
    )
    assert first == second
