"""Property-based tests for `store_subject.decide` (Subject BC).

Complements the example-based `test_store_subject_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition with actor attribution

    (state, command, now, stored_by) -> list[SubjectStored]

Load-bearing properties:

  - state=None always raises `SubjectNotFoundError` carrying
    command.subject_id.
  - The source-state partition is total over `SubjectStatus`: only
    `Removed` emits exactly one `SubjectStored` (subject_id=state.id,
    occurred_at=now, stored_by threaded); every other status raises
    `SubjectCannotStoreError` carrying the current status.
  - The emitted event's subject_id is `state.id`, never
    command.subject_id.
  - Pure: same (state, command, now, stored_by) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

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
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_STORABLE_SOURCES = (SubjectStatus.REMOVED,)
_DISALLOWED_SOURCES = tuple(s for s in SubjectStatus if s not in frozenset(_STORABLE_SOURCES))


def _subject(*, subject_id: UUID, status: SubjectStatus) -> Subject:
    return Subject(id=subject_id, name=SubjectName("PorousCeramicSample-A"), status=status)


@pytest.mark.unit
@given(subject_id=st.uuids(), now=aware_datetimes(), stored_by_uuid=st.uuids())
def test_store_with_none_state_always_raises_not_found(
    subject_id: UUID,
    now: datetime,
    stored_by_uuid: UUID,
) -> None:
    """Empty stream always raises `SubjectNotFoundError` carrying command.subject_id."""
    with pytest.raises(SubjectNotFoundError) as exc:
        store_subject.decide(
            state=None,
            command=StoreSubject(subject_id=subject_id),
            now=now,
            stored_by=ActorId(stored_by_uuid),
        )
    assert exc.value.subject_id == subject_id


@pytest.mark.unit
@given(subject_id=st.uuids(), now=aware_datetimes(), stored_by_uuid=st.uuids())
def test_store_from_removed_emits_single_event(
    subject_id: UUID,
    now: datetime,
    stored_by_uuid: UUID,
) -> None:
    """Removed is the only storable source; emits one SubjectStored."""
    stored_by = ActorId(stored_by_uuid)
    events = store_subject.decide(
        state=_subject(subject_id=subject_id, status=SubjectStatus.REMOVED),
        command=StoreSubject(subject_id=subject_id),
        now=now,
        stored_by=stored_by,
    )
    assert events == [SubjectStored(subject_id=subject_id, occurred_at=now, stored_by=stored_by)]


@pytest.mark.unit
@given(
    subject_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
    stored_by_uuid=st.uuids(),
)
def test_store_from_disallowed_source_always_raises_cannot_store(
    subject_id: UUID,
    source: SubjectStatus,
    now: datetime,
    stored_by_uuid: UUID,
) -> None:
    """Any source other than Removed raises, carrying the current status."""
    with pytest.raises(SubjectCannotStoreError) as exc:
        store_subject.decide(
            state=_subject(subject_id=subject_id, status=source),
            command=StoreSubject(subject_id=subject_id),
            now=now,
            stored_by=ActorId(stored_by_uuid),
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_subject_id=st.uuids(),
    command_subject_id=st.uuids(),
    now=aware_datetimes(),
    stored_by_uuid=st.uuids(),
)
def test_store_uses_state_id_not_command_subject_id(
    state_subject_id: UUID,
    command_subject_id: UUID,
    now: datetime,
    stored_by_uuid: UUID,
) -> None:
    """The emitted event's subject_id is state.id, not command.subject_id."""
    assume(state_subject_id != command_subject_id)
    events = store_subject.decide(
        state=_subject(subject_id=state_subject_id, status=SubjectStatus.REMOVED),
        command=StoreSubject(subject_id=command_subject_id),
        now=now,
        stored_by=ActorId(stored_by_uuid),
    )
    assert events[0].subject_id == state_subject_id


@pytest.mark.unit
@given(subject_id=st.uuids(), now=aware_datetimes(), stored_by_uuid=st.uuids())
def test_store_is_pure_same_input_same_output(
    subject_id: UUID,
    now: datetime,
    stored_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _subject(subject_id=subject_id, status=SubjectStatus.REMOVED)
    command = StoreSubject(subject_id=subject_id)
    stored_by = ActorId(stored_by_uuid)
    first = store_subject.decide(state=state, command=command, now=now, stored_by=stored_by)
    second = store_subject.decide(state=state, command=command, now=now, stored_by=stored_by)
    assert first == second
