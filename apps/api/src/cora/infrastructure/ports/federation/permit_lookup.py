"""PermitLookup port: cross-BC query for Federation BC's permit projection.

Used by per-BC publish/pull slice handlers to resolve the matching
outbound-direction or inbound-direction Permit at command time,
before composing a `FederationTrustContext` for SignaturePort calls
or assembling the cross-BC `append_streams` over the Permit stream.

## Convention

Mirrors the existing CredentialLookup precedent: cross-BC port
shaped around the CONSUMER's need ("what permit authorizes this
publication / pull?"), Federation BC ships the
`PostgresPermitLookup` adapter reading
`proj_federation_permit_summary`, and the in-memory adapter at
`cora.federation.adapters.in_memory_permit_lookup` is the test
default until real federation peers connect.

## No BC imports in the port

`direction` and `status` are typed as `str` so this port stays
inside `cora.infrastructure`'s `depends_on = []` tach contract.
The string values match the BC-tier `Direction` and `PermitStatus`
StrEnums (`Outbound | Inbound`, `Defined | Active | Suspended | Revoked`).
Consumers compare via literal equality on the strings.

## Why outbound/inbound on a single port

The per-BC publish slice needs an outbound permit; the per-BC pull
slice needs an inbound permit. The two lookups share the same
projection table and almost-identical resolution logic (key on
peer_facility_id + artifact_kind + direction); collapsing onto one
port keeps both slice handlers reading from one shipped adapter
instead of two. Per consumer-shaped port discipline, both shapes
land here.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True)
class PermitLookupResult:
    """Summary row from `proj_federation_permit_summary` for slice handlers.

    Carries the minimal columns a per-BC publish / pull handler needs
    to compose a FederationTrustContext and stage the cross-BC
    `append_streams` over the Permit stream. The loaded version is
    surfaced as `current_version` so the handler can pass it as the
    expected_version to `append_streams` without re-loading the
    full Permit stream.
    """

    permit_id: UUID
    peer_facility_id: str
    direction: str
    status: str
    abi_tier_floor: str
    current_version: int


@runtime_checkable
class PermitLookup(Protocol):
    """Cross-BC port: query Federation's permit projection by direction.

    `lookup_outbound` is the publish-side query (matches a peer-
    facility id + artifact kind to the outbound Permit that
    authorizes publishing to that peer); `lookup_inbound` is the
    pull-side query (matches a peer-facility id + artifact kind to
    the inbound Permit that authorizes pulling from that peer).
    Both return None when no matching active permit exists.
    """

    async def lookup_outbound(
        self, peer_facility_id: str, artifact_kind: str
    ) -> PermitLookupResult | None: ...

    async def lookup_inbound(
        self, peer_facility_id: str, artifact_kind: str
    ) -> PermitLookupResult | None: ...


__all__ = ["PermitLookup", "PermitLookupResult"]
