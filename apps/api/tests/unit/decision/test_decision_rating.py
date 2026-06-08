"""Tests for the rating additions to Decision state + event + evolver.

Covers DecisionRating enum, DecisionRatingRecord, Decision.ratings
field, validate_decision_rating_comment helper,
InvalidDecisionRatingCommentError, RUN_DEBRIEF_CHOICES + RunDebriefChoice
constants, DecisionRated event round-trip, evolver fold (including
out-of-order replay safety + cross-actor independence).
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_RUN_DEBRIEF,
    DECISION_RATING_COMMENT_MAX_LENGTH,
    RUN_DEBRIEF_CHOICES,
    Decision,
    DecisionChoice,
    DecisionContext,
    DecisionRated,
    DecisionRating,
    DecisionRatingRecord,
    DecisionRegistered,
    InvalidDecisionRatingCommentError,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.decision.aggregates.decision.evolver import fold
from cora.decision.aggregates.decision.state import validate_decision_rating_comment
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId

_T0 = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_T1 = _T0 + timedelta(minutes=10)
_T2 = _T0 + timedelta(minutes=20)


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Decision",
        stream_id=uuid4(),
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_T0,
        recorded_at=_T0,
    )


# ---------- Constants + enum ----------


@pytest.mark.unit
def test_decision_context_run_debrief_constant() -> None:
    assert DECISION_CONTEXT_RUN_DEBRIEF == "RunDebrief"


@pytest.mark.unit
def test_run_debrief_choices_closed_set() -> None:
    assert (
        frozenset(
            {
                "NominalCompletion",
                "DegradedCompletion",
                "OperatorAbort",
                "EquipmentAbort",
                "DataSuspect",
                "DebriefDeferred",
                "DebriefConflicted",
            }
        )
        == RUN_DEBRIEF_CHOICES
    )


@pytest.mark.unit
def test_decision_rating_enum_values() -> None:
    assert DecisionRating.USEFUL.value == "useful"
    assert DecisionRating.MISLEADING.value == "misleading"
    assert DecisionRating.IGNORED.value == "ignored"


# ---------- validate_decision_rating_comment ----------


@pytest.mark.unit
def test_validate_comment_returns_none_for_none() -> None:
    assert validate_decision_rating_comment(None) is None


@pytest.mark.unit
def test_validate_comment_trims_whitespace() -> None:
    assert validate_decision_rating_comment("  ok  ") == "ok"


@pytest.mark.unit
def test_validate_comment_rejects_empty_string() -> None:
    with pytest.raises(InvalidDecisionRatingCommentError):
        validate_decision_rating_comment("")


@pytest.mark.unit
def test_validate_comment_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidDecisionRatingCommentError):
        validate_decision_rating_comment("   ")


@pytest.mark.unit
def test_validate_comment_rejects_over_cap() -> None:
    with pytest.raises(InvalidDecisionRatingCommentError):
        validate_decision_rating_comment("x" * (DECISION_RATING_COMMENT_MAX_LENGTH + 1))


# ---------- DecisionRatingRecord ----------


@pytest.mark.unit
def test_decision_rating_record_is_frozen() -> None:
    from dataclasses import FrozenInstanceError

    record = DecisionRatingRecord(rating=DecisionRating.USEFUL, comment="good", rated_at=_T0)
    with pytest.raises(FrozenInstanceError):
        record.rating = DecisionRating.MISLEADING  # type: ignore[misc]


# ---------- Decision.ratings field ----------


@pytest.mark.unit
def test_decision_defaults_to_empty_ratings() -> None:
    d = Decision(
        id=uuid4(),
        decided_by=ActorId(uuid4()),
        decided_at=_T0,
        context=DecisionContext("RunDebrief"),
        choice=DecisionChoice("NominalCompletion"),
    )
    assert d.ratings == {}


# ---------- DecisionRated event round-trip ----------


@pytest.mark.unit
def test_decision_rated_event_type_name() -> None:
    e = DecisionRated(
        decision_id=uuid4(),
        rating=DecisionRating.USEFUL,
        comment=None,
        rated_by=ActorId(uuid4()),
        rated_at=_T0,
        occurred_at=_T0,
        confidence_at_rating=None,
    )
    assert event_type_name(e) == "DecisionRated"


@pytest.mark.unit
def test_decision_rated_to_payload_with_comment_and_confidence() -> None:
    decision_id = uuid4()
    actor_id = uuid4()
    e = DecisionRated(
        decision_id=decision_id,
        rating=DecisionRating.MISLEADING,
        comment="missed the obvious anomaly",
        rated_by=ActorId(actor_id),
        rated_at=_T0,
        occurred_at=_T0,
        confidence_at_rating=0.82,
    )
    assert to_payload(e) == {
        "decision_id": str(decision_id),
        "rating": "misleading",
        "comment": "missed the obvious anomaly",
        "rated_by": str(actor_id),
        "rated_at": _T0.isoformat(),
        "occurred_at": _T0.isoformat(),
        "confidence_at_rating": 0.82,
    }


@pytest.mark.unit
def test_decision_rated_to_payload_without_comment() -> None:
    e = DecisionRated(
        decision_id=uuid4(),
        rating=DecisionRating.IGNORED,
        comment=None,
        rated_by=ActorId(uuid4()),
        rated_at=_T0,
        occurred_at=_T0,
        confidence_at_rating=None,
    )
    assert to_payload(e)["comment"] is None


@pytest.mark.unit
def test_decision_rated_round_trip() -> None:
    original = DecisionRated(
        decision_id=uuid4(),
        rating=DecisionRating.USEFUL,
        comment="exactly right",
        rated_by=ActorId(uuid4()),
        rated_at=_T0,
        occurred_at=_T0,
        confidence_at_rating=None,
    )
    stored = _stored("DecisionRated", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_decision_rated_round_trip_null_comment() -> None:
    original = DecisionRated(
        decision_id=uuid4(),
        rating=DecisionRating.IGNORED,
        comment=None,
        rated_by=ActorId(uuid4()),
        rated_at=_T0,
        occurred_at=_T0,
        confidence_at_rating=None,
    )
    stored = _stored("DecisionRated", to_payload(original))
    assert from_stored(stored) == original


# ---------- Evolver fold ----------


def _genesis(*, decision_id: object | None = None) -> DecisionRegistered:
    return DecisionRegistered(
        decision_id=decision_id or uuid4(),  # type: ignore[arg-type]
        decided_by=ActorId(uuid4()),
        context="RunDebrief",
        choice="NominalCompletion",
        parent_id=None,
        override_kind=None,
        rule=None,
        reasoning=None,
        confidence=None,
        confidence_source=None,
        alternatives=(),
        inputs=None,
        reasoning_signature=None,
        occurred_at=_T0,
    )


@pytest.mark.unit
def test_genesis_then_rated_folds_to_state_with_rating() -> None:
    decision_id = uuid4()
    rater_id = uuid4()
    e1 = _genesis(decision_id=decision_id)
    e2 = DecisionRated(
        decision_id=decision_id,
        rating=DecisionRating.USEFUL,
        comment="helpful",
        rated_by=ActorId(rater_id),
        rated_at=_T1,
        occurred_at=_T1,
        confidence_at_rating=None,
    )
    state = fold([e1, e2])
    assert state is not None
    assert rater_id in state.ratings
    record = state.ratings[rater_id]
    assert record.rating is DecisionRating.USEFUL
    assert record.comment == "helpful"
    assert record.rated_at == _T1


@pytest.mark.unit
def test_latest_per_actor_wins() -> None:
    """Second rating from same actor with later timestamp overwrites first."""
    decision_id = uuid4()
    rater_id = uuid4()
    e1 = _genesis(decision_id=decision_id)
    e2 = DecisionRated(
        decision_id=decision_id,
        rating=DecisionRating.MISLEADING,
        comment=None,
        rated_by=ActorId(rater_id),
        rated_at=_T1,
        occurred_at=_T1,
        confidence_at_rating=None,
    )
    e3 = DecisionRated(
        decision_id=decision_id,
        rating=DecisionRating.USEFUL,
        comment="changed my mind on review",
        rated_by=ActorId(rater_id),
        rated_at=_T2,
        occurred_at=_T2,
        confidence_at_rating=None,
    )
    state = fold([e1, e2, e3])
    assert state is not None
    assert state.ratings[rater_id].rating is DecisionRating.USEFUL
    assert state.ratings[rater_id].comment == "changed my mind on review"
    assert state.ratings[rater_id].rated_at == _T2


@pytest.mark.unit
def test_out_of_order_replay_preserves_newer_rating() -> None:
    """If an older rating event lands after a newer one (replay
    rebuild crossing streams), the newer state is preserved."""
    decision_id = uuid4()
    rater_id = uuid4()
    e1 = _genesis(decision_id=decision_id)
    newer = DecisionRated(
        decision_id=decision_id,
        rating=DecisionRating.USEFUL,
        comment="newer",
        rated_by=ActorId(rater_id),
        rated_at=_T2,
        occurred_at=_T2,
        confidence_at_rating=None,
    )
    older = DecisionRated(
        decision_id=decision_id,
        rating=DecisionRating.MISLEADING,
        comment="older",
        rated_by=ActorId(rater_id),
        rated_at=_T1,
        occurred_at=_T1,
        confidence_at_rating=None,
    )
    state = fold([e1, newer, older])
    assert state is not None
    assert state.ratings[rater_id].rating is DecisionRating.USEFUL
    assert state.ratings[rater_id].comment == "newer"


@pytest.mark.unit
def test_ratings_from_different_actors_independent() -> None:
    decision_id = uuid4()
    rater_a = uuid4()
    rater_b = uuid4()
    e1 = _genesis(decision_id=decision_id)
    e2 = DecisionRated(
        decision_id=decision_id,
        rating=DecisionRating.USEFUL,
        comment=None,
        rated_by=ActorId(rater_a),
        rated_at=_T1,
        occurred_at=_T1,
        confidence_at_rating=None,
    )
    e3 = DecisionRated(
        decision_id=decision_id,
        rating=DecisionRating.MISLEADING,
        comment=None,
        rated_by=ActorId(rater_b),
        rated_at=_T1,
        occurred_at=_T1,
        confidence_at_rating=None,
    )
    state = fold([e1, e2, e3])
    assert state is not None
    assert state.ratings[rater_a].rating is DecisionRating.USEFUL
    assert state.ratings[rater_b].rating is DecisionRating.MISLEADING


@pytest.mark.unit
def test_rated_event_preserves_other_aggregate_fields() -> None:
    """Folding a DecisionRated must not wipe parallel state (logbooks
    dict, decision facts)."""
    decision_id = uuid4()
    rater_id = uuid4()
    e1 = _genesis(decision_id=decision_id)
    e2 = DecisionRated(
        decision_id=decision_id,
        rating=DecisionRating.IGNORED,
        comment=None,
        rated_by=ActorId(rater_id),
        rated_at=_T1,
        occurred_at=_T1,
        confidence_at_rating=None,
    )
    state = fold([e1, e2])
    assert state is not None
    assert state.context.value == "RunDebrief"
    assert state.choice.value == "NominalCompletion"
    assert state.logbooks == {}


@pytest.mark.unit
def test_from_stored_unknown_rating_value_raises() -> None:
    stored = _stored(
        "DecisionRated",
        {
            "decision_id": str(uuid4()),
            "rating": "not-a-real-rating",
            "comment": None,
            "rated_by": str(uuid4()),
            "rated_at": _T0.isoformat(),
            "occurred_at": _T0.isoformat(),
            "confidence_at_rating": None,
        },
    )
    with pytest.raises(ValueError):
        from_stored(stored)


# ---------- Cross-arm preservation pins (gate-review test-coverage P1-1) ----------


@pytest.mark.unit
def test_logbook_opened_after_rated_preserves_ratings() -> None:
    """Folding a `DecisionLogbookOpened` on a Decision that already has
    ratings MUST NOT wipe `state.ratings`. The evolver passes
    `ratings=prior.ratings` explicitly at the LogbookOpened arm; this
    test pins that contract so a future refactor (for example a
    `dataclasses.replace`-style consolidation) cannot silently drop
    the field copy. Cross-arm symmetric to
    `test_rated_event_preserves_other_aggregate_fields`.
    """
    from cora.decision.aggregates.decision import (
        REASONING_LOGBOOK_SCHEMA,
        DecisionLogbookOpened,
    )

    decision_id = uuid4()
    rater_id = uuid4()
    logbook_id = uuid4()
    e_genesis = _genesis(decision_id=decision_id)
    e_rated = DecisionRated(
        decision_id=decision_id,
        rating=DecisionRating.USEFUL,
        comment="locked in before logbook opens",
        rated_by=ActorId(rater_id),
        rated_at=_T1,
        occurred_at=_T1,
        confidence_at_rating=None,
    )
    e_opened = DecisionLogbookOpened(
        decision_id=decision_id,
        logbook_id=logbook_id,
        kind="reasoning",
        schema=REASONING_LOGBOOK_SCHEMA,
        occurred_at=_T2,
    )

    state = fold([e_genesis, e_rated, e_opened])

    assert state is not None
    assert rater_id in state.ratings  # ratings survive the logbook-open fold
    assert state.ratings[rater_id].rating is DecisionRating.USEFUL
    assert state.logbooks == {"reasoning": logbook_id}


@pytest.mark.unit
def test_logbook_closed_after_rated_preserves_ratings() -> None:
    """Same invariant for the `DecisionLogbookClosed` arm: a rating
    that landed before a logbook closes MUST persist through the
    close fold."""
    from cora.decision.aggregates.decision import (
        REASONING_LOGBOOK_SCHEMA,
        DecisionLogbookClosed,
        DecisionLogbookOpened,
    )

    decision_id = uuid4()
    rater_id = uuid4()
    logbook_id = uuid4()
    e_genesis = _genesis(decision_id=decision_id)
    e_opened = DecisionLogbookOpened(
        decision_id=decision_id,
        logbook_id=logbook_id,
        kind="reasoning",
        schema=REASONING_LOGBOOK_SCHEMA,
        occurred_at=_T1,
    )
    e_rated = DecisionRated(
        decision_id=decision_id,
        rating=DecisionRating.MISLEADING,
        comment=None,
        rated_by=ActorId(rater_id),
        rated_at=_T2,
        occurred_at=_T2,
        confidence_at_rating=None,
    )
    e_closed = DecisionLogbookClosed(
        decision_id=decision_id,
        logbook_id=logbook_id,
        occurred_at=_T2,
    )

    state = fold([e_genesis, e_opened, e_rated, e_closed])

    assert state is not None
    assert rater_id in state.ratings  # ratings survive the logbook-close fold
    assert state.ratings[rater_id].rating is DecisionRating.MISLEADING
    assert state.logbooks == {}  # logbook removed on close
