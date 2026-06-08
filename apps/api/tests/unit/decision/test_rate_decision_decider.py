"""Pure-decider tests for the `rate_decision` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.decision.aggregates.decision import (
    DECISION_RATING_COMMENT_MAX_LENGTH,
    Decision,
    DecisionChoice,
    DecisionContext,
    DecisionNotFoundError,
    DecisionRated,
    DecisionRating,
    InvalidDecisionRatingCommentError,
)
from cora.decision.features.rate_decision.command import RateDecision
from cora.decision.features.rate_decision.decider import decide
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_RATER_ID = ActorId(uuid4())


def _decision(*, decision_id: object | None = None) -> Decision:
    return Decision(
        id=decision_id or uuid4(),  # type: ignore[arg-type]
        decided_by=ActorId(uuid4()),
        decided_at=_NOW,
        context=DecisionContext("RunDebrief"),
        choice=DecisionChoice("NominalCompletion"),
    )


@pytest.mark.unit
def test_emits_single_decision_rated_event() -> None:
    d = _decision()
    events = decide(
        state=d,
        command=RateDecision(decision_id=d.id, rating=DecisionRating.USEFUL),
        now=_NOW,
        rated_by=_RATER_ID,
    )
    assert len(events) == 1
    assert isinstance(events[0], DecisionRated)
    e = events[0]
    assert e.decision_id == d.id
    assert e.rating is DecisionRating.USEFUL
    assert e.comment is None
    assert e.rated_by == _RATER_ID
    assert e.rated_at == _NOW


@pytest.mark.unit
def test_carries_optional_comment_trimmed() -> None:
    d = _decision()
    events = decide(
        state=d,
        command=RateDecision(
            decision_id=d.id,
            rating=DecisionRating.MISLEADING,
            comment="  flagged the wrong thing  ",
        ),
        now=_NOW,
        rated_by=_RATER_ID,
    )
    assert events[0].comment == "flagged the wrong thing"


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    with pytest.raises(DecisionNotFoundError):
        decide(
            state=None,
            command=RateDecision(decision_id=uuid4(), rating=DecisionRating.USEFUL),
            now=_NOW,
            rated_by=_RATER_ID,
        )


@pytest.mark.unit
def test_invalid_comment_raises() -> None:
    d = _decision()
    with pytest.raises(InvalidDecisionRatingCommentError):
        decide(
            state=d,
            command=RateDecision(
                decision_id=d.id,
                rating=DecisionRating.IGNORED,
                comment="   ",  # whitespace-only rejected (callers pass None)
            ),
            now=_NOW,
            rated_by=_RATER_ID,
        )


@pytest.mark.unit
def test_over_cap_comment_raises() -> None:
    d = _decision()
    with pytest.raises(InvalidDecisionRatingCommentError):
        decide(
            state=d,
            command=RateDecision(
                decision_id=d.id,
                rating=DecisionRating.USEFUL,
                comment="x" * (DECISION_RATING_COMMENT_MAX_LENGTH + 1),
            ),
            now=_NOW,
            rated_by=_RATER_ID,
        )


@pytest.mark.unit
def test_multiple_ratings_from_same_actor_not_rejected_at_decider() -> None:
    """Multiple ratings are valid; the evolver folds latest-per-actor wins.

    The decider deliberately does NOT raise on a duplicate from the
    same actor: operators can change their mind, the audit trail
    keeps all events, the projection takes the latest.
    """
    d = _decision()
    # Simulate state with an existing rating; the decider doesn't
    # check `state.ratings`, so it always succeeds.
    events = decide(
        state=d,
        command=RateDecision(decision_id=d.id, rating=DecisionRating.MISLEADING),
        now=_NOW,
        rated_by=_RATER_ID,
    )
    assert len(events) == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    "rating",
    [DecisionRating.USEFUL, DecisionRating.MISLEADING, DecisionRating.IGNORED],
)
def test_each_rating_value_accepted(rating: DecisionRating) -> None:
    d = _decision()
    events = decide(
        state=d,
        command=RateDecision(decision_id=d.id, rating=rating),
        now=_NOW,
        rated_by=_RATER_ID,
    )
    assert events[0].rating is rating
