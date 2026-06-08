"""Unit tests for the `discard_subject` slice's pure decider.

Terminal disposition: `Removed -> Discarded`. Single-source guard.
Mirrors `return_subject` / `store_subject` decider tests.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import (
    InvalidSubjectDiscardReasonError,
    Subject,
    SubjectCannotDiscardError,
    SubjectDiscarded,
    SubjectName,
    SubjectNotFoundError,
    SubjectStatus,
)
from cora.subject.features import discard_subject
from cora.subject.features.discard_subject import DiscardSubject

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_ACTOR = ActorId(uuid4())


def _subject(*, status: SubjectStatus = SubjectStatus.REMOVED) -> Subject:
    return Subject(id=uuid4(), name=SubjectName("Sample-A1"), status=status)


@pytest.mark.unit
def test_decide_emits_subject_discarded_when_state_is_removed() -> None:
    state = _subject(status=SubjectStatus.REMOVED)
    events = discard_subject.decide(
        state=state,
        command=DiscardSubject(subject_id=state.id, reason="contaminated; biohazard incinerator"),
        now=_NOW,
        discarded_by=_ACTOR,
    )
    assert events == [
        SubjectDiscarded(
            subject_id=state.id,
            reason="contaminated; biohazard incinerator",
            occurred_at=_NOW,
            discarded_by=_ACTOR,
        )
    ]


@pytest.mark.unit
def test_decide_raises_subject_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(SubjectNotFoundError) as exc_info:
        discard_subject.decide(
            state=None,
            command=DiscardSubject(subject_id=target_id, reason="contaminated; incinerator"),
            now=_NOW,
            discarded_by=_ACTOR,
        )
    assert exc_info.value.subject_id == target_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "current",
    [
        SubjectStatus.RECEIVED,
        SubjectStatus.MOUNTED,
        SubjectStatus.MEASURED,
        SubjectStatus.RETURNED,
        SubjectStatus.STORED,
        SubjectStatus.DISCARDED,
    ],
)
def test_decide_raises_cannot_discard_for_every_non_removed_state(
    current: SubjectStatus,
) -> None:
    """Strict semantics, not idempotent: re-discarding an already-
    `Discarded` subject also raises. All six wrong states tested
    explicitly."""
    state = _subject(status=current)
    with pytest.raises(SubjectCannotDiscardError) as exc_info:
        discard_subject.decide(
            state=state,
            command=DiscardSubject(
                subject_id=state.id, reason="contaminated; biohazard incinerator"
            ),
            now=_NOW,
            discarded_by=_ACTOR,
        )
    assert exc_info.value.subject_id == state.id
    assert exc_info.value.current_status is current


@pytest.mark.unit
def test_decide_error_carries_current_status_for_diagnostic_messaging() -> None:
    state = _subject(status=SubjectStatus.RECEIVED)
    with pytest.raises(SubjectCannotDiscardError) as exc_info:
        discard_subject.decide(
            state=state,
            command=DiscardSubject(
                subject_id=state.id, reason="contaminated; biohazard incinerator"
            ),
            now=_NOW,
            discarded_by=_ACTOR,
        )
    msg = str(exc_info.value)
    assert "Received" in msg
    assert "Removed" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _subject(status=SubjectStatus.REMOVED)
    command = DiscardSubject(subject_id=state.id, reason="contaminated; biohazard incinerator")
    first = discard_subject.decide(state=state, command=command, now=_NOW, discarded_by=_ACTOR)
    second = discard_subject.decide(state=state, command=command, now=_NOW, discarded_by=_ACTOR)
    assert first == second


@pytest.mark.unit
@pytest.mark.parametrize("bad_reason", ["", " ", "\t\n  ", "x" * 501])
def test_decide_raises_invalid_reason_for_empty_or_overlong(bad_reason: str) -> None:
    state = _subject(status=SubjectStatus.REMOVED)
    with pytest.raises(InvalidSubjectDiscardReasonError):
        discard_subject.decide(
            state=state,
            command=DiscardSubject(subject_id=state.id, reason=bad_reason),
            now=_NOW,
            discarded_by=_ACTOR,
        )


@pytest.mark.unit
def test_decide_persists_trimmed_reason_in_event() -> None:
    state = _subject(status=SubjectStatus.REMOVED)
    events = discard_subject.decide(
        state=state,
        command=DiscardSubject(subject_id=state.id, reason="  whitespace edges  "),
        now=_NOW,
        discarded_by=_ACTOR,
    )
    assert events == [
        SubjectDiscarded(
            subject_id=state.id,
            reason="whitespace edges",
            occurred_at=_NOW,
            discarded_by=_ACTOR,
        )
    ]
