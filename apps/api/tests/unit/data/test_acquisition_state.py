"""Unit tests for Acquisition state: status enum, errors, carrier-shape VOs.

Pins the single-value AcquisitionStatus, the don't-hoist error
family, the shape-only settings validator, and evidence's
AcquisitionEvidence validator/builder.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.acquisition import (
    Acquisition,
    AcquisitionAlreadyExistsError,
    AcquisitionAssetNotFoundError,
    AcquisitionCannotRecordWithoutCapturingError,
    AcquisitionEvidence,
    AcquisitionRunNotFoundError,
    AcquisitionStatus,
    CapturedAtSource,
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
        evidence=AcquisitionEvidence(),
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
def test_validate_evidence_accepts_empty_dict() -> None:
    """No evidence supplied: every AcquisitionEvidence field is None."""
    assert validate_evidence({}) == AcquisitionEvidence()


@pytest.mark.unit
def test_validate_evidence_accepts_known_shape() -> None:
    value = {
        "reader_kind": "DataExchange",
        "checksum_computer_kind": "PosixChecksum",
        "captured_at_source": "end_date",
        "captured_at_raw": "2026-06-10T09:00:00",
        "projection_count": 1501,
        "flat_count": 40,
        "dark_count": 20,
        "invalid_count": 0,
        "commanded_projection_count": 1501,
        "commanded_flat_count": 40,
        "commanded_dark_count": 20,
        "dropped_frame_count": 0,
        "projection_angle_count": 1501,
        "projection_angle_first": 0.0,
        "projection_angle_last": 180.0,
    }
    evidence = validate_evidence(value)
    assert evidence.reader_kind == "DataExchange"
    assert evidence.captured_at_source is CapturedAtSource.END_DATE
    assert evidence.projection_count == 1501
    assert evidence.projection_angle_first == 0.0


@pytest.mark.unit
def test_validate_evidence_accepts_sparse_subset() -> None:
    """No key is required; a caller may report only what it knows."""
    evidence = validate_evidence({"projection_count": 5})
    assert evidence == AcquisitionEvidence(projection_count=5)


@pytest.mark.unit
def test_validate_evidence_rejects_non_dict() -> None:
    with pytest.raises(InvalidAcquisitionEvidenceError, match="must be a dict"):
        validate_evidence("nope")  # type: ignore[arg-type]


@pytest.mark.unit
def test_validate_evidence_rejects_unknown_key() -> None:
    with pytest.raises(InvalidAcquisitionEvidenceError, match="unknown key"):
        validate_evidence({"frames": 1801})


@pytest.mark.unit
def test_validate_evidence_rejects_wrong_typed_value() -> None:
    with pytest.raises(InvalidAcquisitionEvidenceError, match="projection_count"):
        validate_evidence({"projection_count": "lots"})


@pytest.mark.unit
def test_validate_evidence_rejects_bool_for_int_field() -> None:
    """A Python bool is an int subclass, but JSON's integer and boolean
    are not the same type: a boolean here is a shape violation, not a 0/1."""
    with pytest.raises(InvalidAcquisitionEvidenceError, match="projection_count"):
        validate_evidence({"projection_count": True})


@pytest.mark.unit
def test_validate_evidence_rejects_unknown_captured_at_source() -> None:
    with pytest.raises(InvalidAcquisitionEvidenceError, match="captured_at_source"):
        validate_evidence({"captured_at_source": "acquisition_time"})


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


@pytest.mark.unit
def test_acquisition_recorded_evidence_disposition_pins_the_disclosure_split() -> None:
    """Pins F6's whole point for Acquisition: the actual keep/drop split
    the generator produces for evidence's fields, independent of the
    generator itself (test_record_dispositions_drift.py only proves the
    committed table equals a FRESH run of the SAME generator, so a
    classification bug that is wrong-but-self-consistent would still
    pass it). A future change that regresses any of these back to
    drop:opaque, or promotes an open-vocabulary string to keep:, should
    fail here first."""
    from cora.infrastructure.record_export._dispositions import DISPOSITIONS

    assert DISPOSITIONS["AcquisitionRecorded"]["evidence"] == {
        "reader_kind": "drop:text",
        "checksum_computer_kind": "drop:text",
        "captured_at_source": "keep:enum:CapturedAtSource",
        "captured_at_raw": "drop:text",
        "projection_count": "keep:number",
        "flat_count": "keep:number",
        "dark_count": "keep:number",
        "invalid_count": "keep:number",
        "commanded_projection_count": "keep:number",
        "commanded_flat_count": "keep:number",
        "commanded_dark_count": "keep:number",
        "dropped_frame_count": "keep:number",
        "projection_angle_count": "keep:number",
        "projection_angle_first": "keep:number",
        "projection_angle_last": "keep:number",
    }
