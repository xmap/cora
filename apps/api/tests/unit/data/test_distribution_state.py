"""Unit tests for Distribution-aggregate state value objects + closed lookups.

Covers DistributionUri validation, AccessProtocol closed enum,
URI_SCHEME_TO_ACCESS_PROTOCOL closed lookup, and the
validate_distribution_byte_size helper.
"""

import pytest

from cora.data.aggregates.distribution import (
    DISTRIBUTION_URI_MAX_LENGTH,
    URI_SCHEME_TO_ACCESS_PROTOCOL,
    AccessProtocol,
    DistributionUri,
    InvalidDistributionByteSizeError,
    InvalidDistributionUriError,
    validate_distribution_byte_size,
)

# ---------- DistributionUri ----------


@pytest.mark.unit
def test_distribution_uri_trims_whitespace() -> None:
    uri = DistributionUri("  s3://b/k  ")
    assert uri.value == "s3://b/k"


@pytest.mark.unit
def test_distribution_uri_rejects_empty() -> None:
    with pytest.raises(InvalidDistributionUriError):
        DistributionUri("")


@pytest.mark.unit
def test_distribution_uri_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidDistributionUriError):
        DistributionUri("   ")


@pytest.mark.unit
def test_distribution_uri_rejects_missing_scheme() -> None:
    with pytest.raises(InvalidDistributionUriError):
        DistributionUri("just-a-path")


@pytest.mark.unit
def test_distribution_uri_rejects_over_max_length() -> None:
    too_long = "s3://" + "a" * (DISTRIBUTION_URI_MAX_LENGTH + 10)
    with pytest.raises(InvalidDistributionUriError):
        DistributionUri(too_long)


@pytest.mark.unit
@pytest.mark.parametrize("blocked", ["javascript", "vbscript", "data", "about", "view-source"])
def test_distribution_uri_rejects_blocked_schemes(blocked: str) -> None:
    with pytest.raises(InvalidDistributionUriError):
        DistributionUri(f"{blocked}:malicious")


@pytest.mark.unit
@pytest.mark.parametrize(
    "good_uri",
    [
        "s3://bucket/key.h5",
        "https://aps.anl.gov/data/x.h5",
        "file:///mnt/data/x.h5",
        "globus://endpoint/path/x.h5",
        "nfs://server/share/x.h5",
    ],
)
def test_distribution_uri_accepts_well_formed_uris(good_uri: str) -> None:
    uri = DistributionUri(good_uri)
    assert uri.value == good_uri


# ---------- AccessProtocol closed enum ----------


@pytest.mark.unit
def test_access_protocol_has_exactly_six_values() -> None:
    """Closed-StrEnum day-one per L5; pin the cardinality so adding a
    new transport family is an explicit decision."""
    assert {p.value for p in AccessProtocol} == {
        "HTTPS",
        "Globus",
        "S3",
        "POSIX",
        "NFS",
        "OAI_PMH",
    }


@pytest.mark.unit
def test_access_protocol_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="FTP"):
        AccessProtocol("FTP")


# ---------- URI_SCHEME_TO_ACCESS_PROTOCOL closed lookup ----------


@pytest.mark.unit
def test_uri_scheme_lookup_covers_pilot_schemes() -> None:
    """The closed lookup covers the 5 pilot-validated schemes per L24."""
    assert URI_SCHEME_TO_ACCESS_PROTOCOL["https"] is AccessProtocol.HTTPS
    assert URI_SCHEME_TO_ACCESS_PROTOCOL["http"] is AccessProtocol.HTTPS
    assert URI_SCHEME_TO_ACCESS_PROTOCOL["s3"] is AccessProtocol.S3
    assert URI_SCHEME_TO_ACCESS_PROTOCOL["globus"] is AccessProtocol.GLOBUS
    assert URI_SCHEME_TO_ACCESS_PROTOCOL["file"] is AccessProtocol.POSIX
    assert URI_SCHEME_TO_ACCESS_PROTOCOL["nfs"] is AccessProtocol.NFS


@pytest.mark.unit
def test_uri_scheme_lookup_covers_the_indirect_capture_path_scheme() -> None:
    """`cora-capture-path` (cora.data.adapters.capture_path_locator) resolves
    to a POSIX path before any byte is read, so it maps to POSIX here
    too -- defense-in-depth for the backfill, not a new transport
    family; see this entry's own citation in the source dict."""
    assert URI_SCHEME_TO_ACCESS_PROTOCOL["cora-capture-path"] is AccessProtocol.POSIX


@pytest.mark.unit
def test_uri_scheme_lookup_has_no_fallback() -> None:
    """L24 + anti-hook: no `else HTTPS` fallback. Unmapped scheme raises
    KeyError on direct dict access (the Slice 2 backfill wraps in
    UnmappedDistributionUriSchemeError)."""
    with pytest.raises(KeyError):
        _ = URI_SCHEME_TO_ACCESS_PROTOCOL["ftp"]


# ---------- byte_size validator ----------


@pytest.mark.unit
def test_validate_distribution_byte_size_accepts_zero() -> None:
    assert validate_distribution_byte_size(0) == 0


@pytest.mark.unit
def test_validate_distribution_byte_size_accepts_large() -> None:
    assert validate_distribution_byte_size(10**12) == 10**12


@pytest.mark.unit
def test_validate_distribution_byte_size_rejects_negative() -> None:
    with pytest.raises(InvalidDistributionByteSizeError):
        validate_distribution_byte_size(-1)
