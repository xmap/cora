"""Unit tests for InMemoryPublishPort."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.federation.adapters.in_memory_publish_port import InMemoryPublishPort
from cora.infrastructure.ports.federation import (
    DsseStaticJwksEnvelope,
    FederationCredentialRevokedError,
    PublishedArtifact,
    PublishPort,
    SignedOffBy,
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


def test_in_memory_publish_port_satisfies_publish_port_protocol() -> None:
    assert isinstance(InMemoryPublishPort(), PublishPort)


@pytest.mark.asyncio
async def test_publish_records_artifact_and_returns_in_memory_receipt() -> None:
    port = InMemoryPublishPort()
    artifact = _artifact()
    receipt = await port.publish(artifact)
    assert receipt.receipt_format_hint == "in-memory/v1"
    assert receipt.receipt_bytes.startswith(b"in-memory-receipt-")
    assert port.published_artifacts() == (artifact,)


@pytest.mark.asyncio
async def test_publish_increments_receipt_id_across_calls() -> None:
    port = InMemoryPublishPort()
    r1 = await port.publish(_artifact(b"\x01" * 32))
    r2 = await port.publish(_artifact(b"\x02" * 32))
    assert r1.receipt_bytes != r2.receipt_bytes


@pytest.mark.asyncio
async def test_simulate_credential_revoked_makes_next_publish_raise() -> None:
    port = InMemoryPublishPort()
    cid = uuid4()
    ts = datetime(2026, 5, 31, tzinfo=UTC)
    port.simulate_credential_revoked(cid, ts)
    with pytest.raises(FederationCredentialRevokedError) as exc_info:
        await port.publish(_artifact())
    assert exc_info.value.credential_id == cid
    assert exc_info.value.revoked_at == ts


@pytest.mark.asyncio
async def test_clear_simulations_re_enables_publishing_after_revoked_sim() -> None:
    port = InMemoryPublishPort()
    port.simulate_credential_revoked(uuid4(), datetime(2026, 5, 31, tzinfo=UTC))
    with pytest.raises(FederationCredentialRevokedError):
        await port.publish(_artifact())
    port.clear_simulations()
    receipt = await port.publish(_artifact())
    assert receipt is not None


@pytest.mark.asyncio
async def test_aclose_clears_state_and_is_idempotent() -> None:
    port = InMemoryPublishPort()
    await port.publish(_artifact())
    await port.aclose()
    assert port.published_artifacts() == ()
    await port.aclose()
