"""PullPort: fetch a domain-shaped artifact from a peer facility.

The port returns the verified bytes plus the parsed envelope and
lets the verify-and-apply orchestrator at
`cora.infrastructure.published_artifact` drive the per-arm recipe.
Verification + application live in the shared kernel, not on this
port; the port is the wire-and-trust seam.

Per AH#17: PullPort.fetch MUST raise
`FederationPublicationContentDriftError` if the fetched bytes do
not hash to `reference.content_hash` BEFORE returning. This is
the TOCTOU defense; signature verification cannot recover from a
content-drift attack because the signature would correctly verify
against the wrong bytes.
"""

from typing import Protocol, runtime_checkable

from cora.infrastructure.ports.federation.value_types import (
    ArtifactReference,
    PulledArtifact,
)


@runtime_checkable
class PullPort(Protocol):
    """Fetch a domain-shaped artifact by reference."""

    async def fetch(self, reference: ArtifactReference) -> PulledArtifact: ...


__all__ = ["PullPort"]
