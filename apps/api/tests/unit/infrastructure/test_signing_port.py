"""Unit tests for the SigningPort Protocol surface and value types."""

from datetime import UTC, datetime

import pytest

from cora.infrastructure.ports.canonicalization import CanonicalizedBytes
from cora.infrastructure.ports.signing import (
    CanonicalizationVersionMismatchError,
    Signature,
    SignatureInvalidError,
    SignatureVerification,
    SigningKeyNotFoundError,
    SigningPort,
    SigningTrustContext,
    UnsupportedSigningAlgorithmError,
    algorithms_intersection,
)


class _FakeSigningAdapter:
    """Minimal duck-typed conformer for runtime_checkable Protocol assertions."""

    adapter_version = "fake/v0"

    async def sign(self, canonicalized: CanonicalizedBytes, key_handle: object) -> Signature:
        return Signature(
            bytes_=b"\x00" * 64,
            adapter_version=self.adapter_version,
            key_handle=key_handle,
            signed_at=datetime(2026, 5, 31, tzinfo=UTC),
        )

    async def verify(
        self,
        canonicalized: CanonicalizedBytes,
        signature: Signature,
        signing_trust_context: SigningTrustContext,
    ) -> SignatureVerification:
        return SignatureVerification(verdict="Valid")


def test_signing_port_is_runtime_checkable_against_duck_typed_adapter() -> None:
    assert isinstance(_FakeSigningAdapter(), SigningPort)


def test_signature_is_frozen_dataclass_with_locked_fields() -> None:
    sig = Signature(
        bytes_=b"\x01" * 64,
        adapter_version="cora/v1",
        key_handle="some-kid",
        signed_at=datetime(2026, 5, 31, tzinfo=UTC),
    )
    assert sig.bytes_ == b"\x01" * 64
    assert sig.adapter_version == "cora/v1"
    assert sig.key_handle == "some-kid"
    assert sig.signed_at == datetime(2026, 5, 31, tzinfo=UTC)
    with pytest.raises(AttributeError):
        sig.bytes_ = b"tampered"  # type: ignore[misc]


def test_signing_trust_context_carries_locked_policy_fields() -> None:
    ctx = SigningTrustContext(
        trusted_signing_keys=frozenset({"kid-a", "kid-b"}),
        algorithm_allowlist=frozenset({"EdDSA"}),
        expected_payload_type="application/vnd.cora.test-event+json",
        validity_window=(
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2027, 1, 1, tzinfo=UTC),
        ),
    )
    assert ctx.trusted_signing_keys == frozenset({"kid-a", "kid-b"})
    assert ctx.algorithm_allowlist == frozenset({"EdDSA"})
    assert ctx.expected_payload_type == "application/vnd.cora.test-event+json"
    assert ctx.validity_window is not None


def test_signing_trust_context_accepts_none_validity_window() -> None:
    ctx = SigningTrustContext(
        trusted_signing_keys=frozenset(),
        algorithm_allowlist=frozenset({"EdDSA"}),
        expected_payload_type="application/vnd.cora.test-event+json",
        validity_window=None,
    )
    assert ctx.validity_window is None


def test_signature_verification_default_detail_is_empty_string() -> None:
    verdict = SignatureVerification(verdict="Valid")
    assert verdict.verdict == "Valid"
    assert verdict.detail == ""


def test_signature_verification_carries_unverifiable_verdict_distinct_from_invalid() -> None:
    unverifiable = SignatureVerification(verdict="Unverifiable", detail="JWKS rotation in flight")
    invalid = SignatureVerification(verdict="Invalid", detail="Ed25519 verify rejected")
    assert unverifiable.verdict == "Unverifiable"
    assert invalid.verdict == "Invalid"
    assert unverifiable.detail != invalid.detail


def test_signing_key_not_found_error_carries_key_handle_and_adapter_version() -> None:
    error = SigningKeyNotFoundError(key_handle="lost-kid", adapter_version="cora/v1")
    assert error.key_handle == "lost-kid"
    assert error.adapter_version == "cora/v1"
    assert "lost-kid" in str(error)
    assert "cora/v1" in str(error)


def test_signature_invalid_error_carries_adapter_version_and_reason() -> None:
    error = SignatureInvalidError(adapter_version="cora/v1", reason="Ed25519 verify returned False")
    assert error.adapter_version == "cora/v1"
    assert error.reason == "Ed25519 verify returned False"


def test_unsupported_signing_algorithm_error_carries_requested_algorithm() -> None:
    error = UnsupportedSigningAlgorithmError(requested_algorithm="HS256", adapter_version="cora/v1")
    assert error.requested_algorithm == "HS256"
    assert error.adapter_version == "cora/v1"


def test_canonicalization_version_mismatch_error_carries_both_versions() -> None:
    error = CanonicalizationVersionMismatchError(
        canonicalized_version="cora/v1", signing_version="cora/v2-cose"
    )
    assert error.canonicalized_version == "cora/v1"
    assert error.signing_version == "cora/v2-cose"
    assert "cora/v1" in str(error)
    assert "cora/v2-cose" in str(error)


def test_algorithms_intersection_returns_allowed_subset() -> None:
    allowlist = frozenset({"EdDSA", "ES256"})
    requested = ["EdDSA", "HS256"]
    assert algorithms_intersection(requested, allowlist) == frozenset({"EdDSA"})


def test_algorithms_intersection_returns_empty_when_no_overlap() -> None:
    allowlist = frozenset({"EdDSA"})
    requested = ["HS256", "RS256"]
    assert algorithms_intersection(requested, allowlist) == frozenset()
