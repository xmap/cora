"""Unit tests for InMemoryPullPort."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.federation.adapters.in_memory_pull_port import InMemoryPullPort
from cora.infrastructure.ports.federation import (
    ArtifactReference,
    DsseStaticJwksEnvelope,
    FederationCircuitOpenError,
    FederationPublicationContentDriftError,
    FetchProvenance,
    PublishedArtifact,
    PulledArtifact,
    PullPort,
    SignedOffBy,
)


def _ref(facility_id: object | None = None) -> ArtifactReference:
    return ArtifactReference(
        content_hash=b"\x01" * 32,
        payload_type="application/vnd.cora.test+json",
        source_facility_id=facility_id if facility_id is not None else uuid4(),  # type: ignore[arg-type]
        hint_locator="https://peer/x",
    )


def _pulled(reference: ArtifactReference) -> PulledArtifact:
    artifact = PublishedArtifact(
        content_hash=reference.content_hash,
        canonical_bytes=b"DSSEv1 ...",
        payload_type=reference.payload_type,
        signature_envelope=DsseStaticJwksEnvelope(
            signing_version="cora/v1", payload_bytes=b"opaque"
        ),
        source_facility_id=reference.source_facility_id,
        published_at=datetime(2026, 5, 31, tzinfo=UTC),
        expires_at=None,
        abi_tier="Stable",
        dco_chain=(SignedOffBy(actor_id=uuid4(), signed_at=datetime(2026, 5, 31, tzinfo=UTC)),),
        schema_version=1,
        canonicalization_version="cora/v1",
    )
    return PulledArtifact(
        artifact=artifact,
        fetch_provenance=FetchProvenance(
            locator_used="in-memory://x",
            wire_content_type="application/dsse+json",
            fetch_duration_ms=1,
            byte_count=len(artifact.canonical_bytes),
        ),
    )


def test_in_memory_pull_port_satisfies_pull_port_protocol() -> None:
    assert isinstance(InMemoryPullPort(), PullPort)


@pytest.mark.asyncio
async def test_fetch_without_primed_response_raises_key_error_with_guidance() -> None:
    port = InMemoryPullPort()
    with pytest.raises(KeyError, match="set_pull_response"):
        await port.fetch(_ref())


@pytest.mark.asyncio
async def test_set_pull_response_then_fetch_returns_primed_artifact() -> None:
    port = InMemoryPullPort()
    ref = _ref()
    pulled = _pulled(ref)
    port.set_pull_response(ref, pulled)
    got = await port.fetch(ref)
    assert got is pulled


@pytest.mark.asyncio
async def test_simulate_registry_unreachable_makes_fetch_raise_circuit_open() -> None:
    port = InMemoryPullPort()
    facility_id = uuid4()
    opened = datetime(2026, 5, 31, tzinfo=UTC)
    port.simulate_registry_unreachable(facility_id, opened)
    with pytest.raises(FederationCircuitOpenError) as exc_info:
        await port.fetch(_ref(facility_id=facility_id))
    assert exc_info.value.source_facility_id == facility_id
    assert exc_info.value.opened_at == opened


@pytest.mark.asyncio
async def test_simulate_content_drift_makes_fetch_raise_drift_with_mismatched_hashes() -> None:
    port = InMemoryPullPort()
    ref = _ref()
    port.simulate_content_drift(ref)
    with pytest.raises(FederationPublicationContentDriftError) as exc_info:
        await port.fetch(ref)
    assert exc_info.value.reference_content_hash == ref.content_hash
    assert exc_info.value.fetched_content_hash != ref.content_hash


@pytest.mark.asyncio
async def test_clear_simulations_after_unreachable_sim_lets_fetch_return_response() -> None:
    port = InMemoryPullPort()
    facility_id = uuid4()
    port.simulate_registry_unreachable(facility_id, datetime(2026, 5, 31, tzinfo=UTC))
    ref = _ref(facility_id=facility_id)
    port.set_pull_response(ref, _pulled(ref))
    with pytest.raises(FederationCircuitOpenError):
        await port.fetch(ref)
    port.clear_simulations()
    got = await port.fetch(ref)
    assert got.artifact.content_hash == ref.content_hash


def test_make_provenance_helper_returns_well_formed_fetch_provenance() -> None:
    p = InMemoryPullPort.make_provenance(byte_count=42)
    assert p.byte_count == 42
    assert p.wire_content_type == "application/dsse+json"


@pytest.mark.asyncio
async def test_aclose_clears_state_and_is_idempotent() -> None:
    port = InMemoryPullPort()
    port.set_pull_response(_ref(), _pulled(_ref()))
    await port.aclose()
    await port.aclose()
