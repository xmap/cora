"""In-memory PullPort adapter for tests and dev fixtures.

Dict-backed, no sockets. Test entry verbs:

  - `set_pull_response(reference, pulled)`: prime a fetch response.
  - `simulate_registry_unreachable(source_facility_id, opened_at)`:
    next `fetch` for that facility raises `FederationCircuitOpenError`.
  - `simulate_content_drift(reference)`: next `fetch` of that
    reference returns drifted bytes that hash to something other
    than the reference's `content_hash`, triggering
    `FederationPublicationContentDriftError` BEFORE returning.

Per AH#17: `fetch` MUST raise `FederationPublicationContentDriftError`
when fetched bytes do not hash to `reference.content_hash`. The
in-memory adapter implements the same invariant via the simulate
verb to make TOCTOU defenses testable end-to-end.
"""

import contextlib
import hashlib
from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.federation import (
    ArtifactReference,
    FederationCircuitOpenError,
    FederationPublicationContentDriftError,
    FetchProvenance,
    PulledArtifact,
)


def _reference_key(reference: ArtifactReference) -> tuple[bytes, str]:
    return (reference.content_hash, reference.payload_type)


class InMemoryPullPort:
    """Dict-backed PullPort with simulate_* test entry points."""

    def __init__(self) -> None:
        self._responses: dict[tuple[bytes, str], PulledArtifact] = {}
        self._unreachable_facilities: dict[UUID, datetime] = {}
        self._drift_references: set[tuple[bytes, str]] = set()

    async def fetch(self, reference: ArtifactReference) -> PulledArtifact:
        opened_at = self._unreachable_facilities.get(reference.source_facility_id)
        if opened_at is not None:
            raise FederationCircuitOpenError(
                source_facility_id=reference.source_facility_id, opened_at=opened_at
            )
        key = _reference_key(reference)
        if key in self._drift_references:
            fetched_bytes = b"DRIFT:" + reference.content_hash
            raise FederationPublicationContentDriftError(
                reference_content_hash=reference.content_hash,
                fetched_content_hash=hashlib.sha256(fetched_bytes).digest(),
            )
        response = self._responses.get(key)
        if response is None:
            raise KeyError(
                f"InMemoryPullPort has no response primed for "
                f"reference={reference!r}; call set_pull_response first"
            )
        return response

    def set_pull_response(self, reference: ArtifactReference, pulled: PulledArtifact) -> None:
        self._responses[_reference_key(reference)] = pulled

    def simulate_registry_unreachable(self, source_facility_id: UUID, opened_at: datetime) -> None:
        self._unreachable_facilities[source_facility_id] = opened_at

    def simulate_content_drift(self, reference: ArtifactReference) -> None:
        self._drift_references.add(_reference_key(reference))

    def clear_simulations(self) -> None:
        self._unreachable_facilities.clear()
        self._drift_references.clear()

    @staticmethod
    def make_provenance(byte_count: int) -> FetchProvenance:
        """Helper for tests that need a non-zero FetchProvenance shape."""
        return FetchProvenance(
            locator_used="in-memory://x",
            wire_content_type="application/dsse+json",
            fetch_duration_ms=1,
            byte_count=byte_count,
        )

    async def aclose(self) -> None:
        with contextlib.suppress(Exception):
            self._responses.clear()
            self._unreachable_facilities.clear()
            self._drift_references.clear()


__all__ = ["InMemoryPullPort"]
