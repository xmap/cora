"""Property-based tests for `mount_subject.decide` (Subject BC).

Complements the example-based `test_mount_subject_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition with cross-aggregate validation and actor
attribution

    (state, command, context, now, mounted_by) -> list[SubjectMounted]

Load-bearing properties:

  - state=None always raises `SubjectNotFoundError` carrying
    command.subject_id.
  - The source-state partition is total over `SubjectStatus`: only
    `Received` (with an `Active` mount-target Asset) emits exactly one
    `SubjectMounted` (subject_id=state.id, asset_id=context.asset.id,
    reason=command.reason, occurred_at=now, mounted_by threaded); every
    other status raises `SubjectCannotMountError` carrying the current
    status.
  - The cross-aggregate gate is total over `AssetLifecycle`: a Received
    subject with a non-`Active` mount-target raises
    `SubjectMountTargetUnavailableError`.
  - The emitted event's subject_id is `state.id`, never
    command.subject_id.
  - Pure: same (state, command, context, now, mounted_by) returns equal
    events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import (
    Asset,
    AssetLifecycle,
    AssetName,
    AssetTier,
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
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_MOUNTABLE_SOURCES = (SubjectStatus.RECEIVED,)
_DISALLOWED_SOURCES = tuple(s for s in SubjectStatus if s not in frozenset(_MOUNTABLE_SOURCES))
_NON_ACTIVE_LIFECYCLES = tuple(
    lifecycle for lifecycle in AssetLifecycle if lifecycle is not AssetLifecycle.ACTIVE
)


def _subject(*, subject_id: UUID, status: SubjectStatus) -> Subject:
    return Subject(id=subject_id, name=SubjectName("PorousCeramicSample-A"), status=status)


def _asset(
    *,
    asset_id: UUID,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("Goniometer-1"),
        tier=AssetTier.DEVICE,
        parent_id=asset_id,
        lifecycle=lifecycle,
        family_ids=frozenset(),
    )


@pytest.mark.unit
@given(
    subject_id=st.uuids(),
    asset_id=st.uuids(),
    reason=printable_ascii_text(min_size=1, max_size=500),
    now=aware_datetimes(),
    mounted_by_uuid=st.uuids(),
)
def test_mount_with_none_state_always_raises_not_found(
    subject_id: UUID,
    asset_id: UUID,
    reason: str,
    now: datetime,
    mounted_by_uuid: UUID,
) -> None:
    """Empty stream always raises `SubjectNotFoundError` carrying command.subject_id."""
    with pytest.raises(SubjectNotFoundError) as exc:
        mount_subject.decide(
            state=None,
            command=MountSubject(subject_id=subject_id, asset_id=asset_id, reason=reason),
            context=MountSubjectContext(asset=_asset(asset_id=asset_id)),
            now=now,
            mounted_by=ActorId(mounted_by_uuid),
        )
    assert exc.value.subject_id == subject_id


@pytest.mark.unit
@given(
    subject_id=st.uuids(),
    asset_id=st.uuids(),
    reason=printable_ascii_text(min_size=1, max_size=500),
    now=aware_datetimes(),
    mounted_by_uuid=st.uuids(),
)
def test_mount_from_received_emits_single_event(
    subject_id: UUID,
    asset_id: UUID,
    reason: str,
    now: datetime,
    mounted_by_uuid: UUID,
) -> None:
    """Received is the only mountable source; with an Active asset emits one SubjectMounted."""
    mounted_by = ActorId(mounted_by_uuid)
    events = mount_subject.decide(
        state=_subject(subject_id=subject_id, status=SubjectStatus.RECEIVED),
        command=MountSubject(subject_id=subject_id, asset_id=asset_id, reason=reason),
        context=MountSubjectContext(asset=_asset(asset_id=asset_id)),
        now=now,
        mounted_by=mounted_by,
    )
    assert events == [
        SubjectMounted(
            subject_id=subject_id,
            asset_id=asset_id,
            reason=reason,
            occurred_at=now,
            mounted_by=mounted_by,
        )
    ]


@pytest.mark.unit
@given(
    subject_id=st.uuids(),
    asset_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    reason=printable_ascii_text(min_size=1, max_size=500),
    now=aware_datetimes(),
    mounted_by_uuid=st.uuids(),
)
def test_mount_from_disallowed_source_always_raises_cannot_mount(
    subject_id: UUID,
    asset_id: UUID,
    source: SubjectStatus,
    reason: str,
    now: datetime,
    mounted_by_uuid: UUID,
) -> None:
    """Any source other than Received raises, carrying the current status."""
    with pytest.raises(SubjectCannotMountError) as exc:
        mount_subject.decide(
            state=_subject(subject_id=subject_id, status=source),
            command=MountSubject(subject_id=subject_id, asset_id=asset_id, reason=reason),
            context=MountSubjectContext(asset=_asset(asset_id=asset_id)),
            now=now,
            mounted_by=ActorId(mounted_by_uuid),
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    subject_id=st.uuids(),
    asset_id=st.uuids(),
    lifecycle=st.sampled_from(_NON_ACTIVE_LIFECYCLES),
    reason=printable_ascii_text(min_size=1, max_size=500),
    now=aware_datetimes(),
    mounted_by_uuid=st.uuids(),
)
def test_mount_with_non_active_asset_always_raises_target_unavailable(
    subject_id: UUID,
    asset_id: UUID,
    lifecycle: AssetLifecycle,
    reason: str,
    now: datetime,
    mounted_by_uuid: UUID,
) -> None:
    """Received subject with a non-Active mount-target raises, carrying the asset lifecycle."""
    with pytest.raises(SubjectMountTargetUnavailableError) as exc:
        mount_subject.decide(
            state=_subject(subject_id=subject_id, status=SubjectStatus.RECEIVED),
            command=MountSubject(subject_id=subject_id, asset_id=asset_id, reason=reason),
            context=MountSubjectContext(asset=_asset(asset_id=asset_id, lifecycle=lifecycle)),
            now=now,
            mounted_by=ActorId(mounted_by_uuid),
        )
    assert exc.value.subject_id == subject_id
    assert exc.value.asset_id == asset_id
    assert exc.value.current_lifecycle == lifecycle.value


@pytest.mark.unit
@given(
    state_subject_id=st.uuids(),
    command_subject_id=st.uuids(),
    asset_id=st.uuids(),
    reason=printable_ascii_text(min_size=1, max_size=500),
    now=aware_datetimes(),
    mounted_by_uuid=st.uuids(),
)
def test_mount_uses_state_id_not_command_subject_id(
    state_subject_id: UUID,
    command_subject_id: UUID,
    asset_id: UUID,
    reason: str,
    now: datetime,
    mounted_by_uuid: UUID,
) -> None:
    """The emitted event's subject_id is state.id, not command.subject_id."""
    assume(state_subject_id != command_subject_id)
    events = mount_subject.decide(
        state=_subject(subject_id=state_subject_id, status=SubjectStatus.RECEIVED),
        command=MountSubject(subject_id=command_subject_id, asset_id=asset_id, reason=reason),
        context=MountSubjectContext(asset=_asset(asset_id=asset_id)),
        now=now,
        mounted_by=ActorId(mounted_by_uuid),
    )
    assert events[0].subject_id == state_subject_id


@pytest.mark.unit
@given(
    subject_id=st.uuids(),
    asset_id=st.uuids(),
    reason=printable_ascii_text(min_size=1, max_size=500),
    now=aware_datetimes(),
    mounted_by_uuid=st.uuids(),
)
def test_mount_is_pure_same_input_same_output(
    subject_id: UUID,
    asset_id: UUID,
    reason: str,
    now: datetime,
    mounted_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _subject(subject_id=subject_id, status=SubjectStatus.RECEIVED)
    command = MountSubject(subject_id=subject_id, asset_id=asset_id, reason=reason)
    context = MountSubjectContext(asset=_asset(asset_id=asset_id))
    mounted_by = ActorId(mounted_by_uuid)
    first = mount_subject.decide(
        state=state, command=command, context=context, now=now, mounted_by=mounted_by
    )
    second = mount_subject.decide(
        state=state, command=command, context=context, now=now, mounted_by=mounted_by
    )
    assert first == second
