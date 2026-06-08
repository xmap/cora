"""Unit tests for the `store_subject` slice's pure decider.

Terminal disposition: `Removed -> Stored`. Single-source guard.
Mirrors `return_subject` / `discard_subject` decider tests.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotStoreError,
    SubjectName,
    SubjectNotFoundError,
    SubjectStatus,
    SubjectStored,
)
from cora.subject.features import store_subject
from cora.subject.features.store_subject import StoreSubject

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_ACTOR = ActorId(uuid4())


def _subject(*, status: SubjectStatus = SubjectStatus.REMOVED) -> Subject:
    return Subject(id=uuid4(), name=SubjectName("Sample-A1"), status=status)


@pytest.mark.unit
def test_decide_emits_subject_stored_when_state_is_removed() -> None:
    state = _subject(status=SubjectStatus.REMOVED)
    events = store_subject.decide(
        state=state,
        command=StoreSubject(subject_id=state.id),
        now=_NOW,
        stored_by=_ACTOR,
    )
    assert events == [SubjectStored(subject_id=state.id, occurred_at=_NOW, stored_by=_ACTOR)]


@pytest.mark.unit
def test_decide_raises_subject_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(SubjectNotFoundError) as exc_info:
        store_subject.decide(
            state=None,
            command=StoreSubject(subject_id=target_id),
            now=_NOW,
            stored_by=_ACTOR,
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
def test_decide_raises_cannot_store_for_every_non_removed_state(
    current: SubjectStatus,
) -> None:
    """Strict semantics, not idempotent: re-storing an already-`Stored`
    subject also raises. All six wrong states tested explicitly."""
    state = _subject(status=current)
    with pytest.raises(SubjectCannotStoreError) as exc_info:
        store_subject.decide(
            state=state,
            command=StoreSubject(subject_id=state.id),
            now=_NOW,
            stored_by=_ACTOR,
        )
    assert exc_info.value.subject_id == state.id
    assert exc_info.value.current_status is current


@pytest.mark.unit
def test_decide_error_carries_current_status_for_diagnostic_messaging() -> None:
    state = _subject(status=SubjectStatus.MEASURED)
    with pytest.raises(SubjectCannotStoreError) as exc_info:
        store_subject.decide(
            state=state,
            command=StoreSubject(subject_id=state.id),
            now=_NOW,
            stored_by=_ACTOR,
        )
    msg = str(exc_info.value)
    assert "Measured" in msg
    assert "Removed" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _subject(status=SubjectStatus.REMOVED)
    command = StoreSubject(subject_id=state.id)
    first = store_subject.decide(state=state, command=command, now=_NOW, stored_by=_ACTOR)
    second = store_subject.decide(state=state, command=command, now=_NOW, stored_by=_ACTOR)
    assert first == second
