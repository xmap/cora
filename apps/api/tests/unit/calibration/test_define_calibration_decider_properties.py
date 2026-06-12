"""Property-based tests for `define_calibration.decide` (Calibration BC).

Complements the example-based `test_define_calibration_decider.py` with
universal claims across generated inputs. The genesis decider is pure

    (state, command, now, new_id, defined_by) -> list[CalibrationDefined]

operating_point is schema-validated, so a fixed valid (quantity,
operating_point) pair is used while ids / actor / clock vary:

  - Any non-None state always raises `CalibrationAlreadyExistsError`
    carrying state.id (idempotency-as-error), regardless of command.
  - On the happy path the single `CalibrationDefined` carries the
    injected/passthrough fields: calibration_id=new_id, target_id,
    quantity, operating_point, description=None, defined_by,
    occurred_at=now.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.calibration.aggregates.calibration import (
    Calibration,
    CalibrationAlreadyExistsError,
    CalibrationDefined,
)
from cora.calibration.features import define_calibration
from cora.calibration.features.define_calibration import DefineCalibration
from cora.calibration.quantities import CalibrationQuantity
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


def _op_point() -> dict[str, Any]:
    return {"energy": 25.0, "optics_config": "5x"}


def _existing(*, calibration_id: UUID, defined_at: datetime, defined_by: ActorId) -> Calibration:
    return Calibration(
        id=calibration_id,
        target_id=calibration_id,
        quantity="rotation_center",
        operating_point=_op_point(),
        description=None,
        revisions=(),
        defined_at=defined_at,
        defined_by=defined_by,
    )


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    target_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
    defined_by_uuid=st.uuids(),
)
def test_define_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    target_id: UUID,
    now: datetime,
    new_id: UUID,
    defined_by_uuid: UUID,
) -> None:
    """Any non-None state raises CalibrationAlreadyExistsError carrying state.id."""
    existing = _existing(
        calibration_id=existing_id, defined_at=now, defined_by=ActorId(defined_by_uuid)
    )
    with pytest.raises(CalibrationAlreadyExistsError) as exc:
        define_calibration.decide(
            state=existing,
            command=DefineCalibration(
                target_id=target_id,
                quantity=CalibrationQuantity.ROTATION_CENTER,
                operating_point=_op_point(),
            ),
            now=now,
            new_id=new_id,
            defined_by=ActorId(defined_by_uuid),
        )
    assert exc.value.calibration_id == existing_id


@pytest.mark.unit
@given(
    target_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
    defined_by_uuid=st.uuids(),
)
def test_define_emits_single_event_with_injected_fields(
    target_id: UUID,
    now: datetime,
    new_id: UUID,
    defined_by_uuid: UUID,
) -> None:
    """Empty stream + valid command emits one CalibrationDefined with injected fields."""
    defined_by = ActorId(defined_by_uuid)
    events = define_calibration.decide(
        state=None,
        command=DefineCalibration(
            target_id=target_id,
            quantity=CalibrationQuantity.ROTATION_CENTER,
            operating_point=_op_point(),
        ),
        now=now,
        new_id=new_id,
        defined_by=defined_by,
    )
    assert events == [
        CalibrationDefined(
            calibration_id=new_id,
            target_id=target_id,
            quantity="rotation_center",
            operating_point=_op_point(),
            description=None,
            defined_by=defined_by,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    target_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
    defined_by_uuid=st.uuids(),
)
def test_define_is_pure_same_input_same_output(
    target_id: UUID,
    now: datetime,
    new_id: UUID,
    defined_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock/id leakage)."""
    command = DefineCalibration(
        target_id=target_id,
        quantity=CalibrationQuantity.ROTATION_CENTER,
        operating_point=_op_point(),
    )
    defined_by = ActorId(defined_by_uuid)
    first = define_calibration.decide(
        state=None, command=command, now=now, new_id=new_id, defined_by=defined_by
    )
    second = define_calibration.decide(
        state=None, command=command, now=now, new_id=new_id, defined_by=defined_by
    )
    assert first == second
