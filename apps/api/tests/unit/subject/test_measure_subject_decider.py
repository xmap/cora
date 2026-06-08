"""Unit tests for the `measure_subject` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotMeasureError,
    SubjectMeasured,
    SubjectName,
    SubjectNotFoundError,
    SubjectStatus,
)
from cora.subject.features import measure_subject
from cora.subject.features.measure_subject import MeasureSubject

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_ACTOR = ActorId(uuid4())


def _subject(*, status: SubjectStatus = SubjectStatus.MOUNTED) -> Subject:
    return Subject(id=uuid4(), name=SubjectName("Sample-A1"), status=status)


@pytest.mark.unit
def test_decide_emits_subject_measured_when_state_is_mounted() -> None:
    state = _subject(status=SubjectStatus.MOUNTED)
    events = measure_subject.decide(
        state=state,
        command=MeasureSubject(subject_id=state.id),
        now=_NOW,
        measured_by=_ACTOR,
    )
    assert events == [SubjectMeasured(subject_id=state.id, occurred_at=_NOW, measured_by=_ACTOR)]


@pytest.mark.unit
def test_decide_raises_subject_not_found_when_state_is_none() -> None:
    """Update-style precondition: state must exist."""
    target_id = uuid4()
    with pytest.raises(SubjectNotFoundError) as exc_info:
        measure_subject.decide(
            state=None,
            command=MeasureSubject(subject_id=target_id),
            now=_NOW,
            measured_by=_ACTOR,
        )
    assert exc_info.value.subject_id == target_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "current",
    [
        SubjectStatus.RECEIVED,
        SubjectStatus.MEASURED,
        SubjectStatus.REMOVED,
        SubjectStatus.RETURNED,
        SubjectStatus.STORED,
        SubjectStatus.DISCARDED,
    ],
)
def test_decide_raises_cannot_measure_for_every_non_mounted_state(
    current: SubjectStatus,
) -> None:
    """Strict semantics, not idempotent: re-measuring an already-`Measured`
    subject also raises (rather than no-op or always-emit). Six wrong
    states tested explicitly so a future relaxation has to flip every
    parametrized case deliberately."""
    state = _subject(status=current)
    with pytest.raises(SubjectCannotMeasureError) as exc_info:
        measure_subject.decide(
            state=state,
            command=MeasureSubject(subject_id=state.id),
            now=_NOW,
            measured_by=_ACTOR,
        )
    assert exc_info.value.subject_id == state.id
    assert exc_info.value.current_status is current


@pytest.mark.unit
def test_decide_error_carries_current_status_for_diagnostic_messaging() -> None:
    """The error message includes both the current state and the
    expected source state — pinned because the route's 409 body
    surfaces this string."""
    state = _subject(status=SubjectStatus.RECEIVED)
    with pytest.raises(SubjectCannotMeasureError) as exc_info:
        measure_subject.decide(
            state=state,
            command=MeasureSubject(subject_id=state.id),
            now=_NOW,
            measured_by=_ACTOR,
        )
    msg = str(exc_info.value)
    assert "Received" in msg
    assert "Mounted" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _subject(status=SubjectStatus.MOUNTED)
    command = MeasureSubject(subject_id=state.id)
    first = measure_subject.decide(state=state, command=command, now=_NOW, measured_by=_ACTOR)
    second = measure_subject.decide(state=state, command=command, now=_NOW, measured_by=_ACTOR)
    assert first == second
