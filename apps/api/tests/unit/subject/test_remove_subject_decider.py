"""Unit tests for the `remove_subject` slice's pure decider.

First multi-source-state guard in the codebase:
`Mounted | Measured -> Removed`. Tests parametrize across both source
states so a future change that only handles one is caught.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotRemoveError,
    SubjectName,
    SubjectNotFoundError,
    SubjectRemoved,
    SubjectStatus,
)
from cora.subject.features import remove_subject
from cora.subject.features.remove_subject import RemoveSubject

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_ACTOR = ActorId(uuid4())


def _subject(*, status: SubjectStatus = SubjectStatus.MOUNTED) -> Subject:
    return Subject(id=uuid4(), name=SubjectName("Sample-A1"), status=status)


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [
        SubjectStatus.MOUNTED,
        SubjectStatus.MEASURED,
    ],
)
def test_decide_emits_subject_removed_for_each_allowed_source_state(
    source: SubjectStatus,
) -> None:
    """Both Mounted and Measured are valid sources; the emitted event
    is identical regardless of which one preceded — no `from_status`
    on the event payload."""
    state = _subject(status=source)
    events = remove_subject.decide(
        state=state,
        command=RemoveSubject(subject_id=state.id),
        now=_NOW,
        removed_by=_ACTOR,
    )
    assert events == [SubjectRemoved(subject_id=state.id, occurred_at=_NOW, removed_by=_ACTOR)]


@pytest.mark.unit
def test_decide_raises_subject_not_found_when_state_is_none() -> None:
    """Update-style precondition: state must exist."""
    target_id = uuid4()
    with pytest.raises(SubjectNotFoundError) as exc_info:
        remove_subject.decide(
            state=None,
            command=RemoveSubject(subject_id=target_id),
            now=_NOW,
            removed_by=_ACTOR,
        )
    assert exc_info.value.subject_id == target_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "current",
    [
        SubjectStatus.REMOVED,
        SubjectStatus.RETURNED,
        SubjectStatus.STORED,
        SubjectStatus.DISCARDED,
    ],
)
def test_decide_raises_cannot_remove_for_every_disallowed_source_state(
    current: SubjectStatus,
) -> None:
    """Strict semantics, not idempotent: re-removing an already-`Removed`
    subject also raises. The terminal-leading and terminal states are
    tested explicitly so a future relaxation has to flip every
    parametrized case deliberately. The three ALLOWED states
    (Received, Mounted, Measured -- 4f widening) are covered
    separately."""
    state = _subject(status=current)
    with pytest.raises(SubjectCannotRemoveError) as exc_info:
        remove_subject.decide(
            state=state,
            command=RemoveSubject(subject_id=state.id),
            now=_NOW,
            removed_by=_ACTOR,
        )
    assert exc_info.value.subject_id == state.id
    assert exc_info.value.current_status is current


@pytest.mark.unit
def test_decide_error_message_lists_all_allowed_source_states() -> None:
    """Pinned because the route's 409 body surfaces this string and the
    operator needs to see ALL allowed source states (not just one) to
    diagnose 'why can't I remove this'. 4f widened the set to include
    Received."""
    state = _subject(status=SubjectStatus.REMOVED)
    with pytest.raises(SubjectCannotRemoveError) as exc_info:
        remove_subject.decide(
            state=state,
            command=RemoveSubject(subject_id=state.id),
            now=_NOW,
            removed_by=_ACTOR,
        )
    msg = str(exc_info.value)
    assert "Received" in msg
    assert "Mounted" in msg
    assert "Measured" in msg


@pytest.mark.unit
def test_decide_allows_removal_from_received_state() -> None:
    """4f widening: a Subject that was registered but never mounted
    (or was mounted then dismounted, returning to Received) can be
    removed directly without going through Mounted first."""
    state = _subject(status=SubjectStatus.RECEIVED)
    events = remove_subject.decide(
        state=state,
        command=RemoveSubject(subject_id=state.id),
        now=_NOW,
        removed_by=_ACTOR,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _subject(status=SubjectStatus.MEASURED)
    command = RemoveSubject(subject_id=state.id)
    first = remove_subject.decide(state=state, command=command, now=_NOW, removed_by=_ACTOR)
    second = remove_subject.decide(state=state, command=command, now=_NOW, removed_by=_ACTOR)
    assert first == second
