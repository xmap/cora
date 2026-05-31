"""Unit tests for FederationRegistry composite dispatcher."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.adapters.federation_registry import FederationRegistry
from cora.federation.adapters.in_memory_publish_port import InMemoryPublishPort
from cora.federation.adapters.in_memory_pull_port import InMemoryPullPort
from cora.infrastructure.ports.federation import (
    ArtifactReference,
    DsseStaticJwksEnvelope,
    NoAdapterForFacilityError,
    PublishedArtifact,
    PublishPort,
    PulledArtifact,
    PullPort,
    SignedOffBy,
)


def _facility(hex_prefix: str) -> UUID:
    """Build a UUID whose hex representation starts with `hex_prefix`."""
    padded = hex_prefix.ljust(32, "0")
    return UUID(padded)


def _artifact(facility_id: UUID) -> PublishedArtifact:
    return PublishedArtifact(
        content_hash=b"\x01" * 32,
        canonical_bytes=b"DSSEv1 ...",
        payload_type="application/vnd.cora.test+json",
        signature_envelope=DsseStaticJwksEnvelope(
            signing_version="cora/v1", payload_bytes=b"opaque"
        ),
        source_facility_id=facility_id,
        published_at=datetime(2026, 5, 31, tzinfo=UTC),
        expires_at=None,
        abi_tier="Stable",
        dco_chain=(SignedOffBy(actor_id=uuid4(), signed_at=datetime(2026, 5, 31, tzinfo=UTC)),),
        schema_version=1,
        canonicalization_version="cora/v1",
    )


def _reference(facility_id: UUID) -> ArtifactReference:
    return ArtifactReference(
        content_hash=b"\x01" * 32,
        payload_type="application/vnd.cora.test+json",
        source_facility_id=facility_id,
        hint_locator="https://peer/x",
    )


def test_federation_registry_satisfies_publish_port_protocol() -> None:
    assert isinstance(FederationRegistry(), PublishPort)


def test_federation_registry_satisfies_pull_port_protocol() -> None:
    assert isinstance(FederationRegistry(), PullPort)


@pytest.mark.asyncio
async def test_publish_routes_to_adapter_registered_under_facility_prefix() -> None:
    registry = FederationRegistry()
    aps = InMemoryPublishPort()
    nsls = InMemoryPublishPort()
    registry.register("aaaa", aps)
    registry.register("bbbb", nsls)
    artifact = _artifact(_facility("aaaa1234"))
    await registry.publish(artifact)
    assert len(aps.published_artifacts()) == 1
    assert len(nsls.published_artifacts()) == 0


@pytest.mark.asyncio
async def test_publish_longer_prefix_wins_over_shorter_prefix() -> None:
    registry = FederationRegistry()
    broad = InMemoryPublishPort()
    specific = InMemoryPublishPort()
    registry.register("aa", broad)
    registry.register("aabb", specific)
    artifact = _artifact(_facility("aabb1234"))
    await registry.publish(artifact)
    assert len(specific.published_artifacts()) == 1
    assert len(broad.published_artifacts()) == 0


@pytest.mark.asyncio
async def test_publish_with_no_matching_prefix_raises_no_adapter_for_facility() -> None:
    registry = FederationRegistry()
    registry.register("aaaa", InMemoryPublishPort())
    with pytest.raises(NoAdapterForFacilityError):
        await registry.publish(_artifact(_facility("ffff1234")))


@pytest.mark.asyncio
async def test_fetch_routes_to_adapter_registered_under_facility_prefix() -> None:
    registry = FederationRegistry()
    aps_pull = InMemoryPullPort()
    fac = _facility("aaaa")
    ref = _reference(fac)
    pulled = await _build_pulled(ref)
    aps_pull.set_pull_response(ref, pulled)
    registry.register("aaaa", aps_pull)
    got = await registry.fetch(ref)
    assert got is pulled


@pytest.mark.asyncio
async def test_fetch_with_no_matching_prefix_raises_no_adapter_for_facility() -> None:
    registry = FederationRegistry()
    registry.register("aaaa", InMemoryPullPort())
    with pytest.raises(NoAdapterForFacilityError):
        await registry.fetch(_reference(_facility("ffff")))


def test_register_with_existing_prefix_replaces_prior_entry() -> None:
    registry = FederationRegistry()
    first = InMemoryPublishPort()
    second = InMemoryPublishPort()
    registry.register("aaaa", first)
    registry.register("aaaa", second)
    assert registry.registered_prefixes() == ("aaaa",)


def test_registered_prefixes_preserves_registration_order() -> None:
    registry = FederationRegistry()
    registry.register("aaaa", InMemoryPublishPort())
    registry.register("bbbb", InMemoryPullPort())
    registry.register("cccc", InMemoryPublishPort())
    assert registry.registered_prefixes() == ("aaaa", "bbbb", "cccc")


@pytest.mark.asyncio
async def test_aclose_closes_all_registered_adapters_and_is_idempotent() -> None:
    registry = FederationRegistry()
    adapter = InMemoryPublishPort()
    registry.register("aaaa", adapter)
    await registry.aclose()
    await registry.aclose()


@pytest.mark.asyncio
async def test_aclose_with_flaky_adapter_completes_without_raising() -> None:
    class _FlakyAdapter:
        async def publish(self, artifact: PublishedArtifact) -> object:
            raise NotImplementedError

        async def aclose(self) -> None:
            raise RuntimeError("flaky teardown")

    registry = FederationRegistry()
    registry.register("aaaa", _FlakyAdapter())  # type: ignore[arg-type]
    await registry.aclose()


async def _build_pulled(reference: ArtifactReference) -> PulledArtifact:
    return PulledArtifact(
        artifact=_artifact(reference.source_facility_id),
        fetch_provenance=InMemoryPullPort.make_provenance(byte_count=42),
    )
