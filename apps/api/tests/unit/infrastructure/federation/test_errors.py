"""Unit tests for the federation port-tier error family."""

from datetime import UTC, datetime
from uuid import uuid4

from cora.infrastructure.ports.federation.errors import (
    FederationAdoptionWindowClosedError,
    FederationCanonicalizationMismatchError,
    FederationCircuitOpenError,
    FederationCredentialRevokedError,
    FederationPermitNotFoundError,
    FederationPublicationContentDriftError,
    FederationRateLimitExceededError,
    FederationReceiptMissingError,
    FederationRetryExhaustedError,
    FederationSignatureInvalidError,
    FederationSignerUntrustedError,
    NoAdapterForFacilityError,
)
from cora.infrastructure.ports.federation.value_types import ArtifactReference


def test_federation_permit_not_found_error_carries_kwargs_and_renders_str() -> None:
    pid = uuid4()
    e = FederationPermitNotFoundError(permit_id=pid, lookup_kind="inbound")
    assert e.permit_id == pid
    assert e.lookup_kind == "inbound"
    assert "inbound" in str(e)


def test_federation_signature_invalid_error_carries_failed_stage() -> None:
    e = FederationSignatureInvalidError(
        content_hash=b"\xaa" * 32,
        envelope_kind="dsse_static_jwks",
        failed_stage="signature",
    )
    assert e.failed_stage == "signature"
    assert e.envelope_kind == "dsse_static_jwks"
    assert "dsse_static_jwks" in str(e)


def test_federation_signer_untrusted_error_distinct_from_signature_invalid() -> None:
    e = FederationSignerUntrustedError(
        content_hash=b"\xbb" * 32,
        envelope_kind="cose_sign1_scitt",
        attempted_key_ref="kid-A",
    )
    assert e.attempted_key_ref == "kid-A"


def test_federation_publication_content_drift_error_carries_both_hashes() -> None:
    e = FederationPublicationContentDriftError(
        reference_content_hash=b"\x01" * 32,
        fetched_content_hash=b"\x02" * 32,
    )
    assert e.reference_content_hash != e.fetched_content_hash
    assert e.reference_content_hash.hex() in str(e)
    assert e.fetched_content_hash.hex() in str(e)


def test_federation_credential_revoked_error_carries_credential_id_and_timestamp() -> None:
    cid = uuid4()
    ts = datetime(2026, 5, 31, tzinfo=UTC)
    e = FederationCredentialRevokedError(credential_id=cid, revoked_at=ts)
    assert e.credential_id == cid
    assert e.revoked_at == ts


def test_federation_retry_exhausted_error_carries_reference_and_attempt_count() -> None:
    ref = ArtifactReference(
        content_hash=b"\x03" * 32,
        payload_type="application/vnd.cora.test+json",
        source_facility_id=uuid4(),
        hint_locator="https://peer/x",
    )
    e = FederationRetryExhaustedError(reference=ref, attempts=5, last_error_class="ConnectionError")
    assert e.attempts == 5
    assert e.last_error_class == "ConnectionError"


def test_federation_circuit_open_error_carries_facility_id_and_opened_at() -> None:
    fid = uuid4()
    opened = datetime(2026, 5, 31, tzinfo=UTC)
    e = FederationCircuitOpenError(source_facility_id=fid, opened_at=opened)
    assert e.source_facility_id == fid
    assert e.opened_at == opened


def test_federation_rate_limit_exceeded_error_carries_seconds_as_opaque() -> None:
    e = FederationRateLimitExceededError(source_facility_id=uuid4(), retry_after_seconds=120)
    assert e.retry_after_seconds == 120


def test_federation_adoption_window_closed_error_discriminates_via_status() -> None:
    for status in ("Live", "Yanked", "Withdrawn", "Expired", "AbiTierObsoleteOrRemoved"):
        e = FederationAdoptionWindowClosedError(
            content_hash=b"\x04" * 32,
            publication_status=status,  # type: ignore[arg-type]
        )
        assert e.publication_status == status


def test_federation_receipt_missing_error_normalizes_required_and_observed_to_sorted_tuple() -> (
    None
):
    e = FederationReceiptMissingError(
        content_hash=b"\x05" * 32,
        envelope_kind="cose_sign1_scitt",
        required_receipt_kinds={"scitt", "rekor_sct"},
        observed_receipt_kinds={"ts_authority"},
    )
    assert e.required_receipt_kinds == ("rekor_sct", "scitt")
    assert e.observed_receipt_kinds == ("ts_authority",)


def test_no_adapter_for_facility_error_carries_facility_id() -> None:
    fid = uuid4()
    e = NoAdapterForFacilityError(source_facility_id=fid)
    assert e.source_facility_id == fid


def test_federation_canonicalization_mismatch_error_bridges_memo_1_and_memo_3() -> None:
    e = FederationCanonicalizationMismatchError(
        content_hash=b"\x06" * 32,
        expected_canonicalization_profile_id="cora/v1",
        observed_profile_id="cora/v2-cose",
    )
    assert e.expected_canonicalization_profile_id == "cora/v1"
    assert e.observed_profile_id == "cora/v2-cose"
