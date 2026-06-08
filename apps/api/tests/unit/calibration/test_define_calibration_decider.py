"""Unit tests for the `define_calibration` slice's pure decider.

Pins the genesis-collision guard + STRICT operating_point validation +
description coerce/trim behavior. Slice-level integration (handler →
event-store → projection) is covered by the integration suite.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.calibration.aggregates.calibration import (
    Calibration,
    CalibrationAlreadyExistsError,
    InvalidCalibrationDescriptionError,
    InvalidOperatingPointError,
)
from cora.calibration.features import define_calibration
from cora.calibration.features.define_calibration import DefineCalibration
from cora.calibration.quantities import CalibrationQuantity
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000ca1001"))
_SUBSYSTEM_ID = UUID("01900000-0000-7000-8000-000000ca1002")
_NEW_ID = UUID("01900000-0000-7000-8000-000000ca1003")


def _op_point() -> dict[str, object]:
    return {"energy": 25.0, "optics_config": "5x"}


def _existing_state() -> Calibration:
    return Calibration(
        id=_NEW_ID,
        target_id=_SUBSYSTEM_ID,
        quantity="rotation_center",
        operating_point=_op_point(),
        description=None,
        revisions=(),
        defined_at=_NOW,
        defined_by=_PRINCIPAL_ID,
    )


@pytest.mark.unit
def test_decide_emits_genesis_event_for_valid_command() -> None:
    cmd = DefineCalibration(
        target_id=_SUBSYSTEM_ID,
        quantity=CalibrationQuantity.ROTATION_CENTER,
        operating_point=_op_point(),
    )
    events = define_calibration.decide(
        state=None,
        command=cmd,
        now=_NOW,
        new_id=_NEW_ID,
        defined_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert event.calibration_id == _NEW_ID
    assert event.target_id == _SUBSYSTEM_ID
    assert event.quantity == "rotation_center"
    assert event.operating_point == _op_point()
    assert event.description is None
    assert event.defined_by == _PRINCIPAL_ID


@pytest.mark.unit
def test_decide_rejects_when_state_already_exists() -> None:
    cmd = DefineCalibration(
        target_id=_SUBSYSTEM_ID,
        quantity=CalibrationQuantity.ROTATION_CENTER,
        operating_point=_op_point(),
    )
    with pytest.raises(CalibrationAlreadyExistsError):
        define_calibration.decide(
            state=_existing_state(),
            command=cmd,
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_decide_rejects_missing_required_operating_point_key() -> None:
    """rotation_center requires energy + optics_config."""
    cmd = DefineCalibration(
        target_id=_SUBSYSTEM_ID,
        quantity=CalibrationQuantity.ROTATION_CENTER,
        operating_point={"energy": 25.0},  # missing optics_config
    )
    with pytest.raises(InvalidOperatingPointError):
        define_calibration.decide(
            state=None,
            command=cmd,
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_decide_rejects_empty_operating_point() -> None:
    """Empty operating_point with required-key schema rejects."""
    cmd = DefineCalibration(
        target_id=_SUBSYSTEM_ID,
        quantity=CalibrationQuantity.ROTATION_CENTER,
        operating_point={},
    )
    with pytest.raises(InvalidOperatingPointError):
        define_calibration.decide(
            state=None,
            command=cmd,
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_decide_rejects_additional_operating_point_property() -> None:
    cmd = DefineCalibration(
        target_id=_SUBSYSTEM_ID,
        quantity=CalibrationQuantity.ROTATION_CENTER,
        operating_point={
            "energy": 25.0,
            "optics_config": "5x",
            "unknown_field": "drift",
        },
    )
    with pytest.raises(InvalidOperatingPointError):
        define_calibration.decide(
            state=None,
            command=cmd,
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_decide_coerces_empty_description_to_none() -> None:
    cmd = DefineCalibration(
        target_id=_SUBSYSTEM_ID,
        quantity=CalibrationQuantity.ROTATION_CENTER,
        operating_point=_op_point(),
        description="   ",
    )
    events = define_calibration.decide(
        state=None,
        command=cmd,
        now=_NOW,
        new_id=_NEW_ID,
        defined_by=_PRINCIPAL_ID,
    )
    assert events[0].description is None


@pytest.mark.unit
def test_decide_trims_description() -> None:
    cmd = DefineCalibration(
        target_id=_SUBSYSTEM_ID,
        quantity=CalibrationQuantity.ROTATION_CENTER,
        operating_point=_op_point(),
        description="  vessel-A bakeout pre-scan  ",
    )
    events = define_calibration.decide(
        state=None,
        command=cmd,
        now=_NOW,
        new_id=_NEW_ID,
        defined_by=_PRINCIPAL_ID,
    )
    assert events[0].description == "vessel-A bakeout pre-scan"


@pytest.mark.unit
def test_decide_rejects_overlong_description() -> None:
    cmd = DefineCalibration(
        target_id=_SUBSYSTEM_ID,
        quantity=CalibrationQuantity.ROTATION_CENTER,
        operating_point=_op_point(),
        description="x" * 2001,
    )
    with pytest.raises(InvalidCalibrationDescriptionError):
        define_calibration.decide(
            state=None,
            command=cmd,
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    cmd = DefineCalibration(
        target_id=_SUBSYSTEM_ID,
        quantity=CalibrationQuantity.ROTATION_CENTER,
        operating_point=_op_point(),
    )
    first = define_calibration.decide(
        state=None,
        command=cmd,
        now=_NOW,
        new_id=_NEW_ID,
        defined_by=_PRINCIPAL_ID,
    )
    second = define_calibration.decide(
        state=None,
        command=cmd,
        now=_NOW,
        new_id=_NEW_ID,
        defined_by=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_decide_is_immune_to_uuid4_stub() -> None:
    """Sanity: handler-injected new_id is used verbatim; decider doesn't
    call uuid4() itself."""
    new_id = uuid4()
    events = define_calibration.decide(
        state=None,
        command=DefineCalibration(
            target_id=_SUBSYSTEM_ID,
            quantity=CalibrationQuantity.ROTATION_CENTER,
            operating_point=_op_point(),
        ),
        now=_NOW,
        new_id=new_id,
        defined_by=_PRINCIPAL_ID,
    )
    assert events[0].calibration_id == new_id
