"""Property-based tests for `append_calibration_revision.decide` (Calibration BC).

Complements the example-based `test_append_calibration_revision_decider.py`
with universal claims across generated inputs. The decider is pure

    (state, command, now, new_revision_id, established_by)
        -> list[CalibrationRevisionAppended]

value is schema-validated, so a fixed valid value is used while ids /
actor / clock vary:

  - state=None always raises `CalibrationNotFoundError` carrying
    command.calibration_id.
  - A non-None state emits exactly one `CalibrationRevisionAppended`
    carrying revision_id=new_revision_id, calibration_id=state.id, the
    threaded status + source split + established_by, occurred_at=now, and
    a populated content_hash.
  - A `supersedes_revision_id` not present in state.revisions always
    raises `SupersedesRevisionNotFoundError`.
  - Pure: same inputs return equal events (content hash is deterministic).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.calibration.aggregates.calibration import (
    Calibration,
    CalibrationNotFoundError,
    CalibrationRevisionAppended,
    CalibrationStatus,
    MeasuredSource,
    SupersedesRevisionNotFoundError,
)
from cora.calibration.features import append_calibration_revision
from cora.calibration.features.append_calibration_revision import AppendCalibrationRevision
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


def _value() -> dict[str, Any]:
    return {"center": 1024.5}


def _state(*, calibration_id: UUID, defined_at: datetime, defined_by: ActorId) -> Calibration:
    return Calibration(
        id=calibration_id,
        target_id=calibration_id,
        quantity="rotation_center",
        operating_point={"energy": 25.0, "optics_config": "5x"},
        description=None,
        revisions=(),
        defined_at=defined_at,
        defined_by=defined_by,
    )


@pytest.mark.unit
@given(
    calibration_id=st.uuids(),
    proc_id=st.uuids(),
    now=aware_datetimes(),
    new_revision_id=st.uuids(),
    established_by_uuid=st.uuids(),
)
def test_append_with_none_state_always_raises_not_found(
    calibration_id: UUID,
    proc_id: UUID,
    now: datetime,
    new_revision_id: UUID,
    established_by_uuid: UUID,
) -> None:
    """Empty stream always raises `CalibrationNotFoundError` carrying command.calibration_id."""
    with pytest.raises(CalibrationNotFoundError) as exc:
        append_calibration_revision.decide(
            state=None,
            command=AppendCalibrationRevision(
                calibration_id=calibration_id,
                value=_value(),
                status=CalibrationStatus.PROVISIONAL,
                source=MeasuredSource(procedure_id=proc_id),
            ),
            now=now,
            new_revision_id=new_revision_id,
            established_by=ActorId(established_by_uuid),
        )
    assert exc.value.calibration_id == calibration_id


@pytest.mark.unit
@given(
    calibration_id=st.uuids(),
    proc_id=st.uuids(),
    now=aware_datetimes(),
    new_revision_id=st.uuids(),
    established_by_uuid=st.uuids(),
)
def test_append_emits_single_event_with_injected_fields(
    calibration_id: UUID,
    proc_id: UUID,
    now: datetime,
    new_revision_id: UUID,
    established_by_uuid: UUID,
) -> None:
    """A non-None state emits one CalibrationRevisionAppended with the threaded fields."""
    established_by = ActorId(established_by_uuid)
    state = _state(calibration_id=calibration_id, defined_at=now, defined_by=established_by)
    events = append_calibration_revision.decide(
        state=state,
        command=AppendCalibrationRevision(
            calibration_id=calibration_id,
            value=_value(),
            status=CalibrationStatus.PROVISIONAL,
            source=MeasuredSource(procedure_id=proc_id),
        ),
        now=now,
        new_revision_id=new_revision_id,
        established_by=established_by,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, CalibrationRevisionAppended)
    assert event.revision_id == new_revision_id
    assert event.calibration_id == calibration_id
    assert event.status is CalibrationStatus.PROVISIONAL
    assert event.source_procedure_id == proc_id
    assert event.source_dataset_id is None
    assert event.asserted_by is None
    assert event.established_by == established_by
    assert event.occurred_at == now
    assert event.content_hash is not None


@pytest.mark.unit
@given(
    calibration_id=st.uuids(),
    proc_id=st.uuids(),
    supersedes_id=st.uuids(),
    now=aware_datetimes(),
    new_revision_id=st.uuids(),
    established_by_uuid=st.uuids(),
)
def test_append_unknown_supersedes_always_raises_not_found(
    calibration_id: UUID,
    proc_id: UUID,
    supersedes_id: UUID,
    now: datetime,
    new_revision_id: UUID,
    established_by_uuid: UUID,
) -> None:
    """A supersedes_revision_id absent from state.revisions (empty here) raises."""
    established_by = ActorId(established_by_uuid)
    state = _state(calibration_id=calibration_id, defined_at=now, defined_by=established_by)
    with pytest.raises(SupersedesRevisionNotFoundError):
        append_calibration_revision.decide(
            state=state,
            command=AppendCalibrationRevision(
                calibration_id=calibration_id,
                value=_value(),
                status=CalibrationStatus.PROVISIONAL,
                source=MeasuredSource(procedure_id=proc_id),
                supersedes_revision_id=supersedes_id,
            ),
            now=now,
            new_revision_id=new_revision_id,
            established_by=established_by,
        )


@pytest.mark.unit
@given(
    calibration_id=st.uuids(),
    proc_id=st.uuids(),
    now=aware_datetimes(),
    new_revision_id=st.uuids(),
    established_by_uuid=st.uuids(),
)
def test_append_is_pure_same_input_same_output(
    calibration_id: UUID,
    proc_id: UUID,
    now: datetime,
    new_revision_id: UUID,
    established_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (deterministic content hash)."""
    established_by = ActorId(established_by_uuid)
    state = _state(calibration_id=calibration_id, defined_at=now, defined_by=established_by)
    command = AppendCalibrationRevision(
        calibration_id=calibration_id,
        value=_value(),
        status=CalibrationStatus.PROVISIONAL,
        source=MeasuredSource(procedure_id=proc_id),
    )
    first = append_calibration_revision.decide(
        state=state,
        command=command,
        now=now,
        new_revision_id=new_revision_id,
        established_by=established_by,
    )
    second = append_calibration_revision.decide(
        state=state,
        command=command,
        now=now,
        new_revision_id=new_revision_id,
        established_by=established_by,
    )
    assert first == second
