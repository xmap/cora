"""Property-based tests for `dismount_subject.decide` (Subject BC).

Complements the example-based `test_dismount_subject_decider.py` with
universal claims across generated inputs. The decider is a pure
pre-terminal transition with a reason and actor attribution

    (state, command, now, dismounted_by) -> list[SubjectDismounted]

Load-bearing properties:

  - state=None always raises `SubjectNotFoundError` carrying
    command.subject_id.
  - The source-state partition is total over `SubjectStatus`: only
    `Mounted` and `Measured` emit exactly one `SubjectDismounted`
    (subject_id=state.id, from_asset_id=state.mounted_on_asset_id,
    reason threaded, occurred_at=now, dismounted_by threaded); every
    other status raises `SubjectCannotDismountError` carrying the
    current status.
  - The emitted event's subject_id is `state.id`, never
    command.subject_id.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotDismountError,
    SubjectDismounted,
    SubjectName,
    SubjectNotFoundError,
    SubjectStatus,
)
from cora.subject.features import dismount_subject
from cora.subject.features.dismount_subject import DismountSubject
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_REASON = printable_ascii_text(min_size=1, max_size=500)
_FROM_ASSET_ID = UUID(int=7)
_DISMOUNTABLE_SOURCES = (SubjectStatus.MOUNTED, SubjectStatus.MEASURED)
_DISALLOWED_SOURCES = tuple(s for s in SubjectStatus if s not in frozenset(_DISMOUNTABLE_SOURCES))


def _subject(*, subject_id: UUID, status: SubjectStatus) -> Subject:
    return Subject(
        id=subject_id,
        name=SubjectName("PorousCeramicSample-A"),
        status=status,
        mounted_on_asset_id=_FROM_ASSET_ID,
    )


@pytest.mark.unit
@given(subject_id=st.uuids(), reason=_REASON, now=aware_datetimes(), dismounted_by_uuid=st.uuids())
def test_dismount_with_none_state_always_raises_not_found(
    subject_id: UUID,
    reason: str,
    now: datetime,
    dismounted_by_uuid: UUID,
) -> None:
    """Empty stream always raises `SubjectNotFoundError` carrying command.subject_id."""
    with pytest.raises(SubjectNotFoundError) as exc:
        dismount_subject.decide(
            state=None,
            command=DismountSubject(subject_id=subject_id, reason=reason),
            now=now,
            dismounted_by=ActorId(dismounted_by_uuid),
        )
    assert exc.value.subject_id == subject_id


@pytest.mark.unit
@given(
    subject_id=st.uuids(),
    source=st.sampled_from(_DISMOUNTABLE_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
    dismounted_by_uuid=st.uuids(),
)
def test_dismount_from_permitted_source_emits_single_event(
    subject_id: UUID,
    source: SubjectStatus,
    reason: str,
    now: datetime,
    dismounted_by_uuid: UUID,
) -> None:
    """Mounted and Measured are the dismountable sources; each emits one SubjectDismounted."""
    dismounted_by = ActorId(dismounted_by_uuid)
    events = dismount_subject.decide(
        state=_subject(subject_id=subject_id, status=source),
        command=DismountSubject(subject_id=subject_id, reason=reason),
        now=now,
        dismounted_by=dismounted_by,
    )
    assert events == [
        SubjectDismounted(
            subject_id=subject_id,
            from_asset_id=_FROM_ASSET_ID,
            reason=reason,
            occurred_at=now,
            dismounted_by=dismounted_by,
        )
    ]


@pytest.mark.unit
@given(
    subject_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
    dismounted_by_uuid=st.uuids(),
)
def test_dismount_from_disallowed_source_always_raises_cannot_dismount(
    subject_id: UUID,
    source: SubjectStatus,
    reason: str,
    now: datetime,
    dismounted_by_uuid: UUID,
) -> None:
    """Any source other than Mounted or Measured raises, carrying the current status."""
    with pytest.raises(SubjectCannotDismountError) as exc:
        dismount_subject.decide(
            state=_subject(subject_id=subject_id, status=source),
            command=DismountSubject(subject_id=subject_id, reason=reason),
            now=now,
            dismounted_by=ActorId(dismounted_by_uuid),
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_subject_id=st.uuids(),
    command_subject_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    dismounted_by_uuid=st.uuids(),
)
def test_dismount_uses_state_id_not_command_subject_id(
    state_subject_id: UUID,
    command_subject_id: UUID,
    reason: str,
    now: datetime,
    dismounted_by_uuid: UUID,
) -> None:
    """The emitted event's subject_id is state.id, not command.subject_id."""
    assume(state_subject_id != command_subject_id)
    events = dismount_subject.decide(
        state=_subject(subject_id=state_subject_id, status=SubjectStatus.MOUNTED),
        command=DismountSubject(subject_id=command_subject_id, reason=reason),
        now=now,
        dismounted_by=ActorId(dismounted_by_uuid),
    )
    assert events[0].subject_id == state_subject_id


@pytest.mark.unit
@given(subject_id=st.uuids(), reason=_REASON, now=aware_datetimes(), dismounted_by_uuid=st.uuids())
def test_dismount_is_pure_same_input_same_output(
    subject_id: UUID,
    reason: str,
    now: datetime,
    dismounted_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _subject(subject_id=subject_id, status=SubjectStatus.MOUNTED)
    command = DismountSubject(subject_id=subject_id, reason=reason)
    dismounted_by = ActorId(dismounted_by_uuid)
    first = dismount_subject.decide(
        state=state, command=command, now=now, dismounted_by=dismounted_by
    )
    second = dismount_subject.decide(
        state=state, command=command, now=now, dismounted_by=dismounted_by
    )
    assert first == second
