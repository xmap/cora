"""Unit tests for the CanonicalizationPort Protocol surface and value types."""

from typing import Any

import pytest

from cora.infrastructure.ports.canonicalization import (
    CanonicalizationFailedError,
    CanonicalizationPort,
    CanonicalizedBytes,
    ContentHashMismatchError,
    UnsupportedCanonicalizationVersionError,
)


class _FakeCanonicalizationAdapter:
    """Minimal duck-typed conformer for runtime_checkable Protocol assertions."""

    adapter_version = "fake/v0"

    def canonicalize(self, payload_type: str, payload: Any) -> CanonicalizedBytes:
        return CanonicalizedBytes(
            bytes_=b"",
            adapter_version=self.adapter_version,
            payload_type=payload_type,
        )

    def verify_content_hash(self, payload_type: str, payload: Any, claimed_hash: str) -> bool:
        return False


def test_canonicalization_port_is_runtime_checkable_against_duck_typed_adapter() -> None:
    assert isinstance(_FakeCanonicalizationAdapter(), CanonicalizationPort)


def test_canonicalized_bytes_is_frozen_dataclass_with_mandatory_adapter_version() -> None:
    value = CanonicalizedBytes(
        bytes_=b"abc",
        adapter_version="cora/v1",
        payload_type="application/vnd.cora.test-event+json",
    )
    assert value.bytes_ == b"abc"
    assert value.adapter_version == "cora/v1"
    assert value.payload_type == "application/vnd.cora.test-event+json"
    with pytest.raises(AttributeError):
        value.bytes_ = b"tampered"  # type: ignore[misc]


def test_canonicalized_bytes_construction_without_adapter_version_raises_type_error() -> None:
    with pytest.raises(TypeError):
        CanonicalizedBytes(  # type: ignore[call-arg]
            bytes_=b"abc",
            payload_type="application/vnd.cora.test-event+json",
        )


def test_canonicalization_failed_error_carries_payload_type_adapter_version_reason() -> None:
    error = CanonicalizationFailedError(
        payload_type="application/vnd.cora.bad+json",
        adapter_version="cora/v1",
        reason="Decimal field encountered",
    )
    assert error.payload_type == "application/vnd.cora.bad+json"
    assert error.adapter_version == "cora/v1"
    assert error.reason == "Decimal field encountered"
    assert "application/vnd.cora.bad+json" in str(error)
    assert "Decimal" in str(error)


def test_content_hash_mismatch_error_carries_claimed_and_recomputed_hashes() -> None:
    error = ContentHashMismatchError(
        payload_type="application/vnd.cora.test-event+json",
        claimed_hash="a" * 64,
        recomputed_hash="b" * 64,
        adapter_version="cora/v1",
    )
    assert error.claimed_hash == "a" * 64
    assert error.recomputed_hash == "b" * 64
    assert error.payload_type == "application/vnd.cora.test-event+json"
    assert error.adapter_version == "cora/v1"


def test_unsupported_canonicalization_version_error_carries_registered_set_tuple() -> None:
    error = UnsupportedCanonicalizationVersionError(
        requested_version="cora/v99",
        registered_versions=["cora/v1", "cora/v2-cose"],
    )
    assert error.requested_version == "cora/v99"
    assert error.registered_versions == ("cora/v1", "cora/v2-cose")
    assert "cora/v99" in str(error)
