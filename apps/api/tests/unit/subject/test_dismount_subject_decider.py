"""Unit tests for the `dismount_subject` slice's pure decider."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

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

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_ACTOR = ActorId(uuid4())


def _subject(
    *,
    status: SubjectStatus = SubjectStatus.MOUNTED,
    mounted_on_asset_id: UUID | None = None,
) -> Subject:
    return Subject(
        id=uuid4(),
        name=SubjectName("Sample-A1"),
        status=status,
        mounted_on_asset_id=mounted_on_asset_id if mounted_on_asset_id is not None else uuid4(),
    )


@pytest.mark.unit
def test_decide_emits_subject_dismounted_from_mounted() -> None:
    asset_id = uuid4()
    state = _subject(status=SubjectStatus.MOUNTED, mounted_on_asset_id=asset_id)
    events = dismount_subject.decide(
        state=state,
        command=DismountSubject(subject_id=state.id, reason="run complete"),
        now=_NOW,
        dismounted_by=_ACTOR,
    )
    assert events == [
        SubjectDismounted(
            subject_id=state.id,
            from_asset_id=asset_id,
            reason="run complete",
            occurred_at=_NOW,
            dismounted_by=_ACTOR,
        )
    ]


@pytest.mark.unit
def test_decide_emits_subject_dismounted_from_measured() -> None:
    """4f: dismount allowed from Measured too (after a scan, sample
    can be moved to next stage without going terminal)."""
    asset_id = uuid4()
    state = _subject(status=SubjectStatus.MEASURED, mounted_on_asset_id=asset_id)
    events = dismount_subject.decide(
        state=state,
        command=DismountSubject(subject_id=state.id, reason="moving to detector"),
        now=_NOW,
        dismounted_by=_ACTOR,
    )
    assert len(events) == 1
    assert events[0].from_asset_id == asset_id
    assert events[0].reason == "moving to detector"


@pytest.mark.unit
def test_decide_raises_subject_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(SubjectNotFoundError) as exc_info:
        dismount_subject.decide(
            state=None,
            command=DismountSubject(subject_id=target_id, reason="x"),
            now=_NOW,
            dismounted_by=_ACTOR,
        )
    assert exc_info.value.subject_id == target_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "current",
    [
        SubjectStatus.RECEIVED,
        SubjectStatus.REMOVED,
        SubjectStatus.RETURNED,
        SubjectStatus.STORED,
        SubjectStatus.DISCARDED,
    ],
)
def test_decide_raises_cannot_dismount_for_disallowed_states(
    current: SubjectStatus,
) -> None:
    """Five states must reject dismount: pre-mount (Received) and the
    four post-removal states. The two ALLOWED states (Mounted,
    Measured) are covered above."""
    state = _subject(status=current, mounted_on_asset_id=None)
    with pytest.raises(SubjectCannotDismountError) as exc_info:
        dismount_subject.decide(
            state=state,
            command=DismountSubject(subject_id=state.id, reason="x"),
            now=_NOW,
            dismounted_by=_ACTOR,
        )
    assert exc_info.value.current_status is current


@pytest.mark.unit
def test_decide_error_message_lists_both_allowed_source_states() -> None:
    state = _subject(status=SubjectStatus.RECEIVED, mounted_on_asset_id=None)
    with pytest.raises(SubjectCannotDismountError) as exc_info:
        dismount_subject.decide(
            state=state,
            command=DismountSubject(subject_id=state.id, reason="x"),
            now=_NOW,
            dismounted_by=_ACTOR,
        )
    msg = str(exc_info.value)
    assert "Mounted" in msg
    assert "Measured" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _subject(status=SubjectStatus.MOUNTED)
    command = DismountSubject(subject_id=state.id, reason="x")
    first = dismount_subject.decide(state=state, command=command, now=_NOW, dismounted_by=_ACTOR)
    second = dismount_subject.decide(state=state, command=command, now=_NOW, dismounted_by=_ACTOR)
    assert first == second
