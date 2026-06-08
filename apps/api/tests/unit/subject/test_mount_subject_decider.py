"""Unit tests for the `mount_subject` slice's pure decider."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetLevel,
    AssetLifecycle,
    AssetName,
)
from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotMountError,
    SubjectMounted,
    SubjectMountTargetUnavailableError,
    SubjectName,
    SubjectNotFoundError,
    SubjectStatus,
)
from cora.subject.features import mount_subject
from cora.subject.features.mount_subject import MountSubject, MountSubjectContext

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_ACTOR = ActorId(uuid4())


def _subject(*, status: SubjectStatus = SubjectStatus.RECEIVED) -> Subject:
    return Subject(id=uuid4(), name=SubjectName("Sample-A1"), status=status)


def _asset(
    *,
    asset_id: UUID | None = None,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
) -> Asset:
    return Asset(
        id=asset_id or uuid4(),
        name=AssetName("Goniometer-1"),
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        family_ids=frozenset(),
    )


@pytest.mark.unit
def test_decide_emits_subject_mounted_when_state_is_received_and_asset_active() -> None:
    state = _subject(status=SubjectStatus.RECEIVED)
    asset = _asset()
    events = mount_subject.decide(
        state=state,
        command=MountSubject(subject_id=state.id, asset_id=asset.id, reason=""),
        context=MountSubjectContext(asset=asset),
        now=_NOW,
        mounted_by=_ACTOR,
    )
    assert events == [
        SubjectMounted(
            subject_id=state.id, asset_id=asset.id, reason="", occurred_at=_NOW, mounted_by=_ACTOR
        )
    ]


@pytest.mark.unit
def test_decide_raises_subject_not_found_when_state_is_none() -> None:
    """Update-style precondition: state must exist."""
    target_id = uuid4()
    asset = _asset()
    with pytest.raises(SubjectNotFoundError) as exc_info:
        mount_subject.decide(
            state=None,
            command=MountSubject(subject_id=target_id, asset_id=asset.id, reason=""),
            context=MountSubjectContext(asset=asset),
            now=_NOW,
            mounted_by=_ACTOR,
        )
    assert exc_info.value.subject_id == target_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "current",
    [
        SubjectStatus.MOUNTED,
        SubjectStatus.MEASURED,
        SubjectStatus.REMOVED,
        SubjectStatus.RETURNED,
        SubjectStatus.STORED,
        SubjectStatus.DISCARDED,
    ],
)
def test_decide_raises_cannot_mount_for_every_non_received_state(
    current: SubjectStatus,
) -> None:
    """Strict semantics, not idempotent: mounting an already-mounted (or
    otherwise non-Received) subject raises. Six wrong states tested
    explicitly so a future relaxation has to flip every parametrized
    case deliberately."""
    state = _subject(status=current)
    asset = _asset()
    with pytest.raises(SubjectCannotMountError) as exc_info:
        mount_subject.decide(
            state=state,
            command=MountSubject(subject_id=state.id, asset_id=asset.id, reason=""),
            context=MountSubjectContext(asset=asset),
            now=_NOW,
            mounted_by=_ACTOR,
        )
    assert exc_info.value.subject_id == state.id
    assert exc_info.value.current_status is current


@pytest.mark.unit
def test_decide_error_carries_current_status_for_diagnostic_messaging() -> None:
    """The error message includes both the current state and the
    expected source state — pinned because the route's 409 body
    surfaces this string."""
    state = _subject(status=SubjectStatus.MEASURED)
    asset = _asset()
    with pytest.raises(SubjectCannotMountError) as exc_info:
        mount_subject.decide(
            state=state,
            command=MountSubject(subject_id=state.id, asset_id=asset.id, reason=""),
            context=MountSubjectContext(asset=asset),
            now=_NOW,
            mounted_by=_ACTOR,
        )
    msg = str(exc_info.value)
    assert "Measured" in msg
    assert "Received" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _subject(status=SubjectStatus.RECEIVED)
    asset = _asset()
    command = MountSubject(subject_id=state.id, asset_id=asset.id, reason="")
    context = MountSubjectContext(asset=asset)
    first = mount_subject.decide(
        state=state, command=command, context=context, now=_NOW, mounted_by=_ACTOR
    )
    second = mount_subject.decide(
        state=state, command=command, context=context, now=_NOW, mounted_by=_ACTOR
    )
    assert first == second


@pytest.mark.unit
@pytest.mark.parametrize(
    "lifecycle",
    [
        AssetLifecycle.COMMISSIONED,
        AssetLifecycle.MAINTENANCE,
        AssetLifecycle.DECOMMISSIONED,
    ],
)
def test_decide_raises_when_asset_lifecycle_not_active(
    lifecycle: AssetLifecycle,
) -> None:
    state = _subject(status=SubjectStatus.RECEIVED)
    asset = _asset(lifecycle=lifecycle)
    with pytest.raises(SubjectMountTargetUnavailableError) as exc_info:
        mount_subject.decide(
            state=state,
            command=MountSubject(subject_id=state.id, asset_id=asset.id, reason=""),
            context=MountSubjectContext(asset=asset),
            now=_NOW,
            mounted_by=_ACTOR,
        )
    assert exc_info.value.subject_id == state.id
    assert exc_info.value.asset_id == asset.id
    assert exc_info.value.current_lifecycle == lifecycle.value
