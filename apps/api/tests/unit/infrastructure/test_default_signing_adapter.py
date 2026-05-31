"""Unit tests for DefaultSigningAdapter."""

from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from cora.infrastructure.adapters.default_signing_adapter import (
    DefaultSigningAdapter,
    JwksKid,
)
from cora.infrastructure.ports.canonicalization import CanonicalizedBytes
from cora.infrastructure.ports.signing import (
    CanonicalizationVersionMismatchError,
    Signature,
    SigningKeyNotFoundError,
    SigningTrustContext,
)


def _fixed_clock() -> datetime:
    return datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)


def _build_adapter(
    private_keys: dict[str, bytes], public_keys: dict[str, bytes]
) -> DefaultSigningAdapter:
    async def loader(handle: JwksKid) -> bytes:
        return private_keys[handle.kid]

    async def resolver(kid: str) -> bytes:
        return public_keys[kid]

    return DefaultSigningAdapter(
        private_key_loader=loader,
        public_key_resolver=resolver,
        clock=_fixed_clock,
    )


def _keypair() -> tuple[bytes, bytes]:
    private = Ed25519PrivateKey.generate()
    private_bytes = private.private_bytes(
        encoding=Encoding.Raw, format=PrivateFormat.Raw, encryption_algorithm=NoEncryption()
    )
    public_bytes = private.public_key().public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
    return private_bytes, public_bytes


def _canon(bytes_: bytes = b"DSSEv1 0  0 ") -> CanonicalizedBytes:
    return CanonicalizedBytes(
        bytes_=bytes_,
        adapter_version="cora/v1",
        payload_type="application/vnd.cora.test-event+json",
    )


def test_default_signing_adapter_version_is_cora_v1() -> None:
    adapter = _build_adapter({}, {})
    assert adapter.adapter_version == "cora/v1"


def test_jwks_kid_is_frozen_dataclass_with_kid_field() -> None:
    handle = JwksKid(kid="some-kid")
    assert handle.kid == "some-kid"
    with pytest.raises(AttributeError):
        handle.kid = "tampered"  # type: ignore[misc]


def test_jwks_kid_is_hashable_for_trust_context_membership() -> None:
    a = JwksKid(kid="kid-1")
    b = JwksKid(kid="kid-1")
    s: frozenset[JwksKid] = frozenset({a})
    assert b in s


@pytest.mark.asyncio
async def test_sign_returns_signature_with_locked_version_and_clock() -> None:
    priv, _ = _keypair()
    handle = JwksKid(kid="kid-A")
    adapter = _build_adapter({"kid-A": priv}, {})
    canon = _canon(b"DSSEv1 35 application/vnd.cora.test-event+json 2 {}")
    sig = await adapter.sign(canon, handle)
    assert isinstance(sig, Signature)
    assert sig.adapter_version == "cora/v1"
    assert sig.key_handle == handle
    assert sig.signed_at == _fixed_clock()
    assert len(sig.bytes_) == 64


@pytest.mark.asyncio
async def test_sign_rejects_canonicalized_bytes_from_non_v1_adapter() -> None:
    priv, _ = _keypair()
    adapter = _build_adapter({"kid-A": priv}, {})
    canon = CanonicalizedBytes(
        bytes_=b"future",
        adapter_version="cora/v2-cose",
        payload_type="application/vnd.cora.test-event+json",
    )
    with pytest.raises(CanonicalizationVersionMismatchError) as exc_info:
        await adapter.sign(canon, JwksKid(kid="kid-A"))
    assert exc_info.value.canonicalized_version == "cora/v2-cose"
    assert exc_info.value.signing_version == "cora/v1"


@pytest.mark.asyncio
async def test_sign_raises_signing_key_not_found_when_loader_misses() -> None:
    adapter = _build_adapter({}, {})
    with pytest.raises(SigningKeyNotFoundError) as exc_info:
        await adapter.sign(_canon(), JwksKid(kid="lost-kid"))
    assert exc_info.value.adapter_version == "cora/v1"


@pytest.mark.asyncio
async def test_verify_returns_valid_for_matching_signature() -> None:
    priv, pub = _keypair()
    handle = JwksKid(kid="kid-A")
    adapter = _build_adapter({"kid-A": priv}, {"kid-A": pub})
    canon = _canon(b"DSSEv1 35 application/vnd.cora.test-event+json 2 {}")
    sig = await adapter.sign(canon, handle)
    trust = SigningTrustContext(
        trusted_signing_keys=frozenset({handle}),
        algorithm_allowlist=frozenset({"EdDSA"}),
        expected_payload_type=canon.payload_type,
        validity_window=None,
    )
    verdict = await adapter.verify(canon, sig, trust)
    assert verdict.verdict == "Valid"


@pytest.mark.asyncio
async def test_verify_returns_invalid_on_tampered_bytes() -> None:
    priv, pub = _keypair()
    handle = JwksKid(kid="kid-A")
    adapter = _build_adapter({"kid-A": priv}, {"kid-A": pub})
    canon = _canon(b"DSSEv1 35 application/vnd.cora.test-event+json 2 {}")
    sig = await adapter.sign(canon, handle)
    tampered = _canon(b"DSSEv1 35 application/vnd.cora.test-event+json 2 XX")
    trust = SigningTrustContext(
        trusted_signing_keys=frozenset({handle}),
        algorithm_allowlist=frozenset({"EdDSA"}),
        expected_payload_type=canon.payload_type,
        validity_window=None,
    )
    verdict = await adapter.verify(tampered, sig, trust)
    assert verdict.verdict == "Invalid"
    assert "Ed25519" in verdict.detail


@pytest.mark.asyncio
async def test_verify_returns_unverifiable_when_key_not_in_trust_context() -> None:
    priv, pub = _keypair()
    handle = JwksKid(kid="kid-A")
    adapter = _build_adapter({"kid-A": priv}, {"kid-A": pub})
    canon = _canon()
    sig = await adapter.sign(canon, handle)
    trust = SigningTrustContext(
        trusted_signing_keys=frozenset(),
        algorithm_allowlist=frozenset({"EdDSA"}),
        expected_payload_type=canon.payload_type,
        validity_window=None,
    )
    verdict = await adapter.verify(canon, sig, trust)
    assert verdict.verdict == "Unverifiable"
    assert "not in trust context" in verdict.detail


@pytest.mark.asyncio
async def test_verify_returns_unverifiable_when_resolver_misses() -> None:
    priv, _ = _keypair()
    handle = JwksKid(kid="kid-A")
    adapter = _build_adapter({"kid-A": priv}, {})
    canon = _canon()
    sig = await adapter.sign(canon, handle)
    trust = SigningTrustContext(
        trusted_signing_keys=frozenset({handle}),
        algorithm_allowlist=frozenset({"EdDSA"}),
        expected_payload_type=canon.payload_type,
        validity_window=None,
    )
    verdict = await adapter.verify(canon, sig, trust)
    assert verdict.verdict == "Unverifiable"
    assert "not resolvable" in verdict.detail


@pytest.mark.asyncio
async def test_verify_raises_version_mismatch_when_signature_version_differs() -> None:
    priv, pub = _keypair()
    handle = JwksKid(kid="kid-A")
    adapter = _build_adapter({"kid-A": priv}, {"kid-A": pub})
    canon = _canon()
    sig = await adapter.sign(canon, handle)
    foreign_sig = Signature(
        bytes_=sig.bytes_,
        adapter_version="cora/v2-cose",
        key_handle=sig.key_handle,
        signed_at=sig.signed_at,
    )
    trust = SigningTrustContext(
        trusted_signing_keys=frozenset({handle}),
        algorithm_allowlist=frozenset({"EdDSA"}),
        expected_payload_type=canon.payload_type,
        validity_window=None,
    )
    with pytest.raises(CanonicalizationVersionMismatchError):
        await adapter.verify(canon, foreign_sig, trust)
