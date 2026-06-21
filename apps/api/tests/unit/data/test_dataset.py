"""Unit tests for Dataset aggregate state, value objects, and domain errors.

Mirrors `test_subject.py` shape: VO trim/length/format checks,
status-enum exhaustiveness, error-class shape (carries the right
fields, str(exc) names the right things).
"""

from uuid import uuid4

import pytest

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DATASET_CONFORMS_TO_ENTRY_MAX_LENGTH,
    DATASET_DERIVED_FROM_MAX_ENTRIES,
    DATASET_MEDIA_TYPE_MAX_LENGTH,
    DATASET_NAME_MAX_LENGTH,
    DATASET_URI_MAX_LENGTH,
    DATASET_USED_CALIBRATIONS_MAX_ENTRIES,
    Dataset,
    DatasetAlreadyExistsError,
    DatasetChecksum,
    DatasetEncoding,
    DatasetName,
    DatasetNotFoundError,
    DatasetStatus,
    DatasetUri,
    DerivedFromDatasetsNotFoundError,
    InvalidDatasetByteSizeError,
    InvalidDatasetChecksumError,
    InvalidDatasetEncodingError,
    InvalidDatasetNameError,
    InvalidDatasetUriError,
    InvalidDerivedFromError,
    InvalidUsedCalibrationsError,
    LinkedSubjectNotFoundError,
    ProducingRunNotFoundError,
    validate_byte_size,
    validate_derived_from,
    validate_used_calibration_ids,
)

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH


# ---------- DatasetName VO ----------


@pytest.mark.unit
def test_dataset_name_accepts_normal_string() -> None:
    name = DatasetName("32-ID FlyScan reconstruction")
    assert name.value == "32-ID FlyScan reconstruction"


@pytest.mark.unit
def test_dataset_name_trims_whitespace() -> None:
    name = DatasetName("  32-ID FlyScan  ")
    assert name.value == "32-ID FlyScan"


@pytest.mark.unit
def test_dataset_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidDatasetNameError):
        DatasetName("")


@pytest.mark.unit
def test_dataset_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidDatasetNameError):
        DatasetName("   \t\n   ")


@pytest.mark.unit
def test_dataset_name_rejects_too_long() -> None:
    with pytest.raises(InvalidDatasetNameError):
        DatasetName("a" * (DATASET_NAME_MAX_LENGTH + 1))


@pytest.mark.unit
def test_dataset_name_accepts_max_length() -> None:
    name = DatasetName("a" * DATASET_NAME_MAX_LENGTH)
    assert len(name.value) == DATASET_NAME_MAX_LENGTH


# ---------- DatasetUri VO ----------


@pytest.mark.unit
@pytest.mark.parametrize(
    "uri",
    [
        "s3://bucket/key",
        "https://example.com/dataset/123",
        "file:///path/to/file.h5",
        "globus://endpoint-uuid/path",
        "posix:///mnt/data/file.h5",
    ],
)
def test_dataset_uri_accepts_common_schemes(uri: str) -> None:
    parsed = DatasetUri(uri)
    assert parsed.value == uri


@pytest.mark.unit
def test_dataset_uri_trims_whitespace() -> None:
    uri = DatasetUri("  s3://bucket/key  ")
    assert uri.value == "s3://bucket/key"


@pytest.mark.unit
def test_dataset_uri_rejects_empty() -> None:
    with pytest.raises(InvalidDatasetUriError) as exc_info:
        DatasetUri("")
    assert "empty" in str(exc_info.value).lower()


@pytest.mark.unit
def test_dataset_uri_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidDatasetUriError):
        DatasetUri("   ")


@pytest.mark.unit
def test_dataset_uri_rejects_missing_scheme() -> None:
    with pytest.raises(InvalidDatasetUriError) as exc_info:
        DatasetUri("just-a-path")
    assert "scheme" in str(exc_info.value).lower()


@pytest.mark.unit
def test_dataset_uri_rejects_too_long() -> None:
    with pytest.raises(InvalidDatasetUriError):
        DatasetUri("s3://" + "a" * DATASET_URI_MAX_LENGTH)


@pytest.mark.unit
@pytest.mark.parametrize(
    "uri",
    [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
        "about:blank",
        "view-source:https://example.com",
        # Case-insensitive: scheme.lower() check.
        "JavaScript:alert(1)",
        "DATA:text/plain;base64,SGVsbG8=",
    ],
)
def test_dataset_uri_rejects_known_xss_schemes(uri: str) -> None:
    """Defensive blocklist: known-XSS URI schemes are never legit
    Dataset URIs and would be a free phishing vector if rendered as
    a clickable link by a downstream UI."""
    with pytest.raises(InvalidDatasetUriError) as exc_info:
        DatasetUri(uri)
    assert "blocked" in str(exc_info.value).lower()


@pytest.mark.unit
@pytest.mark.parametrize(
    "uri",
    [
        # Common storage backends a facility might use; none are blocked.
        "s3://bucket/key",
        "gs://bucket/object",
        "azure://account/container/blob",
        "ipfs://Qm.../file.h5",
        "sftp://server/path",
        "ftp://server/path",
        "file:///local/path/data.h5",
        "globus://endpoint/path",
        "https://example.com/dataset/123",
    ],
)
def test_dataset_uri_accepts_real_storage_schemes(uri: str) -> None:
    """The blocklist is defensive, not a closed allowlist; common
    storage / transport schemes pass through."""
    parsed = DatasetUri(uri)
    assert parsed.value == uri


# ---------- DatasetChecksum VO ----------


@pytest.mark.unit
def test_dataset_checksum_accepts_canonical_sha256() -> None:
    checksum = DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256)
    assert checksum.algorithm == "sha256"
    assert checksum.value == _GOOD_SHA256


@pytest.mark.unit
def test_dataset_checksum_accepts_sha256_tree() -> None:
    checksum = DatasetChecksum(algorithm="sha256-tree", value=_GOOD_SHA256)
    assert checksum.algorithm == "sha256-tree"
    assert checksum.value == _GOOD_SHA256


@pytest.mark.unit
def test_dataset_checksum_rejects_unsupported_algorithm() -> None:
    with pytest.raises(InvalidDatasetChecksumError) as exc_info:
        DatasetChecksum(algorithm="md5", value="d41d8cd98f00b204e9800998ecf8427e")
    assert "sha256" in str(exc_info.value)


@pytest.mark.unit
def test_dataset_checksum_rejects_wrong_hex_length() -> None:
    with pytest.raises(InvalidDatasetChecksumError):
        DatasetChecksum(algorithm="sha256", value="a" * 63)


@pytest.mark.unit
def test_dataset_checksum_rejects_uppercase_hex() -> None:
    with pytest.raises(InvalidDatasetChecksumError):
        DatasetChecksum(algorithm="sha256", value="A" * 64)


@pytest.mark.unit
def test_dataset_checksum_rejects_non_hex_chars() -> None:
    with pytest.raises(InvalidDatasetChecksumError):
        DatasetChecksum(algorithm="sha256", value="g" * 64)


# ---------- DatasetEncoding VO ----------


@pytest.mark.unit
def test_dataset_encoding_accepts_media_type_only() -> None:
    fmt = DatasetEncoding(media_type="application/x-hdf5")
    assert fmt.media_type == "application/x-hdf5"
    assert fmt.conforms_to == frozenset()


@pytest.mark.unit
def test_dataset_encoding_accepts_conforms_to() -> None:
    fmt = DatasetEncoding(
        media_type="application/x-hdf5",
        conforms_to=frozenset({"https://manual.nexusformat.org/"}),
    )
    assert fmt.conforms_to == frozenset({"https://manual.nexusformat.org/"})


@pytest.mark.unit
def test_dataset_encoding_trims_media_type_and_conforms_to_entries() -> None:
    fmt = DatasetEncoding(
        media_type="  application/x-hdf5  ",
        conforms_to=frozenset({"  https://manual.nexusformat.org/  "}),
    )
    assert fmt.media_type == "application/x-hdf5"
    assert fmt.conforms_to == frozenset({"https://manual.nexusformat.org/"})


@pytest.mark.unit
def test_dataset_encoding_rejects_empty_media_type() -> None:
    with pytest.raises(InvalidDatasetEncodingError):
        DatasetEncoding(media_type="")


@pytest.mark.unit
def test_dataset_encoding_rejects_whitespace_only_media_type() -> None:
    with pytest.raises(InvalidDatasetEncodingError):
        DatasetEncoding(media_type="   ")


@pytest.mark.unit
def test_dataset_encoding_rejects_empty_conforms_to_entry() -> None:
    with pytest.raises(InvalidDatasetEncodingError):
        DatasetEncoding(media_type="application/x-hdf5", conforms_to=frozenset({""}))


@pytest.mark.unit
def test_dataset_encoding_rejects_too_many_conforms_to_entries() -> None:
    with pytest.raises(InvalidDatasetEncodingError):
        DatasetEncoding(
            media_type="application/x-hdf5",
            conforms_to=frozenset(f"https://example.com/p/{i}" for i in range(64)),
        )


@pytest.mark.unit
def test_dataset_encoding_rejects_media_type_over_max_length() -> None:
    with pytest.raises(InvalidDatasetEncodingError) as exc_info:
        DatasetEncoding(media_type="x" * (DATASET_MEDIA_TYPE_MAX_LENGTH + 1))
    assert str(DATASET_MEDIA_TYPE_MAX_LENGTH) in str(exc_info.value)


@pytest.mark.unit
def test_dataset_encoding_rejects_conforms_to_entry_over_max_length() -> None:
    with pytest.raises(InvalidDatasetEncodingError) as exc_info:
        DatasetEncoding(
            media_type="application/x-hdf5",
            conforms_to=frozenset({"x" * (DATASET_CONFORMS_TO_ENTRY_MAX_LENGTH + 1)}),
        )
    assert str(DATASET_CONFORMS_TO_ENTRY_MAX_LENGTH) in str(exc_info.value)


# ---------- byte_size validation ----------


@pytest.mark.unit
def test_validate_byte_size_accepts_zero() -> None:
    assert validate_byte_size(0) == 0


@pytest.mark.unit
def test_validate_byte_size_accepts_positive() -> None:
    assert validate_byte_size(1_073_741_824) == 1_073_741_824


@pytest.mark.unit
def test_validate_byte_size_rejects_negative() -> None:
    with pytest.raises(InvalidDatasetByteSizeError):
        validate_byte_size(-1)


# ---------- derived_from validation ----------


@pytest.mark.unit
def test_validate_derived_from_accepts_empty() -> None:
    assert validate_derived_from(frozenset()) == frozenset()


@pytest.mark.unit
def test_validate_derived_from_accepts_within_cap() -> None:
    s = frozenset(uuid4() for _ in range(10))
    assert validate_derived_from(s) == s


@pytest.mark.unit
def test_validate_derived_from_rejects_over_cap() -> None:
    s = frozenset(uuid4() for _ in range(DATASET_DERIVED_FROM_MAX_ENTRIES + 1))
    with pytest.raises(InvalidDerivedFromError):
        validate_derived_from(s)


# ---------- used_calibration_ids validation ----------


@pytest.mark.unit
def test_validate_used_calibration_ids_accepts_empty() -> None:
    """Empty citation set is the default (no calibrations cited)."""
    assert validate_used_calibration_ids(frozenset()) == frozenset()


@pytest.mark.unit
def test_validate_used_calibration_ids_accepts_within_cap() -> None:
    """A reasonable-size citation set (under the cap) is accepted
    verbatim — no element-level existence check at this layer."""
    s = frozenset(uuid4() for _ in range(10))
    assert validate_used_calibration_ids(s) == s


@pytest.mark.unit
def test_validate_used_calibration_ids_accepts_exactly_at_cap() -> None:
    """Boundary: exactly DATASET_USED_CALIBRATIONS_MAX_ENTRIES is
    accepted (off-by-one guard mirrors validate_derived_from)."""
    s = frozenset(uuid4() for _ in range(DATASET_USED_CALIBRATIONS_MAX_ENTRIES))
    assert validate_used_calibration_ids(s) == s


@pytest.mark.unit
def test_validate_used_calibration_ids_rejects_over_cap() -> None:
    """Cardinality cap rejects > DATASET_USED_CALIBRATIONS_MAX_ENTRIES;
    raises InvalidUsedCalibrationsError. Mirrors InvalidDerivedFromError
    shape exactly (same precedent + same default cap of 64)."""
    s = frozenset(uuid4() for _ in range(DATASET_USED_CALIBRATIONS_MAX_ENTRIES + 1))
    with pytest.raises(InvalidUsedCalibrationsError):
        validate_used_calibration_ids(s)


@pytest.mark.unit
def test_invalid_used_calibration_ids_error_carries_count() -> None:
    """The error class exposes `.count` for observability + debugging
    (matches InvalidDerivedFromError contract)."""
    bad_count = DATASET_USED_CALIBRATIONS_MAX_ENTRIES + 5
    err = InvalidUsedCalibrationsError(bad_count)
    assert err.count == bad_count
    assert str(bad_count) in str(err)


# ---------- DatasetStatus enum ----------


@pytest.mark.unit
def test_dataset_status_in_7b() -> None:
    """7b adds Discarded; full lifecycle FSM today is Registered → Discarded."""
    assert {s.value for s in DatasetStatus} == {"Registered", "Discarded"}


@pytest.mark.unit
def test_dataset_status_is_str_enum_for_natural_serialization() -> None:
    assert isinstance(DatasetStatus.REGISTERED, str)
    assert DatasetStatus.REGISTERED == "Registered"
    assert f"{DatasetStatus.REGISTERED}" == "Registered"
    assert DatasetStatus.DISCARDED == "Discarded"


# ---------- Dataset aggregate root ----------


@pytest.mark.unit
def test_dataset_default_status_is_registered() -> None:
    ds = Dataset(
        id=uuid4(),
        name=DatasetName("D"),
        uri=DatasetUri("s3://b/k"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=0,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
    )
    assert ds.status is DatasetStatus.REGISTERED


@pytest.mark.unit
def test_dataset_default_optional_refs_are_none_or_empty() -> None:
    ds = Dataset(
        id=uuid4(),
        name=DatasetName("D"),
        uri=DatasetUri("s3://b/k"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=0,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
    )
    assert ds.producing_run_id is None
    assert ds.subject_id is None
    assert ds.derived_from == frozenset()


# ---------- Error classes ----------


@pytest.mark.unit
def test_dataset_already_exists_error_carries_dataset_id() -> None:
    dataset_id = uuid4()
    err = DatasetAlreadyExistsError(dataset_id)
    assert err.dataset_id == dataset_id
    assert str(dataset_id) in str(err)


@pytest.mark.unit
def test_dataset_not_found_error_carries_dataset_id() -> None:
    dataset_id = uuid4()
    err = DatasetNotFoundError(dataset_id)
    assert err.dataset_id == dataset_id
    assert str(dataset_id) in str(err)


@pytest.mark.unit
def test_producing_run_missing_error_carries_run_id() -> None:
    run_id = uuid4()
    err = ProducingRunNotFoundError(run_id)
    assert err.run_id == run_id
    assert str(run_id) in str(err)


@pytest.mark.unit
def test_linked_subject_missing_error_carries_subject_id() -> None:
    subject_id = uuid4()
    err = LinkedSubjectNotFoundError(subject_id)
    assert err.subject_id == subject_id
    assert str(subject_id) in str(err)


@pytest.mark.unit
def test_derived_from_datasets_missing_error_carries_missing_ids() -> None:
    missing = [uuid4(), uuid4()]
    err = DerivedFromDatasetsNotFoundError(missing)
    assert err.missing_ids == missing
    msg = str(err)
    for m in missing:
        assert str(m) in msg
