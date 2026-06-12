"""Property-based tests for `measure_subject.decide` (Subject BC).

Complements the example-based `test_measure_subject_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition with actor attribution

    (state, command, now, measured_by) -> list[SubjectMeasured]

Load-bearing properties:

  - state=None always raises `SubjectNotFoundError` carrying
    command.subject_id.
  - The source-state partition is total over `SubjectStatus`: only
    `Mounted` emits exactly one `SubjectMeasured` (subject_id=state.id,
    occurred_at=now, measured_by threaded); every other status raises
    `SubjectCannotMeasureError` carrying the current status.
  - The emitted event's subject_id is `state.id`, never
    command.subject_id.
  - Pure: same (state, command, now, measured_by) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

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
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_MEASURABLE_SOURCES = (SubjectStatus.MOUNTED,)
_DISALLOWED_SOURCES = tuple(s for s in SubjectStatus if s not in frozenset(_MEASURABLE_SOURCES))


def _subject(*, subject_id: UUID, status: SubjectStatus) -> Subject:
    return Subject(id=subject_id, name=SubjectName("PorousCeramicSample-A"), status=status)


@pytest.mark.unit
@given(subject_id=st.uuids(), now=aware_datetimes(), measured_by_uuid=st.uuids())
def test_measure_with_none_state_always_raises_not_found(
    subject_id: UUID,
    now: datetime,
    measured_by_uuid: UUID,
) -> None:
    """Empty stream always raises `SubjectNotFoundError` carrying command.subject_id."""
    with pytest.raises(SubjectNotFoundError) as exc:
        measure_subject.decide(
            state=None,
            command=MeasureSubject(subject_id=subject_id),
            now=now,
            measured_by=ActorId(measured_by_uuid),
        )
    assert exc.value.subject_id == subject_id


@pytest.mark.unit
@given(subject_id=st.uuids(), now=aware_datetimes(), measured_by_uuid=st.uuids())
def test_measure_from_mounted_emits_single_event(
    subject_id: UUID,
    now: datetime,
    measured_by_uuid: UUID,
) -> None:
    """Mounted is the only measurable source; emits one SubjectMeasured."""
    measured_by = ActorId(measured_by_uuid)
    events = measure_subject.decide(
        state=_subject(subject_id=subject_id, status=SubjectStatus.MOUNTED),
        command=MeasureSubject(subject_id=subject_id),
        now=now,
        measured_by=measured_by,
    )
    assert events == [
        SubjectMeasured(subject_id=subject_id, occurred_at=now, measured_by=measured_by)
    ]


@pytest.mark.unit
@given(
    subject_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
    measured_by_uuid=st.uuids(),
)
def test_measure_from_disallowed_source_always_raises_cannot_measure(
    subject_id: UUID,
    source: SubjectStatus,
    now: datetime,
    measured_by_uuid: UUID,
) -> None:
    """Any source other than Mounted raises, carrying the current status."""
    with pytest.raises(SubjectCannotMeasureError) as exc:
        measure_subject.decide(
            state=_subject(subject_id=subject_id, status=source),
            command=MeasureSubject(subject_id=subject_id),
            now=now,
            measured_by=ActorId(measured_by_uuid),
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_subject_id=st.uuids(),
    command_subject_id=st.uuids(),
    now=aware_datetimes(),
    measured_by_uuid=st.uuids(),
)
def test_measure_uses_state_id_not_command_subject_id(
    state_subject_id: UUID,
    command_subject_id: UUID,
    now: datetime,
    measured_by_uuid: UUID,
) -> None:
    """The emitted event's subject_id is state.id, not command.subject_id."""
    assume(state_subject_id != command_subject_id)
    events = measure_subject.decide(
        state=_subject(subject_id=state_subject_id, status=SubjectStatus.MOUNTED),
        command=MeasureSubject(subject_id=command_subject_id),
        now=now,
        measured_by=ActorId(measured_by_uuid),
    )
    assert events[0].subject_id == state_subject_id


@pytest.mark.unit
@given(subject_id=st.uuids(), now=aware_datetimes(), measured_by_uuid=st.uuids())
def test_measure_is_pure_same_input_same_output(
    subject_id: UUID,
    now: datetime,
    measured_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _subject(subject_id=subject_id, status=SubjectStatus.MOUNTED)
    command = MeasureSubject(subject_id=subject_id)
    measured_by = ActorId(measured_by_uuid)
    first = measure_subject.decide(state=state, command=command, now=now, measured_by=measured_by)
    second = measure_subject.decide(state=state, command=command, now=now, measured_by=measured_by)
    assert first == second
