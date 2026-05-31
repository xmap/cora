"""Architecture fitness: byte-exactness of the v1 canonicalization recipe.

The v1 adapter is the verification path for every shipped Method,
Plan, CalibrationRevision, and signed DecisionRegistered for the
lifetime of the data per the lock memo. Changing any byte the v1
adapter emits would silently invalidate every pinned content_hash
across CORA history.

This fitness test pins a golden vector: for a known input payload
and a known payload_type, the v1 adapter MUST emit the same
SHA-256 digest forever. The constant below was computed from the
shipped `compute_content_hash` helper at the time this fitness was
introduced; any change that alters the constant is a regression on
the immutability invariant and MUST be reverted, not adjusted.
"""

import hashlib

from cora.infrastructure.adapters.default_canonicalization_adapter import (
    DefaultCanonicalizationAdapter,
)

_GOLDEN_PAYLOAD_TYPE = "application/vnd.cora.test-event+json"
_GOLDEN_PAYLOAD = {"name": "test", "value": 42}
_GOLDEN_SHA256_HEX = "1a4badf0f45fff0374a2332cfb29eb6492aecf98fc1b69418faac6a1b700ad8b"


def test_default_canonicalization_adapter_v1_golden_vector_sha256_is_immutable() -> None:
    adapter = DefaultCanonicalizationAdapter()
    out = adapter.canonicalize(_GOLDEN_PAYLOAD_TYPE, _GOLDEN_PAYLOAD)
    actual_hex = hashlib.sha256(out.bytes_).hexdigest()
    assert actual_hex == _GOLDEN_SHA256_HEX, (
        f"v1 canonicalization byte-exactness regression: "
        f"expected {_GOLDEN_SHA256_HEX!r} got {actual_hex!r}. "
        f"Any change that alters this constant invalidates every "
        f"pinned content_hash across CORA history and MUST be "
        f"reverted, not adjusted."
    )


def test_default_canonicalization_adapter_v1_verify_content_hash_matches_golden() -> None:
    adapter = DefaultCanonicalizationAdapter()
    assert adapter.verify_content_hash(_GOLDEN_PAYLOAD_TYPE, _GOLDEN_PAYLOAD, _GOLDEN_SHA256_HEX)


def test_default_canonicalization_adapter_v1_adapter_version_is_locked_to_cora_v1() -> None:
    adapter = DefaultCanonicalizationAdapter()
    assert adapter.adapter_version == "cora/v1"
