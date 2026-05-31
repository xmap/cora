"""PublishPort: publish a domain-shaped artifact to the federation surface.

Per the federation port-tier design, the port speaks
`PublishedArtifact` + `PublishReceipt`; wire-tier vocabulary
(DSSE, COSE, Sigstore, Rekor, SCITT, CBOR) is owned by the
adapters. Adapters land at `cora/federation/adapters/*`.

An in-memory adapter ships as the test-tier substitute in a
follow-up iteration; production wire-tier adapters land later with
the matching library pins.
"""

from typing import Protocol, runtime_checkable

from cora.infrastructure.ports.federation.value_types import (
    PublishedArtifact,
    PublishReceipt,
)


@runtime_checkable
class PublishPort(Protocol):
    """Publish a domain-shaped artifact to the federation surface."""

    async def publish(self, artifact: PublishedArtifact) -> PublishReceipt: ...


__all__ = ["PublishPort"]
