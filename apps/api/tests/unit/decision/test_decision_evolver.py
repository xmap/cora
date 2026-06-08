"""Unit tests for the Decision evolver."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.decision.aggregates.decision import (
    DecisionConfidenceSource,
    DecisionRegistered,
    evolve,
    fold,
)
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_registered_creates_decision_with_required_fields() -> None:
    decision_id = uuid4()
    decided_by = ActorId(uuid4())
    event = DecisionRegistered(
        decision_id=decision_id,
        decided_by=decided_by,
        context="RecipeApproval",
        choice="Approved",
        parent_id=None,
        override_kind=None,
        rule=None,
        reasoning=None,
        confidence=None,
        confidence_source=None,
        alternatives=(),
        inputs=None,
        reasoning_signature=None,
        occurred_at=_NOW,
    )
    state = evolve(state=None, event=event)
    assert state.id == decision_id
    assert state.decided_by == decided_by
    assert state.decided_at == _NOW
    assert state.context.value == "RecipeApproval"
    assert state.choice.value == "Approved"


@pytest.mark.unit
def test_evolve_registered_preserves_optional_fields() -> None:
    parent_id = uuid4()
    inputs = {"measured": 1.0, "limit": 2.0}
    event = DecisionRegistered(
        decision_id=uuid4(),
        decided_by=ActorId(uuid4()),
        context="ProcedureExecution",
        choice="Pass",
        parent_id=parent_id,
        override_kind="correction",
        rule="iso17025:7.1.3:simple_acceptance",
        reasoning="Checked twice.",
        confidence=0.95,
        confidence_source=DecisionConfidenceSource.ENSEMBLE,
        alternatives=("Pass", "Fail", "Re-measure"),
        inputs=inputs,
        reasoning_signature="sig:xyz",
        occurred_at=_NOW,
    )
    state = evolve(state=None, event=event)
    assert state.parent_id == parent_id
    assert state.override_kind == "correction"
    assert state.rule is not None
    assert state.rule.value == "iso17025:7.1.3:simple_acceptance"
    assert state.reasoning == "Checked twice."
    assert state.confidence == 0.95
    assert state.confidence_source is DecisionConfidenceSource.ENSEMBLE
    assert state.alternatives == ("Pass", "Fail", "Re-measure")
    assert state.inputs == inputs
    assert state.reasoning_signature == "sig:xyz"


@pytest.mark.unit
def test_fold_empty_stream_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_event_returns_decision() -> None:
    event = DecisionRegistered(
        decision_id=uuid4(),
        decided_by=ActorId(uuid4()),
        context="RunAbort",
        choice="Abort",
        parent_id=None,
        override_kind=None,
        rule=None,
        reasoning=None,
        confidence=None,
        confidence_source=None,
        alternatives=(),
        inputs=None,
        reasoning_signature=None,
        occurred_at=_NOW,
    )
    state = fold([event])
    assert state is not None
    assert state.context.value == "RunAbort"
