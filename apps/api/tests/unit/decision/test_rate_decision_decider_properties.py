"""Property-based tests for `rate_decision.decide` (Decision BC).

Complements the example-based `test_rate_decision_decider.py` with
universal claims across generated inputs. The decider is pure

    (state, command, now, rated_by) -> list[DecisionRated]

Rating has no source-state guard (multiple ratings per actor are
allowed; latest-per-actor wins at fold time), so the universal claims
are about existence, field threading, and purity:

  - state=None always raises `DecisionNotFoundError` carrying
    command.decision_id.
  - A non-None state emits exactly one `DecisionRated` carrying the
    threaded rating + comment + rated_by, rated_at=occurred_at=now, and
    confidence_at_rating snapshotted from state.confidence.
  - The emitted event's decision_id is `state.id`, never
    command.decision_id.
  - Pure: same (state, command, now, rated_by) returns equal events.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.decision.aggregates.decision import (
    Decision,
    DecisionChoice,
    DecisionContext,
    DecisionNotFoundError,
    DecisionRated,
    DecisionRating,
)
from cora.decision.features import rate_decision
from cora.decision.features.rate_decision import RateDecision
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

_RATING = st.sampled_from(list(DecisionRating))
_COMMENT = st.one_of(st.none(), printable_ascii_text(min_size=1, max_size=500))
_FIXED_DECIDED_AT = datetime(2026, 1, 1, tzinfo=UTC)
_FIXED_DECIDED_BY = UUID(int=3)


def _decision(*, decision_id: UUID) -> Decision:
    return Decision(
        id=decision_id,
        decided_by=ActorId(_FIXED_DECIDED_BY),
        decided_at=_FIXED_DECIDED_AT,
        context=DecisionContext("RunDebrief"),
        choice=DecisionChoice("NominalCompletion"),
    )


@pytest.mark.unit
@given(
    decision_id=st.uuids(),
    rating=_RATING,
    comment=_COMMENT,
    now=aware_datetimes(),
    rated_by_uuid=st.uuids(),
)
def test_rate_with_none_state_always_raises_not_found(
    decision_id: UUID,
    rating: DecisionRating,
    comment: str | None,
    now: datetime,
    rated_by_uuid: UUID,
) -> None:
    """Empty stream always raises `DecisionNotFoundError` carrying command.decision_id."""
    with pytest.raises(DecisionNotFoundError) as exc:
        rate_decision.decide(
            state=None,
            command=RateDecision(decision_id=decision_id, rating=rating, comment=comment),
            now=now,
            rated_by=ActorId(rated_by_uuid),
        )
    assert exc.value.decision_id == decision_id


@pytest.mark.unit
@given(
    decision_id=st.uuids(),
    rating=_RATING,
    comment=_COMMENT,
    now=aware_datetimes(),
    rated_by_uuid=st.uuids(),
)
def test_rate_existing_decision_emits_single_event(
    decision_id: UUID,
    rating: DecisionRating,
    comment: str | None,
    now: datetime,
    rated_by_uuid: UUID,
) -> None:
    """A non-None state emits one DecisionRated with the threaded fields."""
    rated_by = ActorId(rated_by_uuid)
    state = _decision(decision_id=decision_id)
    events = rate_decision.decide(
        state=state,
        command=RateDecision(decision_id=decision_id, rating=rating, comment=comment),
        now=now,
        rated_by=rated_by,
    )
    assert events == [
        DecisionRated(
            decision_id=decision_id,
            rating=rating,
            comment=comment,
            rated_by=rated_by,
            rated_at=now,
            occurred_at=now,
            confidence_at_rating=state.confidence,
        )
    ]


@pytest.mark.unit
@given(
    state_decision_id=st.uuids(),
    command_decision_id=st.uuids(),
    rating=_RATING,
    now=aware_datetimes(),
    rated_by_uuid=st.uuids(),
)
def test_rate_uses_state_id_not_command_decision_id(
    state_decision_id: UUID,
    command_decision_id: UUID,
    rating: DecisionRating,
    now: datetime,
    rated_by_uuid: UUID,
) -> None:
    """The emitted event's decision_id is state.id, not command.decision_id."""
    assume(state_decision_id != command_decision_id)
    events = rate_decision.decide(
        state=_decision(decision_id=state_decision_id),
        command=RateDecision(decision_id=command_decision_id, rating=rating),
        now=now,
        rated_by=ActorId(rated_by_uuid),
    )
    assert events[0].decision_id == state_decision_id


@pytest.mark.unit
@given(
    decision_id=st.uuids(),
    rating=_RATING,
    comment=_COMMENT,
    now=aware_datetimes(),
    rated_by_uuid=st.uuids(),
)
def test_rate_is_pure_same_input_same_output(
    decision_id: UUID,
    rating: DecisionRating,
    comment: str | None,
    now: datetime,
    rated_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _decision(decision_id=decision_id)
    command = RateDecision(decision_id=decision_id, rating=rating, comment=comment)
    rated_by = ActorId(rated_by_uuid)
    first = rate_decision.decide(state=state, command=command, now=now, rated_by=rated_by)
    second = rate_decision.decide(state=state, command=command, now=now, rated_by=rated_by)
    assert first == second
