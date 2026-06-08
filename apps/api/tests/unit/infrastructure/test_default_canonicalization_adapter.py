"""Unit tests for DefaultCanonicalizationAdapter."""

from cora.infrastructure.adapters.default_canonicalization_adapter import (
    DefaultCanonicalizationAdapter,
)
from cora.infrastructure.ports.canonicalization import (
    CanonicalizationFailedError,
    CanonicalizedBytes,
)
from cora.shared.content_hash import compute_content_hash


def test_default_canonicalization_adapter_version_is_cora_v1() -> None:
    adapter = DefaultCanonicalizationAdapter()
    assert adapter.adapter_version == "cora/v1"


def test_canonicalize_returns_canonicalized_bytes_with_locked_version() -> None:
    adapter = DefaultCanonicalizationAdapter()
    out = adapter.canonicalize(
        "application/vnd.cora.test-event+json", {"name": "test", "value": 42}
    )
    assert isinstance(out, CanonicalizedBytes)
    assert out.adapter_version == "cora/v1"
    assert out.payload_type == "application/vnd.cora.test-event+json"
    assert out.bytes_.startswith(b"DSSEv1 ")


def test_canonicalize_byte_for_byte_matches_shipped_helper_pae_wrap() -> None:
    adapter = DefaultCanonicalizationAdapter()
    payload_type = "application/vnd.cora.test-event+json"
    payload = {"name": "test", "value": 42}
    via_adapter = adapter.canonicalize(payload_type, payload).bytes_
    expected_hash = compute_content_hash(payload_type, payload)
    import hashlib

    assert hashlib.sha256(via_adapter).hexdigest() == expected_hash


def test_canonicalize_rejects_payload_type_outside_v1_uri_scheme() -> None:
    adapter = DefaultCanonicalizationAdapter()
    try:
        adapter.canonicalize("application/json", {"x": 1})
    except CanonicalizationFailedError as exc:
        assert exc.payload_type == "application/json"
        assert exc.adapter_version == "cora/v1"
    else:
        raise AssertionError("expected CanonicalizationFailedError")


def test_verify_content_hash_returns_true_on_matching_recomputation() -> None:
    adapter = DefaultCanonicalizationAdapter()
    payload_type = "application/vnd.cora.test-event+json"
    payload = {"name": "test", "value": 42}
    claimed = compute_content_hash(payload_type, payload)
    assert adapter.verify_content_hash(payload_type, payload, claimed) is True


def test_verify_content_hash_returns_false_on_mismatched_claimed_hash() -> None:
    adapter = DefaultCanonicalizationAdapter()
    payload_type = "application/vnd.cora.test-event+json"
    payload = {"name": "test", "value": 42}
    assert adapter.verify_content_hash(payload_type, payload, "0" * 64) is False


def test_verify_content_hash_rejects_payload_type_outside_v1_uri_scheme() -> None:
    adapter = DefaultCanonicalizationAdapter()
    try:
        adapter.verify_content_hash("application/json", {"x": 1}, "0" * 64)
    except CanonicalizationFailedError as exc:
        assert exc.adapter_version == "cora/v1"
    else:
        raise AssertionError("expected CanonicalizationFailedError")
