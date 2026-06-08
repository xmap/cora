"""Unit tests for the `return_subject` slice's pure decider.

Terminal disposition: `Removed -> Returned`. Single-source guard
(only `Removed` is a valid prior state).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotReturnError,
    SubjectName,
    SubjectNotFoundError,
    SubjectReturned,
    SubjectStatus,
)
from cora.subject.features import return_subject
from cora.subject.features.return_subject import ReturnSubject

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_ACTOR = ActorId(uuid4())


def _subject(*, status: SubjectStatus = SubjectStatus.REMOVED) -> Subject:
    return Subject(id=uuid4(), name=SubjectName("Sample-A1"), status=status)


@pytest.mark.unit
def test_decide_emits_subject_returned_when_state_is_removed() -> None:
    state = _subject(status=SubjectStatus.REMOVED)
    events = return_subject.decide(
        state=state,
        command=ReturnSubject(subject_id=state.id),
        now=_NOW,
        returned_by=_ACTOR,
    )
    assert events == [SubjectReturned(subject_id=state.id, occurred_at=_NOW, returned_by=_ACTOR)]


@pytest.mark.unit
def test_decide_raises_subject_not_found_when_state_is_none() -> None:
    """Update-style precondition: state must exist."""
    target_id = uuid4()
    with pytest.raises(SubjectNotFoundError) as exc_info:
        return_subject.decide(
            state=None,
            command=ReturnSubject(subject_id=target_id),
            now=_NOW,
            returned_by=_ACTOR,
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
def test_decide_raises_cannot_return_for_every_non_removed_state(
    current: SubjectStatus,
) -> None:
    """Strict semantics, not idempotent: re-returning an already-`Returned`
    subject also raises. All six wrong states tested explicitly so a
    future relaxation has to flip every parametrized case deliberately.
    The other two terminal states (Stored, Discarded) are also
    disallowed sources — pinned because they're the closest "looks
    similar" cases that an implementer might be tempted to allow."""
    state = _subject(status=current)
    with pytest.raises(SubjectCannotReturnError) as exc_info:
        return_subject.decide(
            state=state,
            command=ReturnSubject(subject_id=state.id),
            now=_NOW,
            returned_by=_ACTOR,
        )
    assert exc_info.value.subject_id == state.id
    assert exc_info.value.current_status is current


@pytest.mark.unit
def test_decide_error_carries_current_status_for_diagnostic_messaging() -> None:
    """The error message includes both the current state and the
    expected source state — pinned because the route's 409 body
    surfaces this string."""
    state = _subject(status=SubjectStatus.MOUNTED)
    with pytest.raises(SubjectCannotReturnError) as exc_info:
        return_subject.decide(
            state=state,
            command=ReturnSubject(subject_id=state.id),
            now=_NOW,
            returned_by=_ACTOR,
        )
    msg = str(exc_info.value)
    assert "Mounted" in msg
    assert "Removed" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _subject(status=SubjectStatus.REMOVED)
    command = ReturnSubject(subject_id=state.id)
    first = return_subject.decide(state=state, command=command, now=_NOW, returned_by=_ACTOR)
    second = return_subject.decide(state=state, command=command, now=_NOW, returned_by=_ACTOR)
    assert first == second
