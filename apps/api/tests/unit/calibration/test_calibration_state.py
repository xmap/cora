"""State-layer gap tests for the Calibration aggregate.

Addresses the gate-review test gaps:
  - `CalibrationDescription` VO trim + bound checks (gate review P1 #1)
  - 9 error class instantiation pins (gate review P1 #2)
  - `CalibrationStatus` + `CalibrationQuantity` enum value-locks
    (gate review P1 #3)
"""

from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.calibration.aggregates.calibration import (
    CALIBRATION_DESCRIPTION_MAX_LENGTH,
    CalibrationAlreadyExistsError,
    CalibrationDescription,
    CalibrationIdentityAlreadyExistsError,
    CalibrationNotFoundError,
    CalibrationStatus,
    InvalidCalibrationDescriptionError,
    InvalidCalibrationQuantityError,
    InvalidCalibrationSourceError,
    InvalidCalibrationValueError,
    InvalidOperatingPointError,
    SupersedesRevisionNotFoundError,
)
from cora.calibration.quantities import CalibrationQuantity

# ---------- CalibrationDescription VO ----------


@pytest.mark.unit
def test_calibration_description_trims_surrounding_whitespace() -> None:
    desc = CalibrationDescription("  rotation-axis bakeout pre-scan  ")
    assert desc.value == "rotation-axis bakeout pre-scan"


@pytest.mark.unit
def test_calibration_description_accepts_max_length() -> None:
    desc = CalibrationDescription("x" * CALIBRATION_DESCRIPTION_MAX_LENGTH)
    assert len(desc.value) == CALIBRATION_DESCRIPTION_MAX_LENGTH


@pytest.mark.unit
def test_calibration_description_rejects_overlong_value() -> None:
    with pytest.raises(InvalidCalibrationDescriptionError) as excinfo:
        CalibrationDescription("x" * (CALIBRATION_DESCRIPTION_MAX_LENGTH + 1))
    # The error carries the raw value for log diagnostics.
    assert excinfo.value.value.startswith("x")


@pytest.mark.unit
def test_calibration_description_vo_is_frozen() -> None:
    """frozen=True dataclass; assignment raises FrozenInstanceError."""
    from dataclasses import FrozenInstanceError

    desc = CalibrationDescription("ok")
    with pytest.raises(FrozenInstanceError):
        desc.value = "other"  # type: ignore[misc]  # pyright: ignore[reportAttributeAccessIssue]


# ---------- Enum value-locks ----------


@pytest.mark.unit
def test_calibration_status_value_set_is_locked() -> None:
    """Confidence ladder is locked at 2 tiers; tier expansion is a future option."""
    assert {s.value for s in CalibrationStatus} == {"Provisional", "Verified"}
    assert len(list(CalibrationStatus)) == 2


@pytest.mark.unit
def test_calibration_quantity_value_set_is_locked() -> None:
    """Pilot quantities. Adding requires PR + new schema module."""
    assert {q.value for q in CalibrationQuantity} == {
        "rotation_center",
        "detector_pixel_size",
        "magnification",
        "effective_thickness",
        "energy_position_curve",
    }
    assert len(list(CalibrationQuantity)) == 5


# ---------- Error-class instantiation + attribute pins ----------


@pytest.mark.unit
def test_calibration_not_found_error_carries_calibration_id() -> None:
    cal_id = uuid4()
    err = CalibrationNotFoundError(cal_id)
    assert err.calibration_id == cal_id
    assert str(cal_id) in str(err)


@pytest.mark.unit
def test_calibration_already_exists_error_carries_calibration_id() -> None:
    cal_id = uuid4()
    err = CalibrationAlreadyExistsError(cal_id)
    assert err.calibration_id == cal_id
    assert str(cal_id) in str(err)


@pytest.mark.unit
def test_invalid_calibration_quantity_error_carries_value() -> None:
    err = InvalidCalibrationQuantityError("rotation_centre")
    assert err.value == "rotation_centre"
    assert "rotation_centre" in str(err)


@pytest.mark.unit
def test_invalid_operating_point_error_carries_message() -> None:
    err = InvalidOperatingPointError("missing required key energy")
    assert "energy" in err.message


@pytest.mark.unit
def test_invalid_calibration_value_error_carries_message() -> None:
    err = InvalidCalibrationValueError("center must be number")
    assert "center" in err.message


@pytest.mark.unit
def test_invalid_calibration_source_error_carries_message() -> None:
    err = InvalidCalibrationSourceError("two non-null arc fields")
    assert "non-null" in err.message


@pytest.mark.unit
def test_supersedes_revision_not_found_error_carries_both_ids() -> None:
    cal_id = uuid4()
    rev_id = uuid4()
    err = SupersedesRevisionNotFoundError(cal_id, rev_id)
    assert err.calibration_id == cal_id
    assert err.supersedes_revision_id == rev_id
    assert str(rev_id) in str(err)


@pytest.mark.unit
def test_duplicate_calibration_identity_error_carries_identity_tuple() -> None:
    asset_id = uuid4()
    op_point: dict[str, Any] = {"energy": 25.0, "optics_config": "5x"}
    err = CalibrationIdentityAlreadyExistsError(
        target_id=asset_id,
        quantity="rotation_center",
        operating_point=op_point,
    )
    assert err.target_id == asset_id
    assert err.quantity == "rotation_center"
    assert err.operating_point == op_point


@pytest.mark.unit
def test_invalid_calibration_description_error_truncates_in_message_via_value_attr() -> None:
    """The full value rides on `.value` for log diagnostics; the message
    itself contains the repr (so log filters can decide to redact)."""
    long_value = "x" * 5000
    err = InvalidCalibrationDescriptionError(long_value)
    assert err.value == long_value
    # Message exists and references the bound for operator clarity.
    assert "0-" in str(err)


# ---------- Identity assignment (genesis) ----------


@pytest.mark.unit
def test_calibration_uses_canonical_str_for_quantity() -> None:
    """CalibrationQuantity is StrEnum; its value-string is what events
    carry on the wire and what state.quantity holds."""
    q = CalibrationQuantity.ROTATION_CENTER
    assert q.value == "rotation_center"
    assert str(q) == "rotation_center"


@pytest.mark.unit
def test_calibration_status_enum_string_round_trips() -> None:
    """Wire string -> enum via constructor; required by the evolver
    when reconstructing a CalibrationRevision from the event payload."""
    assert CalibrationStatus("Provisional") is CalibrationStatus.PROVISIONAL
    assert CalibrationStatus("Verified") is CalibrationStatus.VERIFIED


@pytest.mark.unit
def test_calibration_status_constructor_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        CalibrationStatus("Refined")  # 3rd tier deferred to phase 12f


# Helper to silence the unused-import linter when pyright fires.
_ = UUID
