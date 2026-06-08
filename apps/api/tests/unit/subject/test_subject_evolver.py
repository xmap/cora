"""Unit tests for the Subject aggregate's evolver."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import (
    Subject,
    SubjectName,
    SubjectStatus,
    evolve,
    fold,
)
from cora.subject.aggregates.subject.events import (
    SubjectDiscarded,
    SubjectDismounted,
    SubjectMeasured,
    SubjectMounted,
    SubjectRegistered,
    SubjectRemoved,
    SubjectReturned,
    SubjectStored,
)
from cora.subject.features import register_subject
from cora.subject.features.register_subject import RegisterSubject

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_ACTOR = ActorId(uuid4())
_ASSET_ID = UUID("01900000-0000-7000-8000-00000000a55e")


@pytest.mark.unit
def test_evolve_subject_registered_sets_status_to_received() -> None:
    """SubjectRegistered is the genesis event; status defaults to
    Received via the evolver. Pin so a future change (for example, adding
    `initial_status` to the event payload) is a deliberate
    additive-state evolution."""
    subject_id = uuid4()
    state = evolve(
        None,
        SubjectRegistered(
            subject_id=subject_id, name="Sample-A1", occurred_at=_NOW, registered_by=_ACTOR
        ),
    )
    assert state == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.RECEIVED
    )


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_subject_registered_returns_subject() -> None:
    subject_id = uuid4()
    state = fold(
        [
            SubjectRegistered(
                subject_id=subject_id, name="Sample-A1", occurred_at=_NOW, registered_by=_ACTOR
            )
        ]
    )
    assert state == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.RECEIVED
    )


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    subject_id = uuid4()
    events = [
        SubjectRegistered(
            subject_id=subject_id, name="Sample-A1", occurred_at=_NOW, registered_by=_ACTOR
        )
    ]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip() -> None:
    """The events the decider produces must rebuild the expected state."""
    new_id = uuid4()
    command = RegisterSubject(name="  Sample-A1  ")  # whitespace exercises the VO trim

    events = register_subject.decide(
        state=None, command=command, now=_NOW, new_id=new_id, registered_by=_ACTOR
    )
    rebuilt = fold(events)

    assert rebuilt == Subject(
        id=new_id, name=SubjectName("Sample-A1"), status=SubjectStatus.RECEIVED
    )


# ---------- SubjectMounted ----------


@pytest.mark.unit
def test_evolve_subject_mounted_flips_status_to_mounted() -> None:
    """SubjectMounted folded onto a Received subject sets status=MOUNTED.
    Status field is NOT in the event payload; the evolver derives it from
    the event TYPE (same precedent as ActorDeactivated -> active=False)."""
    subject_id = uuid4()
    received = Subject(id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.RECEIVED)
    mounted = evolve(
        received,
        SubjectMounted(
            subject_id=subject_id,
            asset_id=_ASSET_ID,
            reason="",
            occurred_at=_NOW,
            mounted_by=_ACTOR,
        ),
    )
    assert mounted == Subject(
        id=subject_id,
        name=SubjectName("Sample-A1"),
        status=SubjectStatus.MOUNTED,
        mounted_on_asset_id=_ASSET_ID,
    )


@pytest.mark.unit
def test_evolve_subject_mounted_preserves_id_and_name() -> None:
    """The evolver only updates `status`; id and name are carried over
    from prior state. Pinned so a future change that accidentally
    drops the name (for example, refactor that builds Subject from event
    fields only) is caught."""
    subject_id = uuid4()
    received = Subject(id=subject_id, name=SubjectName("Original"), status=SubjectStatus.RECEIVED)
    mounted = evolve(
        received,
        SubjectMounted(
            subject_id=subject_id,
            asset_id=_ASSET_ID,
            reason="",
            occurred_at=_NOW,
            mounted_by=_ACTOR,
        ),
    )
    assert mounted.id == subject_id
    assert mounted.name == SubjectName("Original")


@pytest.mark.unit
def test_evolve_subject_mounted_on_empty_state_raises() -> None:
    """SubjectMounted before SubjectRegistered = corrupted stream.
    Fail loud rather than silently producing an empty subject."""
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            SubjectMounted(
                subject_id=uuid4(),
                asset_id=_ASSET_ID,
                reason="",
                occurred_at=_NOW,
                mounted_by=_ACTOR,
            ),
        )


@pytest.mark.unit
def test_fold_register_then_mount_yields_mounted_subject() -> None:
    """End-to-end fold: registration + mount produces a Mounted subject."""
    subject_id = uuid4()
    state = fold(
        [
            SubjectRegistered(
                subject_id=subject_id, name="Sample-A1", occurred_at=_NOW, registered_by=_ACTOR
            ),
            SubjectMounted(
                subject_id=subject_id,
                asset_id=_ASSET_ID,
                reason="",
                occurred_at=_NOW,
                mounted_by=_ACTOR,
            ),
        ]
    )
    assert state == Subject(
        id=subject_id,
        name=SubjectName("Sample-A1"),
        status=SubjectStatus.MOUNTED,
        mounted_on_asset_id=_ASSET_ID,
    )


# ---------- SubjectMeasured ----------


@pytest.mark.unit
def test_evolve_subject_measured_flips_status_to_measured() -> None:
    """SubjectMeasured folded onto a Mounted subject sets status=MEASURED.
    Status field is NOT in the event payload; the evolver derives it
    from the event TYPE (same precedent as SubjectMounted)."""
    subject_id = uuid4()
    mounted = Subject(id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.MOUNTED)
    measured = evolve(
        mounted, SubjectMeasured(subject_id=subject_id, occurred_at=_NOW, measured_by=_ACTOR)
    )
    assert measured == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.MEASURED
    )


@pytest.mark.unit
def test_evolve_subject_measured_preserves_id_and_name() -> None:
    subject_id = uuid4()
    mounted = Subject(id=subject_id, name=SubjectName("Original"), status=SubjectStatus.MOUNTED)
    measured = evolve(
        mounted, SubjectMeasured(subject_id=subject_id, occurred_at=_NOW, measured_by=_ACTOR)
    )
    assert measured.id == subject_id
    assert measured.name == SubjectName("Original")


@pytest.mark.unit
def test_evolve_subject_measured_on_empty_state_raises() -> None:
    """SubjectMeasured before SubjectRegistered = corrupted stream.
    Fail loud rather than silently producing an empty subject."""
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, SubjectMeasured(subject_id=uuid4(), occurred_at=_NOW, measured_by=_ACTOR))


@pytest.mark.unit
def test_fold_register_mount_measure_yields_measured_subject() -> None:
    """End-to-end fold: registration + mount + measure produces a Measured subject."""
    subject_id = uuid4()
    state = fold(
        [
            SubjectRegistered(
                subject_id=subject_id, name="Sample-A1", occurred_at=_NOW, registered_by=_ACTOR
            ),
            SubjectMounted(
                subject_id=subject_id,
                asset_id=_ASSET_ID,
                reason="",
                occurred_at=_NOW,
                mounted_by=_ACTOR,
            ),
            SubjectMeasured(subject_id=subject_id, occurred_at=_NOW, measured_by=_ACTOR),
        ]
    )
    assert state == Subject(
        id=subject_id,
        name=SubjectName("Sample-A1"),
        status=SubjectStatus.MEASURED,
        mounted_on_asset_id=_ASSET_ID,
    )


# ---------- SubjectRemoved ----------


@pytest.mark.unit
def test_evolve_subject_removed_from_mounted_flips_status_to_removed() -> None:
    """SubjectRemoved folded onto a Mounted subject sets status=REMOVED.
    Multi-source-to-single-target: the evolver sets the same target
    status regardless of which source state preceded the event."""
    subject_id = uuid4()
    mounted = Subject(id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.MOUNTED)
    removed = evolve(
        mounted, SubjectRemoved(subject_id=subject_id, occurred_at=_NOW, removed_by=_ACTOR)
    )
    assert removed == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.REMOVED
    )


@pytest.mark.unit
def test_evolve_subject_removed_from_measured_flips_status_to_removed() -> None:
    """The other source state for Removed: Measured -> Removed. Pinned
    so a future change that only handles one source state in the
    evolver is caught."""
    subject_id = uuid4()
    measured = Subject(id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.MEASURED)
    removed = evolve(
        measured, SubjectRemoved(subject_id=subject_id, occurred_at=_NOW, removed_by=_ACTOR)
    )
    assert removed == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.REMOVED
    )


@pytest.mark.unit
def test_evolve_subject_removed_preserves_id_and_name() -> None:
    subject_id = uuid4()
    measured = Subject(id=subject_id, name=SubjectName("Original"), status=SubjectStatus.MEASURED)
    removed = evolve(
        measured, SubjectRemoved(subject_id=subject_id, occurred_at=_NOW, removed_by=_ACTOR)
    )
    assert removed.id == subject_id
    assert removed.name == SubjectName("Original")


@pytest.mark.unit
def test_evolve_subject_removed_on_empty_state_raises() -> None:
    """SubjectRemoved before SubjectRegistered = corrupted stream."""
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, SubjectRemoved(subject_id=uuid4(), occurred_at=_NOW, removed_by=_ACTOR))


@pytest.mark.unit
def test_fold_register_mount_remove_yields_removed_subject() -> None:
    """End-to-end fold: registration + mount + remove (skipping measure)
    produces a Removed subject. Pinned because the multi-source-state
    contract has to be honored at the fold level too, not just the
    decider."""
    subject_id = uuid4()
    state = fold(
        [
            SubjectRegistered(
                subject_id=subject_id, name="Sample-A1", occurred_at=_NOW, registered_by=_ACTOR
            ),
            SubjectMounted(
                subject_id=subject_id,
                asset_id=_ASSET_ID,
                reason="",
                occurred_at=_NOW,
                mounted_by=_ACTOR,
            ),
            SubjectRemoved(subject_id=subject_id, occurred_at=_NOW, removed_by=_ACTOR),
        ]
    )
    assert state == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.REMOVED
    )


@pytest.mark.unit
def test_fold_register_mount_measure_remove_yields_removed_subject() -> None:
    """End-to-end fold: full happy path (register + mount + measure +
    remove) produces a Removed subject."""
    subject_id = uuid4()
    state = fold(
        [
            SubjectRegistered(
                subject_id=subject_id, name="Sample-A1", occurred_at=_NOW, registered_by=_ACTOR
            ),
            SubjectMounted(
                subject_id=subject_id,
                asset_id=_ASSET_ID,
                reason="",
                occurred_at=_NOW,
                mounted_by=_ACTOR,
            ),
            SubjectMeasured(subject_id=subject_id, occurred_at=_NOW, measured_by=_ACTOR),
            SubjectRemoved(subject_id=subject_id, occurred_at=_NOW, removed_by=_ACTOR),
        ]
    )
    assert state == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.REMOVED
    )


# ---------- Terminal disposition events ----------


@pytest.mark.unit
def test_evolve_subject_returned_flips_status_to_returned() -> None:
    """SubjectReturned folded onto a Removed subject sets status=RETURNED.
    Terminal disposition: same evolver pattern (event TYPE encodes
    state change), no payload field."""
    subject_id = uuid4()
    removed = Subject(id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.REMOVED)
    returned = evolve(
        removed, SubjectReturned(subject_id=subject_id, occurred_at=_NOW, returned_by=_ACTOR)
    )
    assert returned == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.RETURNED
    )


@pytest.mark.unit
def test_evolve_subject_stored_flips_status_to_stored() -> None:
    subject_id = uuid4()
    removed = Subject(id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.REMOVED)
    stored = evolve(
        removed, SubjectStored(subject_id=subject_id, occurred_at=_NOW, stored_by=_ACTOR)
    )
    assert stored == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.STORED
    )


@pytest.mark.unit
def test_evolve_subject_discarded_flips_status_to_discarded() -> None:
    subject_id = uuid4()
    removed = Subject(id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.REMOVED)
    discarded = evolve(
        removed,
        SubjectDiscarded(
            subject_id=subject_id, reason="contaminated", occurred_at=_NOW, discarded_by=_ACTOR
        ),
    )
    assert discarded == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.DISCARDED
    )


@pytest.mark.unit
def test_evolve_terminal_events_preserve_id_and_name() -> None:
    """All three terminal events only update `status`; id and name
    carry over from prior state. Pinned so a future change that
    accidentally drops the name (for example, refactor that builds Subject
    from event fields only) is caught for all three."""
    subject_id = uuid4()
    removed = Subject(id=subject_id, name=SubjectName("Original"), status=SubjectStatus.REMOVED)
    for event in (
        SubjectReturned(subject_id=subject_id, occurred_at=_NOW, returned_by=_ACTOR),
        SubjectStored(subject_id=subject_id, occurred_at=_NOW, stored_by=_ACTOR),
        SubjectDiscarded(
            subject_id=subject_id, reason="contaminated", occurred_at=_NOW, discarded_by=_ACTOR
        ),
    ):
        result = evolve(removed, event)
        assert result.id == subject_id
        assert result.name == SubjectName("Original")


@pytest.mark.unit
def test_evolve_subject_returned_on_empty_state_raises() -> None:
    """Terminal events before SubjectRegistered = corrupted stream."""
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, SubjectReturned(subject_id=uuid4(), occurred_at=_NOW, returned_by=_ACTOR))


@pytest.mark.unit
def test_evolve_subject_stored_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, SubjectStored(subject_id=uuid4(), occurred_at=_NOW, stored_by=_ACTOR))


@pytest.mark.unit
def test_evolve_subject_discarded_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            SubjectDiscarded(
                subject_id=uuid4(), reason="contaminated", occurred_at=_NOW, discarded_by=_ACTOR
            ),
        )


@pytest.mark.unit
def test_fold_full_lifecycle_to_returned() -> None:
    """End-to-end fold: register + mount + measure + remove + return
    produces a Returned subject. Pinned because the full lifecycle is
    the canonical happy path for one of the three terminal slices."""
    subject_id = uuid4()
    state = fold(
        [
            SubjectRegistered(
                subject_id=subject_id, name="Sample-A1", occurred_at=_NOW, registered_by=_ACTOR
            ),
            SubjectMounted(
                subject_id=subject_id,
                asset_id=_ASSET_ID,
                reason="",
                occurred_at=_NOW,
                mounted_by=_ACTOR,
            ),
            SubjectMeasured(subject_id=subject_id, occurred_at=_NOW, measured_by=_ACTOR),
            SubjectRemoved(subject_id=subject_id, occurred_at=_NOW, removed_by=_ACTOR),
            SubjectReturned(subject_id=subject_id, occurred_at=_NOW, returned_by=_ACTOR),
        ]
    )
    assert state == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.RETURNED
    )


@pytest.mark.unit
def test_fold_full_lifecycle_to_stored() -> None:
    subject_id = uuid4()
    state = fold(
        [
            SubjectRegistered(
                subject_id=subject_id, name="Sample-A1", occurred_at=_NOW, registered_by=_ACTOR
            ),
            SubjectMounted(
                subject_id=subject_id,
                asset_id=_ASSET_ID,
                reason="",
                occurred_at=_NOW,
                mounted_by=_ACTOR,
            ),
            SubjectMeasured(subject_id=subject_id, occurred_at=_NOW, measured_by=_ACTOR),
            SubjectRemoved(subject_id=subject_id, occurred_at=_NOW, removed_by=_ACTOR),
            SubjectStored(subject_id=subject_id, occurred_at=_NOW, stored_by=_ACTOR),
        ]
    )
    assert state == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.STORED
    )


@pytest.mark.unit
def test_fold_full_lifecycle_to_discarded() -> None:
    subject_id = uuid4()
    state = fold(
        [
            SubjectRegistered(
                subject_id=subject_id, name="Sample-A1", occurred_at=_NOW, registered_by=_ACTOR
            ),
            SubjectMounted(
                subject_id=subject_id,
                asset_id=_ASSET_ID,
                reason="",
                occurred_at=_NOW,
                mounted_by=_ACTOR,
            ),
            SubjectMeasured(subject_id=subject_id, occurred_at=_NOW, measured_by=_ACTOR),
            SubjectRemoved(subject_id=subject_id, occurred_at=_NOW, removed_by=_ACTOR),
            SubjectDiscarded(
                subject_id=subject_id, reason="contaminated", occurred_at=_NOW, discarded_by=_ACTOR
            ),
        ]
    )
    assert state == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.DISCARDED
    )


# ---------- SubjectDismounted ----------


@pytest.mark.unit
def test_evolve_subject_dismounted_returns_to_received_with_no_asset() -> None:
    """4f: dismount returns the Subject to Received status with
    mounted_on_asset_id cleared. Sample is back to 'in the lab, not
    currently mounted'; ready for re-mount or removal."""
    subject_id = uuid4()
    prior = Subject(
        id=subject_id,
        name=SubjectName("Sample-A1"),
        status=SubjectStatus.MOUNTED,
        mounted_on_asset_id=_ASSET_ID,
    )
    state = evolve(
        prior,
        SubjectDismounted(
            subject_id=subject_id,
            from_asset_id=_ASSET_ID,
            reason="run complete",
            occurred_at=_NOW,
            dismounted_by=_ACTOR,
        ),
    )
    assert state.status is SubjectStatus.RECEIVED
    assert state.mounted_on_asset_id is None


@pytest.mark.unit
def test_evolve_subject_dismounted_preserves_name() -> None:
    subject_id = uuid4()
    prior = Subject(
        id=subject_id,
        name=SubjectName("Sample-XYZ"),
        status=SubjectStatus.MEASURED,
        mounted_on_asset_id=_ASSET_ID,
    )
    state = evolve(
        prior,
        SubjectDismounted(
            subject_id=subject_id,
            from_asset_id=_ASSET_ID,
            reason="x",
            occurred_at=_NOW,
            dismounted_by=_ACTOR,
        ),
    )
    assert state.name == SubjectName("Sample-XYZ")


@pytest.mark.unit
def test_fold_mount_dismount_remount_cycle_lands_at_second_asset() -> None:
    """End-to-end audit log: register, mount on A, dismount, mount
    on B. Final state is Mounted on B; the audit log records all
    four events for full chain-of-custody."""
    subject_id = uuid4()
    asset_a = UUID("01900000-0000-7000-8000-00000000a001")
    asset_b = UUID("01900000-0000-7000-8000-00000000b001")
    state = fold(
        [
            SubjectRegistered(
                subject_id=subject_id, name="Sample-A1", occurred_at=_NOW, registered_by=_ACTOR
            ),
            SubjectMounted(
                subject_id=subject_id,
                asset_id=asset_a,
                reason="alignment",
                occurred_at=_NOW,
                mounted_by=_ACTOR,
            ),
            SubjectDismounted(
                subject_id=subject_id,
                from_asset_id=asset_a,
                reason="moving",
                occurred_at=_NOW,
                dismounted_by=_ACTOR,
            ),
            SubjectMounted(
                subject_id=subject_id,
                asset_id=asset_b,
                reason="loaded for scan",
                occurred_at=_NOW,
                mounted_by=_ACTOR,
            ),
        ]
    )
    assert state is not None
    assert state.status is SubjectStatus.MOUNTED
    assert state.mounted_on_asset_id == asset_b
