"""Unit tests for the federation port Protocols.

Pins the runtime_checkable Protocol surface for PublishPort,
PullPort, and SignaturePort against minimal duck-typed conformers.
"""

from datetime import UTC, datetime
from uuid import uuid4

from cora.infrastructure.ports.canonicalization import CanonicalizedBytes
from cora.infrastructure.ports.federation import (
    ArtifactReference,
    DsseStaticJwksEnvelope,
    FederationTrustContext,
    FetchProvenance,
    PublishedArtifact,
    PublishPort,
    PublishReceipt,
    PulledArtifact,
    PullPort,
    SignatureEnvelope,
    SignaturePort,
    SignedOffBy,
    StageResult,
    VerificationOutcome,
    Verified,
)


def _published() -> PublishedArtifact:
    return PublishedArtifact(
        content_hash=b"\x01" * 32,
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


class _FakePublishAdapter:
    async def publish(self, artifact: PublishedArtifact) -> PublishReceipt:
        _ = artifact
        return PublishReceipt(
            receipt_bytes=b"opaque",
            receipt_format_hint="fake/v0",
            transparency_log_hint="fake-log",
            recorded_at=datetime(2026, 5, 31, tzinfo=UTC),
        )


class _FakePullAdapter:
    async def fetch(self, reference: ArtifactReference) -> PulledArtifact:
        _ = reference
        return PulledArtifact(
            artifact=_published(),
            fetch_provenance=FetchProvenance(
                locator_used="fake://x",
                wire_content_type="application/dsse+json",
                fetch_duration_ms=1,
                byte_count=1,
            ),
        )


class _FakeSignatureAdapter:
    async def verify(
        self,
        artifact: PublishedArtifact,
        trust_context: FederationTrustContext,
    ) -> VerificationOutcome:
        _ = artifact, trust_context
        return Verified(stage_results=(StageResult(stage="content_hash", outcome="pass"),))

    async def sign(
        self,
        canonicalized: CanonicalizedBytes,
        trust_context: FederationTrustContext,
    ) -> SignatureEnvelope:
        _ = canonicalized, trust_context
        return DsseStaticJwksEnvelope(signing_version="cora/v1", payload_bytes=b"opaque")


def test_publish_port_is_runtime_checkable_against_duck_typed_adapter() -> None:
    assert isinstance(_FakePublishAdapter(), PublishPort)


def test_pull_port_is_runtime_checkable_against_duck_typed_adapter() -> None:
    assert isinstance(_FakePullAdapter(), PullPort)


def test_signature_port_is_runtime_checkable_against_duck_typed_adapter() -> None:
    assert isinstance(_FakeSignatureAdapter(), SignaturePort)


def test_object_without_publish_method_is_not_a_publish_port() -> None:
    class _Empty:
        pass

    assert not isinstance(_Empty(), PublishPort)


def test_object_without_fetch_method_is_not_a_pull_port() -> None:
    class _Empty:
        pass

    assert not isinstance(_Empty(), PullPort)


def test_object_without_verify_and_sign_methods_is_not_a_signature_port() -> None:
    class _OnlyVerify:
        async def verify(
            self,
            artifact: PublishedArtifact,
            trust_context: FederationTrustContext,
        ) -> VerificationOutcome:
            _ = artifact, trust_context
            return Verified(stage_results=())

    assert not isinstance(_OnlyVerify(), SignaturePort)
