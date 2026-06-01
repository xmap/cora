"""In-memory PermitLookup adapter for tests and dev fixtures.

Dict-backed, mirrors the InMemoryCredentialLookup precedent. Test
entry verb is `register(...)` which primes a (peer_facility_id,
artifact_kind, direction) -> PermitLookupResult lookup; the
production PostgresPermitLookup reads the same projection columns
from `proj_federation_permit_summary`.
"""

from uuid import UUID

from cora.infrastructure.ports.federation.permit_lookup import (
    PermitLookup,
    PermitLookupResult,
)


def _key(peer_facility_id: str, artifact_kind: str, direction: str) -> tuple[str, str, str]:
    return (peer_facility_id, artifact_kind, direction)


class InMemoryPermitLookup(PermitLookup):
    """Dict-backed PermitLookup with `register` test entry point.

    Construct empty, call `register(...)` for each permit the test
    needs, then hand the adapter to the handler under test. The
    seeded permits survive across `lookup_outbound` / `lookup_inbound`
    calls until `clear()` is invoked.
    """

    def __init__(self) -> None:
        self._permits: dict[tuple[str, str, str], PermitLookupResult] = {}

    def register(
        self,
        *,
        peer_facility_id: str,
        artifact_kind: str,
        direction: str,
        result: PermitLookupResult,
    ) -> None:
        """Seed a permit for a (peer, artifact_kind, direction) lookup key."""
        self._permits[_key(peer_facility_id, artifact_kind, direction)] = result

    def register_outbound(
        self,
        *,
        peer_facility_id: str,
        artifact_kind: str,
        permit_id: UUID,
        status: str = "Active",
        abi_tier_floor: str = "Stable",
        current_version: int = 1,
    ) -> PermitLookupResult:
        """Convenience: seed an outbound permit; returns the seeded result for assertions."""
        result = PermitLookupResult(
            permit_id=permit_id,
            peer_facility_id=peer_facility_id,
            direction="Outbound",
            status=status,
            abi_tier_floor=abi_tier_floor,
            current_version=current_version,
        )
        self.register(
            peer_facility_id=peer_facility_id,
            artifact_kind=artifact_kind,
            direction="Outbound",
            result=result,
        )
        return result

    def register_inbound(
        self,
        *,
        peer_facility_id: str,
        artifact_kind: str,
        permit_id: UUID,
        status: str = "Active",
        abi_tier_floor: str = "Stable",
        current_version: int = 1,
    ) -> PermitLookupResult:
        """Convenience: seed an inbound permit; returns the seeded result for assertions."""
        result = PermitLookupResult(
            permit_id=permit_id,
            peer_facility_id=peer_facility_id,
            direction="Inbound",
            status=status,
            abi_tier_floor=abi_tier_floor,
            current_version=current_version,
        )
        self.register(
            peer_facility_id=peer_facility_id,
            artifact_kind=artifact_kind,
            direction="Inbound",
            result=result,
        )
        return result

    async def lookup_outbound(
        self, peer_facility_id: str, artifact_kind: str
    ) -> PermitLookupResult | None:
        return self._permits.get(_key(peer_facility_id, artifact_kind, "Outbound"))

    async def lookup_inbound(
        self, peer_facility_id: str, artifact_kind: str
    ) -> PermitLookupResult | None:
        return self._permits.get(_key(peer_facility_id, artifact_kind, "Inbound"))

    def clear(self) -> None:
        self._permits.clear()


__all__ = ["InMemoryPermitLookup"]
