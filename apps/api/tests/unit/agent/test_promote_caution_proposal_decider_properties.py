"""Property-based tests for `promote_caution_proposal.decide` (Agent BC).

Complements the example-based `test_promote_caution_proposal_decider.py`
with universal claims across generated inputs. This decider is the
validate-and-extract shape: it takes a loaded `Decision` and a command
and returns a read-only `ProposedCautionView` (NO events, NO clock).

    (state, command) -> ProposedCautionView

Load-bearing properties:

  - state=None always raises `DecisionNotFoundError` carrying
    command.decision_id.
  - A Decision whose context is not "CautionProposal" always raises
    `DecisionNotCautionProposalError`.
  - choice "NoAction" always raises `CautionProposalNotActionableError`.
  - A missing `proposed_caution` payload always raises
    `CautionProposalMalformedError`.
  - choice "ProposeSupersede" without a supersedes_caution_id always
    raises `CautionProposalMalformedError`.
  - On a well-formed actionable proposal the view carries
    decision_id=command.decision_id plus the extracted payload fields.
  - Pure: same (state, command) returns equal views.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.agent.errors import (
    CautionProposalMalformedError,
    CautionProposalNotActionableError,
    DecisionNotCautionProposalError,
)
from cora.agent.features.promote_caution_proposal.command import PromoteCautionProposal
from cora.agent.features.promote_caution_proposal.decider import decide
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_CAUTION_PROPOSAL,
    Decision,
    DecisionChoice,
    DecisionContext,
    DecisionNotFoundError,
)
from cora.shared.identity import ActorId

_FIXED_DECIDED_AT = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)
_FIXED_DECIDER = ActorId(UUID(int=3))


def _decision(
    *,
    decision_id: UUID,
    context: str = DECISION_CONTEXT_CAUTION_PROPOSAL,
    choice: str = "ProposeCaution",
    inputs: dict[str, Any] | None = None,
) -> Decision:
    return Decision(
        id=decision_id,
        decided_by=_FIXED_DECIDER,
        decided_at=_FIXED_DECIDED_AT,
        context=DecisionContext(context),
        choice=DecisionChoice(choice),
        inputs=inputs,
    )


def _proposed(*, target_id: UUID) -> dict[str, Any]:
    return {
        "target_kind": "Asset",
        "target_id": str(target_id),
        "category": "Wear",
        "severity": "Notice",
        "title": "encoder drift",
        "body": "the encoder drifts when warm; let it warm up 5 minutes",
        "tags": ["encoder", "warm-up"],
    }


@pytest.mark.unit
@given(decision_id=st.uuids())
def test_promote_with_none_state_always_raises_not_found(decision_id: UUID) -> None:
    """Empty stream always raises `DecisionNotFoundError` carrying command.decision_id."""
    with pytest.raises(DecisionNotFoundError):
        decide(state=None, command=PromoteCautionProposal(decision_id=decision_id))


@pytest.mark.unit
@given(decision_id=st.uuids(), target_id=st.uuids())
def test_promote_non_caution_proposal_context_always_raises_wrong_context(
    decision_id: UUID,
    target_id: UUID,
) -> None:
    """A Decision whose context is not CautionProposal raises DecisionNotCautionProposalError."""
    state = _decision(
        decision_id=decision_id,
        context="RunDebrief",
        choice="NominalCompletion",
        inputs={"proposed_caution": _proposed(target_id=target_id)},
    )
    with pytest.raises(DecisionNotCautionProposalError):
        decide(state=state, command=PromoteCautionProposal(decision_id=decision_id))


@pytest.mark.unit
@given(decision_id=st.uuids())
def test_promote_no_action_choice_always_raises_not_actionable(decision_id: UUID) -> None:
    """NoAction choice (with the right context) is not actionable."""
    state = _decision(
        decision_id=decision_id,
        choice="NoAction",
        inputs={"reason": "no signal worth a caution"},
    )
    with pytest.raises(CautionProposalNotActionableError):
        decide(state=state, command=PromoteCautionProposal(decision_id=decision_id))


@pytest.mark.unit
@given(decision_id=st.uuids())
def test_promote_missing_payload_always_raises_malformed(decision_id: UUID) -> None:
    """A missing proposed_caution payload raises CautionProposalMalformedError."""
    state = _decision(decision_id=decision_id, choice="ProposeCaution", inputs={})
    with pytest.raises(CautionProposalMalformedError):
        decide(state=state, command=PromoteCautionProposal(decision_id=decision_id))


@pytest.mark.unit
@given(decision_id=st.uuids(), target_id=st.uuids())
def test_promote_supersede_without_supersedes_id_always_raises_malformed(
    decision_id: UUID,
    target_id: UUID,
) -> None:
    """ProposeSupersede with no supersedes_caution_id is malformed."""
    state = _decision(
        decision_id=decision_id,
        choice="ProposeSupersede",
        inputs={"proposed_caution": _proposed(target_id=target_id)},
    )
    with pytest.raises(CautionProposalMalformedError):
        decide(state=state, command=PromoteCautionProposal(decision_id=decision_id))


@pytest.mark.unit
@given(decision_id=st.uuids(), target_id=st.uuids())
def test_promote_actionable_proposal_returns_extracted_view(
    decision_id: UUID,
    target_id: UUID,
) -> None:
    """A well-formed actionable proposal returns the extracted ProposedCautionView."""
    state = _decision(
        decision_id=decision_id,
        choice="ProposeCaution",
        inputs={"proposed_caution": _proposed(target_id=target_id)},
    )
    view = decide(state=state, command=PromoteCautionProposal(decision_id=decision_id))
    assert view.decision_id == decision_id
    assert view.choice == "ProposeCaution"
    assert view.target_kind == "Asset"
    assert view.target_id == target_id
    assert view.category == "Wear"
    assert view.severity == "Notice"
    assert view.tags == ("encoder", "warm-up")
    assert view.supersedes_caution_id is None


@pytest.mark.unit
@given(decision_id=st.uuids(), target_id=st.uuids())
def test_promote_is_pure_same_input_same_output(decision_id: UUID, target_id: UUID) -> None:
    """Two calls with identical args return equal views."""
    state = _decision(
        decision_id=decision_id,
        choice="ProposeCaution",
        inputs={"proposed_caution": _proposed(target_id=target_id)},
    )
    command = PromoteCautionProposal(decision_id=decision_id)
    assert decide(state=state, command=command) == decide(state=state, command=command)
