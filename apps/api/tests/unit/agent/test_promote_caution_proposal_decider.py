"""Pure-decider tests for the `promote_caution_proposal` slice."""

from typing import Any
from uuid import uuid4

import pytest

from cora.agent.errors import (
    CautionProposalMalformedError,
    CautionProposalNotActionableError,
    DecisionNotCautionProposalError,
)
from cora.agent.features.promote_caution_proposal.command import PromoteCautionProposal
from cora.agent.features.promote_caution_proposal.decider import decide
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_CAUTION_PROPOSAL,
    DECISION_CONTEXT_RUN_DEBRIEF,
    Decision,
    DecisionChoice,
    DecisionContext,
    DecisionNotFoundError,
)
from cora.shared.identity import ActorId


def _decision(
    *,
    decision_id: object | None = None,
    context: str = DECISION_CONTEXT_CAUTION_PROPOSAL,
    choice: str = "ProposeNotice",
    inputs: dict[str, Any] | None = None,
) -> Decision:
    return Decision(
        id=decision_id or uuid4(),  # type: ignore[arg-type]
        decided_by=ActorId(uuid4()),
        context=DecisionContext(context),
        choice=DecisionChoice(choice),
        inputs=inputs,
    )


def _valid_proposed(target_id: object | None = None) -> dict[str, Any]:
    return {
        "target_kind": "Asset",
        "target_id": str(target_id or uuid4()),
        "category": "Wear",
        "severity": "Notice",
        "title": "encoder drift",
        "body": "the encoder drifts when warm; let it warm up 5 minutes",
        "tags": ["encoder", "warm-up"],
    }


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    decision_id = uuid4()
    with pytest.raises(DecisionNotFoundError):
        decide(state=None, command=PromoteCautionProposal(decision_id=decision_id))


@pytest.mark.unit
def test_wrong_context_raises() -> None:
    """Promoting a non-CautionProposal Decision is a 400."""
    decision_id = uuid4()
    state = _decision(
        decision_id=decision_id,
        context=DECISION_CONTEXT_RUN_DEBRIEF,
        choice="NominalCompletion",
        inputs={"proposed_caution": _valid_proposed()},
    )
    with pytest.raises(DecisionNotCautionProposalError):
        decide(state=state, command=PromoteCautionProposal(decision_id=decision_id))


@pytest.mark.unit
def test_no_action_choice_is_not_actionable() -> None:
    decision_id = uuid4()
    state = _decision(
        decision_id=decision_id,
        choice="NoAction",
        inputs={"reason": "no signal worth a caution"},
    )
    with pytest.raises(CautionProposalNotActionableError):
        decide(state=state, command=PromoteCautionProposal(decision_id=decision_id))


@pytest.mark.unit
def test_missing_proposed_caution_payload_raises() -> None:
    decision_id = uuid4()
    state = _decision(decision_id=decision_id, choice="ProposeNotice", inputs={})
    with pytest.raises(CautionProposalMalformedError):
        decide(state=state, command=PromoteCautionProposal(decision_id=decision_id))


@pytest.mark.unit
def test_propose_notice_extracts_view() -> None:
    decision_id = uuid4()
    target_id = uuid4()
    state = _decision(
        decision_id=decision_id,
        choice="ProposeNotice",
        inputs={"proposed_caution": _valid_proposed(target_id=target_id)},
    )
    view = decide(state=state, command=PromoteCautionProposal(decision_id=decision_id))
    assert view.choice == "ProposeNotice"
    assert view.target_kind == "Asset"
    assert view.target_id == target_id
    assert view.category == "Wear"
    assert view.severity == "Notice"
    assert view.title == "encoder drift"
    assert view.tags == ("encoder", "warm-up")
    assert view.supersedes_caution_id is None


@pytest.mark.unit
def test_propose_supersede_requires_supersedes_caution_id() -> None:
    decision_id = uuid4()
    proposed = _valid_proposed()
    # supersedes_caution_id missing
    state = _decision(
        decision_id=decision_id,
        choice="ProposeSupersede",
        inputs={"proposed_caution": proposed},
    )
    with pytest.raises(CautionProposalMalformedError):
        decide(state=state, command=PromoteCautionProposal(decision_id=decision_id))


@pytest.mark.unit
def test_propose_supersede_extracts_supersedes_id() -> None:
    decision_id = uuid4()
    sup_id = uuid4()
    proposed = _valid_proposed()
    proposed["supersedes_caution_id"] = str(sup_id)
    state = _decision(
        decision_id=decision_id,
        choice="ProposeSupersede",
        inputs={"proposed_caution": proposed},
    )
    view = decide(state=state, command=PromoteCautionProposal(decision_id=decision_id))
    assert view.choice == "ProposeSupersede"
    assert view.supersedes_caution_id == sup_id


@pytest.mark.unit
def test_supersedes_caution_id_on_non_supersede_choice_raises() -> None:
    """Cross-check: supersedes field is only valid with ProposeSupersede."""
    decision_id = uuid4()
    proposed = _valid_proposed()
    proposed["supersedes_caution_id"] = str(uuid4())
    state = _decision(
        decision_id=decision_id,
        choice="ProposeNotice",
        inputs={"proposed_caution": proposed},
    )
    with pytest.raises(CautionProposalMalformedError):
        decide(state=state, command=PromoteCautionProposal(decision_id=decision_id))


@pytest.mark.unit
def test_invalid_target_id_uuid_raises() -> None:
    decision_id = uuid4()
    proposed = _valid_proposed()
    proposed["target_id"] = "not-a-uuid"
    state = _decision(
        decision_id=decision_id,
        choice="ProposeNotice",
        inputs={"proposed_caution": proposed},
    )
    with pytest.raises(CautionProposalMalformedError):
        decide(state=state, command=PromoteCautionProposal(decision_id=decision_id))


@pytest.mark.unit
def test_missing_required_proposed_field_raises() -> None:
    decision_id = uuid4()
    proposed = _valid_proposed()
    del proposed["title"]  # required
    state = _decision(
        decision_id=decision_id,
        choice="ProposeNotice",
        inputs={"proposed_caution": proposed},
    )
    with pytest.raises(CautionProposalMalformedError):
        decide(state=state, command=PromoteCautionProposal(decision_id=decision_id))
