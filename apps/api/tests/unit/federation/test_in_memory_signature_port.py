"""Unit tests for InMemorySignaturePort."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.federation.adapters.in_memory_signature_port import InMemorySignaturePort
from cora.infrastructure.ports.canonicalization import CanonicalizedBytes
from cora.infrastructure.ports.federation import (
    DsseStaticJwksEnvelope,
    FederationTrustContext,
    PublishedArtifact,
    Rejected,
    SignaturePort,
    SignedOffBy,
    UnverifiabilityReason,
    Unverifiable,
    Verified,
)


def _artifact(content_hash: bytes = b"\x01" * 32) -> PublishedArtifact:
    return PublishedArtifact(
        content_hash=content_hash,
        canonical_bytes=b"DSSEv1 ...",
        payload_type="application/vnd.cora.test+json",
        signature_envelope=DsseStaticJwksEnvelope(
            signing_version="cora/v1", payload_bytes=b"opaque"
        ),
        source_facility_id=uuid4(),
        published_at=datetime(2026, 5, 31, tzinfo=UTC),
        expires_at=None,
        abi_tier="Stable",
        dco_chain=(SignedOffBy(actor_id=uuid4(), signed_at=datetime(2026, 5, 31, tzinfo=UTC)),),
        schema_version=1,
        canonicalization_version="cora/v1",
    )


def _trust_context() -> FederationTrustContext:
    return FederationTrustContext(
        permit_id=uuid4(),
        allowed_credentials=frozenset(),
        allowed_payload_types=frozenset({"application/vnd.cora.test+json"}),
        abi_tier_floor="Stable",
    )


def _canonicalized(version: str = "cora/v1") -> CanonicalizedBytes:
    return CanonicalizedBytes(
        bytes_=b"DSSEv1 ...",
        adapter_version=version,
        payload_type="application/vnd.cora.test+json",
    )


def test_in_memory_signature_port_satisfies_signature_port_protocol() -> None:
    assert isinstance(InMemorySignaturePort(), SignaturePort)


@pytest.mark.asyncio
async def test_verify_returns_default_verified_outcome_when_no_simulation_set() -> None:
    port = InMemorySignaturePort()
    outcome = await port.verify(_artifact(), _trust_context())
    assert isinstance(outcome, Verified)
    assert all(r.outcome == "pass" for r in outcome.stage_results)


@pytest.mark.asyncio
async def test_simulate_signature_invalid_makes_verify_return_rejected_with_failed_stage() -> None:
    port = InMemorySignaturePort()
    port.simulate_signature_invalid(b"\xaa" * 32, failed_stage="signature")
    outcome = await port.verify(_artifact(content_hash=b"\xaa" * 32), _trust_context())
    assert isinstance(outcome, Rejected)
    assert outcome.rejection.failed_stage == "signature"


@pytest.mark.asyncio
async def test_set_verification_outcome_overrides_default_per_content_hash() -> None:
    port = InMemorySignaturePort()
    primed = Unverifiable(
        stage_results=(),
        unverifiability=UnverifiabilityReason(failed_stage="key_resolution", reason="test"),
    )
    port.set_verification_outcome(b"\xbb" * 32, primed)
    outcome = await port.verify(_artifact(content_hash=b"\xbb" * 32), _trust_context())
    assert outcome is primed


@pytest.mark.asyncio
async def test_sign_returns_in_memory_dsse_static_jwks_envelope_with_matching_version() -> None:
    port = InMemorySignaturePort()
    canonicalized = _canonicalized(version="cora/v1")
    envelope = await port.sign(canonicalized, _trust_context())
    assert isinstance(envelope, DsseStaticJwksEnvelope)
    assert envelope.signing_version == "cora/v1"
    assert envelope.payload_bytes.endswith(canonicalized.bytes_)


@pytest.mark.asyncio
async def test_set_sign_envelope_overrides_default_per_canonicalization_version() -> None:
    port = InMemorySignaturePort()
    primed = DsseStaticJwksEnvelope(signing_version="cora/v2-cose", payload_bytes=b"custom")
    port.set_sign_envelope("cora/v2-cose", primed)
    out = await port.sign(_canonicalized(version="cora/v2-cose"), _trust_context())
    assert out is primed


@pytest.mark.asyncio
async def test_clear_simulations_resets_both_verify_and_sign_overrides() -> None:
    port = InMemorySignaturePort()
    port.simulate_signature_invalid(b"\xcc" * 32, failed_stage="signature")
    port.set_sign_envelope(
        "cora/v1", DsseStaticJwksEnvelope(signing_version="cora/v1", payload_bytes=b"x")
    )
    port.clear_simulations()
    outcome = await port.verify(_artifact(content_hash=b"\xcc" * 32), _trust_context())
    assert isinstance(outcome, Verified)


@pytest.mark.asyncio
async def test_aclose_clears_state_and_is_idempotent() -> None:
    port = InMemorySignaturePort()
    port.simulate_signature_invalid(b"\xdd" * 32, failed_stage="signature")
    await port.aclose()
    await port.aclose()
