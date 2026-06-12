"""Property-based tests for `remove_subject.decide` (Subject BC).

Complements the example-based `test_remove_subject_decider.py` with
universal claims across generated inputs. The decider is a pure
multi-source FSM transition with actor attribution

    (state, command, now, removed_by) -> list[SubjectRemoved]

Load-bearing properties:

  - state=None always raises `SubjectNotFoundError` carrying
    command.subject_id.
  - The source-state partition is total over `SubjectStatus`: only
    `Received`, `Mounted`, and `Measured` emit exactly one
    `SubjectRemoved` (subject_id=state.id, occurred_at=now, removed_by
    threaded); every other status raises `SubjectCannotRemoveError`
    carrying the current status.
  - The emitted event's subject_id is `state.id`, never
    command.subject_id.
  - Pure: same (state, command, now, removed_by) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

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
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_REMOVABLE_SOURCES = (
    SubjectStatus.RECEIVED,
    SubjectStatus.MOUNTED,
    SubjectStatus.MEASURED,
)
_DISALLOWED_SOURCES = tuple(s for s in SubjectStatus if s not in frozenset(_REMOVABLE_SOURCES))


def _subject(*, subject_id: UUID, status: SubjectStatus) -> Subject:
    return Subject(id=subject_id, name=SubjectName("PorousCeramicSample-A"), status=status)


@pytest.mark.unit
@given(subject_id=st.uuids(), now=aware_datetimes(), removed_by_uuid=st.uuids())
def test_remove_with_none_state_always_raises_not_found(
    subject_id: UUID,
    now: datetime,
    removed_by_uuid: UUID,
) -> None:
    """Empty stream always raises `SubjectNotFoundError` carrying command.subject_id."""
    with pytest.raises(SubjectNotFoundError) as exc:
        remove_subject.decide(
            state=None,
            command=RemoveSubject(subject_id=subject_id),
            now=now,
            removed_by=ActorId(removed_by_uuid),
        )
    assert exc.value.subject_id == subject_id


@pytest.mark.unit
@given(
    subject_id=st.uuids(),
    source=st.sampled_from(_REMOVABLE_SOURCES),
    now=aware_datetimes(),
    removed_by_uuid=st.uuids(),
)
def test_remove_from_removable_source_emits_single_event(
    subject_id: UUID,
    source: SubjectStatus,
    now: datetime,
    removed_by_uuid: UUID,
) -> None:
    """Received, Mounted, and Measured each emit one SubjectRemoved."""
    removed_by = ActorId(removed_by_uuid)
    events = remove_subject.decide(
        state=_subject(subject_id=subject_id, status=source),
        command=RemoveSubject(subject_id=subject_id),
        now=now,
        removed_by=removed_by,
    )
    assert events == [SubjectRemoved(subject_id=subject_id, occurred_at=now, removed_by=removed_by)]


@pytest.mark.unit
@given(
    subject_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
    removed_by_uuid=st.uuids(),
)
def test_remove_from_disallowed_source_always_raises_cannot_remove(
    subject_id: UUID,
    source: SubjectStatus,
    now: datetime,
    removed_by_uuid: UUID,
) -> None:
    """Any source outside {Received, Mounted, Measured} raises, carrying the current status."""
    with pytest.raises(SubjectCannotRemoveError) as exc:
        remove_subject.decide(
            state=_subject(subject_id=subject_id, status=source),
            command=RemoveSubject(subject_id=subject_id),
            now=now,
            removed_by=ActorId(removed_by_uuid),
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_subject_id=st.uuids(),
    command_subject_id=st.uuids(),
    source=st.sampled_from(_REMOVABLE_SOURCES),
    now=aware_datetimes(),
    removed_by_uuid=st.uuids(),
)
def test_remove_uses_state_id_not_command_subject_id(
    state_subject_id: UUID,
    command_subject_id: UUID,
    source: SubjectStatus,
    now: datetime,
    removed_by_uuid: UUID,
) -> None:
    """The emitted event's subject_id is state.id, not command.subject_id."""
    assume(state_subject_id != command_subject_id)
    events = remove_subject.decide(
        state=_subject(subject_id=state_subject_id, status=source),
        command=RemoveSubject(subject_id=command_subject_id),
        now=now,
        removed_by=ActorId(removed_by_uuid),
    )
    assert events[0].subject_id == state_subject_id


@pytest.mark.unit
@given(
    subject_id=st.uuids(),
    source=st.sampled_from(_REMOVABLE_SOURCES),
    now=aware_datetimes(),
    removed_by_uuid=st.uuids(),
)
def test_remove_is_pure_same_input_same_output(
    subject_id: UUID,
    source: SubjectStatus,
    now: datetime,
    removed_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _subject(subject_id=subject_id, status=source)
    command = RemoveSubject(subject_id=subject_id)
    removed_by = ActorId(removed_by_uuid)
    first = remove_subject.decide(state=state, command=command, now=now, removed_by=removed_by)
    second = remove_subject.decide(state=state, command=command, now=now, removed_by=removed_by)
    assert first == second
