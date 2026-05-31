"""Unit tests for the verify-then-apply orchestrator."""

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.federation.adapters.in_memory_signature_port import InMemorySignaturePort
from cora.infrastructure.adapters.canonicalization_registry import (
    CanonicalizationRegistry,
)
from cora.infrastructure.adapters.default_canonicalization_adapter import (
    DefaultCanonicalizationAdapter,
)
from cora.infrastructure.ports.federation.value_types import (
    AssistedBy,
    DsseStaticJwksEnvelope,
    FederationTrustContext,
    PublishedArtifact,
    Rejected,
    SignedOffBy,
    UnverifiabilityReason,
    Unverifiable,
    Verified,
)
from cora.infrastructure.published_artifact import verify_then_apply

_NOW = datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)


def _registry() -> CanonicalizationRegistry:
    r = CanonicalizationRegistry()
    r.register("cora/v1", DefaultCanonicalizationAdapter())
    r.set_default("cora/v1")
    return r


def _trust_context() -> FederationTrustContext:
    return FederationTrustContext(
        permit_id=uuid4(),
        allowed_credentials=frozenset(),
        allowed_payload_types=frozenset({"application/vnd.cora.test+json"}),
        abi_tier_floor="Stable",
    )


def _artifact(
    *,
    canonical_bytes: bytes = b"DSSEv1 ...",
    abi_tier: str = "Stable",
    payload_type: str = "application/vnd.cora.test+json",
    expires_at: datetime | None = None,
    canonicalization_version: str = "cora/v1",
    dco_chain: tuple[object, ...] | None = None,
) -> PublishedArtifact:
    if dco_chain is None:
        dco_chain = (SignedOffBy(actor_id=uuid4(), signed_at=_NOW),)
    return PublishedArtifact(
        content_hash=hashlib.sha256(canonical_bytes).digest(),
        canonical_bytes=canonical_bytes,
        payload_type=payload_type,
        signature_envelope=DsseStaticJwksEnvelope(
            signing_version=canonicalization_version, payload_bytes=b"opaque"
        ),
        source_facility_id=uuid4(),
        published_at=_NOW,
        expires_at=expires_at,
        abi_tier=abi_tier,
        dco_chain=dco_chain,  # type: ignore[arg-type]
        schema_version=1,
        canonicalization_version=canonicalization_version,
    )


@pytest.mark.asyncio
async def test_verify_then_apply_returns_verified_for_well_formed_artifact() -> None:
    outcome = await verify_then_apply(
        _artifact(),
        trust_context=_trust_context(),
        signature_port=InMemorySignaturePort(),
        canonicalization_registry=_registry(),
        now=_NOW,
    )
    assert isinstance(outcome, Verified)
    assert any(r.stage == "content_hash" and r.outcome == "pass" for r in outcome.stage_results)
    assert any(r.stage == "abi_tier" and r.outcome == "pass" for r in outcome.stage_results)
    assert any(r.stage == "dco_chain" and r.outcome == "pass" for r in outcome.stage_results)


@pytest.mark.asyncio
async def test_verify_then_apply_short_circuits_rejected_on_untrusted_payload_type() -> None:
    outcome = await verify_then_apply(
        _artifact(payload_type="application/vnd.cora.unknown+json"),
        trust_context=_trust_context(),
        signature_port=InMemorySignaturePort(),
        canonicalization_registry=_registry(),
        now=_NOW,
    )
    assert isinstance(outcome, Rejected)
    assert outcome.rejection.failed_stage == "payload_type_trusted"


@pytest.mark.asyncio
async def test_verify_then_apply_returns_unverifiable_when_canon_version_unregistered() -> None:
    outcome = await verify_then_apply(
        _artifact(canonicalization_version="cora/v99-unknown"),
        trust_context=_trust_context(),
        signature_port=InMemorySignaturePort(),
        canonicalization_registry=_registry(),
        now=_NOW,
    )
    assert isinstance(outcome, Unverifiable)
    assert outcome.unverifiability.failed_stage == "content_hash"


@pytest.mark.asyncio
async def test_verify_then_apply_rejects_on_content_hash_mismatch() -> None:
    canonical_bytes = b"DSSEv1 original"
    artifact = PublishedArtifact(
        content_hash=b"\xff" * 32,
        canonical_bytes=canonical_bytes,
        payload_type="application/vnd.cora.test+json",
        signature_envelope=DsseStaticJwksEnvelope(
            signing_version="cora/v1", payload_bytes=b"opaque"
        ),
        source_facility_id=uuid4(),
        published_at=_NOW,
        expires_at=None,
        abi_tier="Stable",
        dco_chain=(SignedOffBy(actor_id=uuid4(), signed_at=_NOW),),
        schema_version=1,
        canonicalization_version="cora/v1",
    )
    outcome = await verify_then_apply(
        artifact,
        trust_context=_trust_context(),
        signature_port=InMemorySignaturePort(),
        canonicalization_registry=_registry(),
        now=_NOW,
    )
    assert isinstance(outcome, Rejected)
    assert outcome.rejection.failed_stage == "content_hash"


@pytest.mark.asyncio
async def test_verify_then_apply_propagates_rejected_from_signature_port() -> None:
    signature_port = InMemorySignaturePort()
    artifact = _artifact()
    signature_port.simulate_signature_invalid(artifact.content_hash, failed_stage="signature")
    outcome = await verify_then_apply(
        artifact,
        trust_context=_trust_context(),
        signature_port=signature_port,
        canonicalization_registry=_registry(),
        now=_NOW,
    )
    assert isinstance(outcome, Rejected)
    assert outcome.rejection.failed_stage == "signature"


@pytest.mark.asyncio
async def test_verify_then_apply_propagates_unverifiable_from_signature_port() -> None:
    signature_port = InMemorySignaturePort()
    artifact = _artifact()
    signature_port.set_verification_outcome(
        artifact.content_hash,
        Unverifiable(
            stage_results=(),
            unverifiability=UnverifiabilityReason(
                failed_stage="key_resolution", reason="JWKS unavailable"
            ),
        ),
    )
    outcome = await verify_then_apply(
        artifact,
        trust_context=_trust_context(),
        signature_port=signature_port,
        canonicalization_registry=_registry(),
        now=_NOW,
    )
    assert isinstance(outcome, Unverifiable)
    assert outcome.unverifiability.failed_stage == "key_resolution"


@pytest.mark.asyncio
async def test_verify_then_apply_rejects_when_abi_tier_below_floor() -> None:
    outcome = await verify_then_apply(
        _artifact(abi_tier="Testing"),
        trust_context=_trust_context(),
        signature_port=InMemorySignaturePort(),
        canonicalization_registry=_registry(),
        now=_NOW,
    )
    assert isinstance(outcome, Rejected)
    assert outcome.rejection.failed_stage == "abi_tier"


@pytest.mark.asyncio
async def test_verify_then_apply_rejects_when_artifact_is_expired() -> None:
    outcome = await verify_then_apply(
        _artifact(expires_at=datetime(2026, 1, 1, tzinfo=UTC)),
        trust_context=_trust_context(),
        signature_port=InMemorySignaturePort(),
        canonicalization_registry=_registry(),
        now=_NOW,
    )
    assert isinstance(outcome, Rejected)
    assert outcome.rejection.failed_stage == "expires_at"


@pytest.mark.asyncio
async def test_verify_then_apply_rejects_on_ai_only_dco_chain() -> None:
    outcome = await verify_then_apply(
        _artifact(
            dco_chain=(
                AssistedBy(
                    agent_id=uuid4(),
                    model_ref="m",
                    assisted_at=_NOW,
                    citation="x",
                ),
            )
        ),
        trust_context=_trust_context(),
        signature_port=InMemorySignaturePort(),
        canonicalization_registry=_registry(),
        now=_NOW,
    )
    assert isinstance(outcome, Rejected)
    assert outcome.rejection.failed_stage == "dco_chain"


@pytest.mark.asyncio
async def test_verify_then_apply_records_deferred_stages_as_skip_with_reason() -> None:
    outcome = await verify_then_apply(
        _artifact(),
        trust_context=_trust_context(),
        signature_port=InMemorySignaturePort(),
        canonicalization_registry=_registry(),
        now=_NOW,
    )
    assert isinstance(outcome, Verified)
    deferred_stages = {r.stage for r in outcome.stage_results if r.outcome == "skip"}
    assert {"payload_type_known", "head_pointer_fresh", "replay_cache"}.issubset(deferred_stages)
