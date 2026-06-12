"""Property-based tests for `discard_subject.decide` (Subject BC).

Complements the example-based `test_discard_subject_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source terminal disposition with a reason and actor attribution

    (state, command, now, discarded_by) -> list[SubjectDiscarded]

Load-bearing properties:

  - state=None always raises `SubjectNotFoundError` carrying
    command.subject_id.
  - The source-state partition is total over `SubjectStatus`: only
    `Removed` emits exactly one `SubjectDiscarded` (subject_id=state.id,
    reason threaded, occurred_at=now, discarded_by threaded); every
    other status raises `SubjectCannotDiscardError` carrying the
    current status.
  - The emitted event's subject_id is `state.id`, never
    command.subject_id.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotDiscardError,
    SubjectDiscarded,
    SubjectName,
    SubjectNotFoundError,
    SubjectStatus,
)
from cora.subject.features import discard_subject
from cora.subject.features.discard_subject import DiscardSubject
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_REASON = printable_ascii_text(min_size=1, max_size=500)
_DISCARDABLE_SOURCES = (SubjectStatus.REMOVED,)
_DISALLOWED_SOURCES = tuple(s for s in SubjectStatus if s not in frozenset(_DISCARDABLE_SOURCES))


def _subject(*, subject_id: UUID, status: SubjectStatus) -> Subject:
    return Subject(id=subject_id, name=SubjectName("PorousCeramicSample-A"), status=status)


@pytest.mark.unit
@given(subject_id=st.uuids(), reason=_REASON, now=aware_datetimes(), discarded_by_uuid=st.uuids())
def test_discard_with_none_state_always_raises_not_found(
    subject_id: UUID,
    reason: str,
    now: datetime,
    discarded_by_uuid: UUID,
) -> None:
    """Empty stream always raises `SubjectNotFoundError` carrying command.subject_id."""
    with pytest.raises(SubjectNotFoundError) as exc:
        discard_subject.decide(
            state=None,
            command=DiscardSubject(subject_id=subject_id, reason=reason),
            now=now,
            discarded_by=ActorId(discarded_by_uuid),
        )
    assert exc.value.subject_id == subject_id


@pytest.mark.unit
@given(subject_id=st.uuids(), reason=_REASON, now=aware_datetimes(), discarded_by_uuid=st.uuids())
def test_discard_from_removed_emits_single_event(
    subject_id: UUID,
    reason: str,
    now: datetime,
    discarded_by_uuid: UUID,
) -> None:
    """Removed is the only discardable source; emits one SubjectDiscarded."""
    discarded_by = ActorId(discarded_by_uuid)
    events = discard_subject.decide(
        state=_subject(subject_id=subject_id, status=SubjectStatus.REMOVED),
        command=DiscardSubject(subject_id=subject_id, reason=reason),
        now=now,
        discarded_by=discarded_by,
    )
    assert events == [
        SubjectDiscarded(
            subject_id=subject_id, reason=reason, occurred_at=now, discarded_by=discarded_by
        )
    ]


@pytest.mark.unit
@given(
    subject_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
    discarded_by_uuid=st.uuids(),
)
def test_discard_from_disallowed_source_always_raises_cannot_discard(
    subject_id: UUID,
    source: SubjectStatus,
    reason: str,
    now: datetime,
    discarded_by_uuid: UUID,
) -> None:
    """Any source other than Removed raises, carrying the current status.

    A valid reason is supplied so the source-state guard is what fires
    (reason validation runs first in the decider).
    """
    with pytest.raises(SubjectCannotDiscardError) as exc:
        discard_subject.decide(
            state=_subject(subject_id=subject_id, status=source),
            command=DiscardSubject(subject_id=subject_id, reason=reason),
            now=now,
            discarded_by=ActorId(discarded_by_uuid),
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_subject_id=st.uuids(),
    command_subject_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    discarded_by_uuid=st.uuids(),
)
def test_discard_uses_state_id_not_command_subject_id(
    state_subject_id: UUID,
    command_subject_id: UUID,
    reason: str,
    now: datetime,
    discarded_by_uuid: UUID,
) -> None:
    """The emitted event's subject_id is state.id, not command.subject_id."""
    assume(state_subject_id != command_subject_id)
    events = discard_subject.decide(
        state=_subject(subject_id=state_subject_id, status=SubjectStatus.REMOVED),
        command=DiscardSubject(subject_id=command_subject_id, reason=reason),
        now=now,
        discarded_by=ActorId(discarded_by_uuid),
    )
    assert events[0].subject_id == state_subject_id


@pytest.mark.unit
@given(subject_id=st.uuids(), reason=_REASON, now=aware_datetimes(), discarded_by_uuid=st.uuids())
def test_discard_is_pure_same_input_same_output(
    subject_id: UUID,
    reason: str,
    now: datetime,
    discarded_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _subject(subject_id=subject_id, status=SubjectStatus.REMOVED)
    command = DiscardSubject(subject_id=subject_id, reason=reason)
    discarded_by = ActorId(discarded_by_uuid)
    first = discard_subject.decide(state=state, command=command, now=now, discarded_by=discarded_by)
    second = discard_subject.decide(
        state=state, command=command, now=now, discarded_by=discarded_by
    )
    assert first == second
