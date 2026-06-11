"""Unit tests for Acquisition state: status enum, errors, carrier-shape VOs.

Pins the single-value AcquisitionStatus, the don't-hoist error
family, and the shape-only settings / evidence validators.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.acquisition import (
    Acquisition,
    AcquisitionAlreadyExistsError,
    AcquisitionAssetNotFoundError,
    AcquisitionCannotRecordWithoutCapturingError,
    AcquisitionRunNotFoundError,
    AcquisitionStatus,
    InvalidAcquisitionEvidenceError,
    InvalidAcquisitionSettingsError,
    validate_evidence,
    validate_settings,
)
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
_RECORDED_BY = ActorId(UUID("01900000-0000-7000-8000-0000000000b1"))


@pytest.mark.unit
def test_acquisition_status_ships_single_value() -> None:
    """AcquisitionStatus is a one-member StrEnum (terminal at genesis)."""
    assert list(AcquisitionStatus) == [AcquisitionStatus.RECORDED]
    assert AcquisitionStatus.RECORDED.value == "Recorded"


@pytest.mark.unit
def test_acquisition_status_value_is_pascal_case() -> None:
    """The string value is PascalCase (BC-status-vocabulary fitness)."""
    assert AcquisitionStatus.RECORDED.value[0].isupper()
    assert "_" not in AcquisitionStatus.RECORDED.value


@pytest.mark.unit
def test_acquisition_state_defaults_to_recorded() -> None:
    acq = Acquisition(
        id=uuid4(),
        dataset_id=uuid4(),
        producing_asset_id=uuid4(),
        producing_run_id=None,
        captured_at=_NOW,
        settings={},
        evidence={},
        recorded_at=_NOW,
        recorded_by=_RECORDED_BY,
    )
    assert acq.status is AcquisitionStatus.RECORDED


@pytest.mark.unit
def test_validate_settings_accepts_primitive_leaves() -> None:
    value = {"exposure_ms": 200, "binning": "2x2", "dark": True, "gain": 1.5, "note": None}
    assert validate_settings(value) is value


@pytest.mark.unit
def test_validate_settings_accepts_nested_containers() -> None:
    value = {"roi": {"x": 0, "y": 0, "w": 1024, "h": 1024}, "flats": [1, 2, 3]}
    assert validate_settings(value) is value


@pytest.mark.unit
def test_validate_settings_accepts_empty_dict() -> None:
    assert validate_settings({}) == {}


@pytest.mark.unit
def test_validate_settings_rejects_non_dict() -> None:
    with pytest.raises(InvalidAcquisitionSettingsError, match="must be a dict"):
        validate_settings([1, 2, 3])  # type: ignore[arg-type]


@pytest.mark.unit
def test_validate_settings_rejects_non_primitive_leaf() -> None:
    with pytest.raises(InvalidAcquisitionSettingsError, match="non-primitive leaf"):
        validate_settings({"bad": object()})


@pytest.mark.unit
def test_validate_settings_rejects_non_string_key() -> None:
    with pytest.raises(InvalidAcquisitionSettingsError, match="keys must be strings"):
        validate_settings({"ok": {1: "x"}})  # type: ignore[dict-item]


@pytest.mark.unit
def test_validate_evidence_accepts_primitive_leaves() -> None:
    value = {"checksum": "abc", "verified": True}
    assert validate_evidence(value) is value


@pytest.mark.unit
def test_validate_evidence_rejects_non_dict() -> None:
    with pytest.raises(InvalidAcquisitionEvidenceError, match="must be a dict"):
        validate_evidence("nope")  # type: ignore[arg-type]


@pytest.mark.unit
def test_validate_evidence_rejects_non_primitive_leaf() -> None:
    with pytest.raises(InvalidAcquisitionEvidenceError, match="non-primitive leaf"):
        validate_evidence({"bad": object()})


@pytest.mark.unit
def test_acquisition_already_exists_error_carries_id() -> None:
    acq_id = uuid4()
    err = AcquisitionAlreadyExistsError(acq_id)
    assert err.acquisition_id == acq_id
    assert str(acq_id) in str(err)


@pytest.mark.unit
def test_acquisition_asset_not_found_error_carries_id() -> None:
    asset_id = uuid4()
    err = AcquisitionAssetNotFoundError(asset_id)
    assert err.asset_id == asset_id
    assert str(asset_id) in str(err)


@pytest.mark.unit
def test_acquisition_run_not_found_error_carries_id() -> None:
    run_id = uuid4()
    err = AcquisitionRunNotFoundError(run_id)
    assert err.run_id == run_id
    assert str(run_id) in str(err)


@pytest.mark.unit
def test_acquisition_asset_missing_capturing_affordance_error_carries_id() -> None:
    asset_id = uuid4()
    err = AcquisitionCannotRecordWithoutCapturingError(asset_id)
    assert err.asset_id == asset_id
    assert "Capturing" in str(err)
