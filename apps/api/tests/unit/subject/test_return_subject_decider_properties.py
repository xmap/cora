"""Property-based tests for `return_subject.decide` (Subject BC).

Complements the example-based `test_return_subject_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition with actor attribution

    (state, command, now, returned_by) -> list[SubjectReturned]

Load-bearing properties:

  - state=None always raises `SubjectNotFoundError` carrying
    command.subject_id.
  - The source-state partition is total over `SubjectStatus`: only
    `Removed` emits exactly one `SubjectReturned` (subject_id=state.id,
    occurred_at=now, returned_by threaded); every other status raises
    `SubjectCannotReturnError` carrying the current status.
  - The emitted event's subject_id is `state.id`, never
    command.subject_id.
  - Pure: same (state, command, now, returned_by) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

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
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_RETURNABLE_SOURCES = (SubjectStatus.REMOVED,)
_DISALLOWED_SOURCES = tuple(s for s in SubjectStatus if s not in frozenset(_RETURNABLE_SOURCES))


def _subject(*, subject_id: UUID, status: SubjectStatus) -> Subject:
    return Subject(id=subject_id, name=SubjectName("PorousCeramicSample-A"), status=status)


@pytest.mark.unit
@given(subject_id=st.uuids(), now=aware_datetimes(), returned_by_uuid=st.uuids())
def test_return_with_none_state_always_raises_not_found(
    subject_id: UUID,
    now: datetime,
    returned_by_uuid: UUID,
) -> None:
    """Empty stream always raises `SubjectNotFoundError` carrying command.subject_id."""
    with pytest.raises(SubjectNotFoundError) as exc:
        return_subject.decide(
            state=None,
            command=ReturnSubject(subject_id=subject_id),
            now=now,
            returned_by=ActorId(returned_by_uuid),
        )
    assert exc.value.subject_id == subject_id


@pytest.mark.unit
@given(subject_id=st.uuids(), now=aware_datetimes(), returned_by_uuid=st.uuids())
def test_return_from_removed_emits_single_event(
    subject_id: UUID,
    now: datetime,
    returned_by_uuid: UUID,
) -> None:
    """Removed is the only returnable source; emits one SubjectReturned."""
    returned_by = ActorId(returned_by_uuid)
    events = return_subject.decide(
        state=_subject(subject_id=subject_id, status=SubjectStatus.REMOVED),
        command=ReturnSubject(subject_id=subject_id),
        now=now,
        returned_by=returned_by,
    )
    assert events == [
        SubjectReturned(subject_id=subject_id, occurred_at=now, returned_by=returned_by)
    ]


@pytest.mark.unit
@given(
    subject_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
    returned_by_uuid=st.uuids(),
)
def test_return_from_disallowed_source_always_raises_cannot_return(
    subject_id: UUID,
    source: SubjectStatus,
    now: datetime,
    returned_by_uuid: UUID,
) -> None:
    """Any source other than Removed raises, carrying the current status."""
    with pytest.raises(SubjectCannotReturnError) as exc:
        return_subject.decide(
            state=_subject(subject_id=subject_id, status=source),
            command=ReturnSubject(subject_id=subject_id),
            now=now,
            returned_by=ActorId(returned_by_uuid),
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_subject_id=st.uuids(),
    command_subject_id=st.uuids(),
    now=aware_datetimes(),
    returned_by_uuid=st.uuids(),
)
def test_return_uses_state_id_not_command_subject_id(
    state_subject_id: UUID,
    command_subject_id: UUID,
    now: datetime,
    returned_by_uuid: UUID,
) -> None:
    """The emitted event's subject_id is state.id, not command.subject_id."""
    assume(state_subject_id != command_subject_id)
    events = return_subject.decide(
        state=_subject(subject_id=state_subject_id, status=SubjectStatus.REMOVED),
        command=ReturnSubject(subject_id=command_subject_id),
        now=now,
        returned_by=ActorId(returned_by_uuid),
    )
    assert events[0].subject_id == state_subject_id


@pytest.mark.unit
@given(subject_id=st.uuids(), now=aware_datetimes(), returned_by_uuid=st.uuids())
def test_return_is_pure_same_input_same_output(
    subject_id: UUID,
    now: datetime,
    returned_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _subject(subject_id=subject_id, status=SubjectStatus.REMOVED)
    command = ReturnSubject(subject_id=subject_id)
    returned_by = ActorId(returned_by_uuid)
    first = return_subject.decide(state=state, command=command, now=now, returned_by=returned_by)
    second = return_subject.decide(state=state, command=command, now=now, returned_by=returned_by)
    assert first == second
