"""Calibration evolver: genesis + append-calibration-revision folding.

Pins the append-only invariant (revisions accumulate; never overwrite)
and the deserialise-source round-trip via the evolver.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.calibration.aggregates.calibration import (
    AssertedSource,
    Calibration,
    CalibrationDefined,
    CalibrationRevisionAppended,
    CalibrationStatus,
    ComputedSource,
    MeasuredSource,
    evolve,
    fold,
)
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 18, 14, 30, 0, tzinfo=UTC)
_CAL_ID = UUID("01900000-0000-7000-8000-000000ca0001")
_SUB_ID = UUID("01900000-0000-7000-8000-000000ca0002")
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000ca0003"))
_PROC_ID = UUID("01900000-0000-7000-8000-000000ca0004")
_DATASET_ID = UUID("01900000-0000-7000-8000-000000ca0005")
_REV_ID_1 = UUID("01900000-0000-7000-8000-000000ca0006")
_REV_ID_2 = UUID("01900000-0000-7000-8000-000000ca0007")


def _defined() -> CalibrationDefined:
    return CalibrationDefined(
        calibration_id=_CAL_ID,
        target_id=_SUB_ID,
        quantity="rotation_center",
        operating_point={"energy": 25, "optics_config": "5x"},
        description=None,
        defined_by=_ACTOR_ID,
        occurred_at=_NOW,
    )


def _revision(
    *,
    revision_id: UUID,
    source_kind: str = "measured",
    supersedes: UUID | None = None,
    established_at: datetime = _NOW,
) -> CalibrationRevisionAppended:
    source_procedure_id = _PROC_ID if source_kind == "measured" else None
    source_dataset_id = _DATASET_ID if source_kind == "computed" else None
    asserted_by = _ACTOR_ID if source_kind == "asserted" else None
    return CalibrationRevisionAppended(
        revision_id=revision_id,
        calibration_id=_CAL_ID,
        value={"center": 1024.5},
        status=CalibrationStatus.PROVISIONAL,
        source_procedure_id=source_procedure_id,
        source_dataset_id=source_dataset_id,
        asserted_by=asserted_by,
        established_at=established_at,
        established_by=_ACTOR_ID,
        decided_by_decision_id=None,
        supersedes_revision_id=supersedes,
        occurred_at=established_at,
    )


@pytest.mark.unit
def test_evolve_genesis_creates_aggregate_with_empty_revisions() -> None:
    state = evolve(None, _defined())
    assert isinstance(state, Calibration)
    assert state.id == _CAL_ID
    assert state.target_id == _SUB_ID
    assert state.quantity == "rotation_center"
    assert state.operating_point == {"energy": 25, "optics_config": "5x"}
    assert state.revisions == ()
    assert state.defined_by == _ACTOR_ID
    assert state.defined_at == _NOW


@pytest.mark.unit
def test_evolve_revision_append_grows_revisions_tuple() -> None:
    state = evolve(None, _defined())
    state = evolve(state, _revision(revision_id=_REV_ID_1, established_at=_NOW))
    assert state.revisions[0].revision_id == _REV_ID_1
    assert state.revisions[0].status is CalibrationStatus.PROVISIONAL
    assert isinstance(state.revisions[0].source, MeasuredSource)
    assert len(state.revisions) == 1
    # Per Path C, `last_revised_at` lives on the projection, not state;
    # the projection-level test in test_projection_worker_postgres
    # asserts the projection column gets bumped. Here we only pin
    # state — that the new revision is appended with the right
    # `established_at` on the CalibrationRevision itself.
    assert state.revisions[0].established_at == _NOW


@pytest.mark.unit
def test_evolve_multiple_revisions_append_in_order() -> None:
    state = evolve(None, _defined())
    state = evolve(state, _revision(revision_id=_REV_ID_1, established_at=_NOW))
    state = evolve(
        state,
        _revision(
            revision_id=_REV_ID_2,
            source_kind="computed",
            supersedes=_REV_ID_1,
            established_at=_LATER,
        ),
    )
    assert len(state.revisions) == 2
    assert [r.revision_id for r in state.revisions] == [_REV_ID_1, _REV_ID_2]
    assert isinstance(state.revisions[1].source, ComputedSource)
    assert state.revisions[1].supersedes_revision_id == _REV_ID_1
    # Latest revision's established_at is the read-side surface for
    # last_revised_at; the projection mirrors that.
    assert state.revisions[1].established_at == _LATER


@pytest.mark.unit
def test_fold_replays_full_history() -> None:
    events = [
        _defined(),
        _revision(revision_id=_REV_ID_1, established_at=_NOW),
        _revision(
            revision_id=_REV_ID_2,
            source_kind="asserted",
            established_at=_LATER,
        ),
    ]
    state = fold(events)
    assert state is not None
    assert len(state.revisions) == 2
    assert isinstance(state.revisions[1].source, AssertedSource)


@pytest.mark.unit
def test_fold_empty_stream_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_evolve_revision_without_prior_state_raises() -> None:
    """Transition events applied to empty state raise via require_state."""
    with pytest.raises(ValueError, match="CalibrationRevisionAppended"):
        evolve(None, _revision(revision_id=_REV_ID_1))


@pytest.mark.unit
def test_fold_equals_left_fold_via_evolve() -> None:
    """Standard event-sourcing replay-determinism invariant: `fold(events)`
    equals `evolve(evolve(evolve(None, e1), e2), e3)`.

    Pins that `fold` is precisely the left-fold of `evolve` over the
    initial empty state — no hidden state accumulation or branching."""
    events = [
        _defined(),
        _revision(revision_id=_REV_ID_1, established_at=_NOW),
        _revision(
            revision_id=_REV_ID_2,
            source_kind="computed",
            supersedes=_REV_ID_1,
            established_at=_LATER,
        ),
    ]
    folded = fold(events)
    manual = evolve(evolve(evolve(None, events[0]), events[1]), events[2])
    assert folded == manual
