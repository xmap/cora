"""CredentialLookup port: cross-BC query for Federation BC's credential projection.

Used by Federation BC's `initialize_seal` and `rotate_seal_online_key`
handlers to gate Seal init / rotation on cross-aggregate purpose binding
(the referenced Credential's purpose must match the seal slot) and the
status-Active invariant (Rotating or Revoked secrets cannot back a Seal).

## Convention

This is a cross-BC port (third after `Authorize` and `ClearanceLookup`):
one implementor (Federation BC ships `PostgresCredentialLookup` reading
`proj_federation_credential_summary`), many potential consumers
(Seal slices today; possibly other Federation slices later). Lives in
`cora.infrastructure.ports` per the existing pattern (`Authorize`,
`ClearanceLookup`, `CautionLookup`, `SupplyLookup`, `SecretStore`, ...).

The port is shaped around the CONSUMER's need: Seal deciders need
"what is this Credential's purpose and status, for the purpose-binding
and Active-only checks at commit time". Adapters translate the
projection's columns to this shape.

## Modern DDD alignment

Per Khononov / Cockburn / Herberto Graca: cross-BC integration at
command time should go through a port that the consumer shapes, with
the implementor providing the adapter. The replicated read model
(`proj_federation_credential_summary`) is the modern recommendation
over synchronous replay of the upstream Credential aggregate, because
the projection is already a denormalized cross-stream view.

## No BC imports in the port

`purpose` stays typed `str` (not Federation BC's `CredentialPurpose`
StrEnum) and `status` is a `Literal` alias pinning Federation BC's
`CredentialStatus` StrEnum value set (not the StrEnum itself), so
this port stays inside `cora.infrastructure`'s `depends_on = []`
tach contract: `Literal` comes from `typing`, so the alias pins the
enum's value set without importing the enum. A fitness test pins
the alias to the enum and fails if the two ever drift. `purpose`'s
values match the StrEnum's string values; deciders partition by
literal comparison (`purpose == "SealOnlineSigning"`, `status ==
"Active"`).

`facility_id` is typed `FacilityCode` (not bare `str`) per the locked
two-tier facility identity design ([[project-structural-scope-design]]
Slice 3 "FacilityCode VO + port-surface migration"). The VO is the
cross-deployment convergent identity for a facility; the projection
adapter constructs it from the raw `TEXT` column, and consumers
extract `.value` only at the boundary where they meet aggregate-stored
bare-string `facility_id` payloads (event payloads on disk remain
strings; the VO is in-memory only at the port surface).
"""

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from cora.shared.facility_code import FacilityCode

CredentialStatusValue = Literal["Active", "Rotating", "Revoked"]


@dataclass(frozen=True)
class CredentialLookupResult:
    """Summary row from `proj_federation_credential_summary` for purpose-binding checks.

    Carries the minimal columns the seal deciders need to validate
    cross-aggregate purpose binding before commit. Loaded by the
    handler via `CredentialLookup.lookup` and handed to the decider in
    the seal-slice context object.

    `purpose` is the `CredentialPurpose` StrEnum value as a plain
    string; `status` is a `Literal` alias pinning `CredentialStatus`'s
    value set (both match the projection's `TEXT` columns). The
    decider partitions on `purpose == "SealOnlineSigning"` /
    `"SealOfflineRoot"` and `status == "Active"`.

    `facility_id` is a `FacilityCode` value object per the two-tier
    facility-identity design; the adapter constructs the VO from the
    raw `TEXT` column. A malformed code at the projection-row tier
    raises `InvalidFacilityCodeError` at adapter construction time,
    which surfaces upstream as a port-level integrity error.
    """

    id: UUID
    facility_id: FacilityCode
    purpose: str
    status: CredentialStatusValue


class CredentialLookup(Protocol):
    """Cross-BC port: query Federation's credential projection for purpose binding."""

    async def lookup(self, credential_id: UUID) -> CredentialLookupResult | None:
        """Return the projection row for `credential_id`, or None if not found.

        Returning None signals "no Credential with that id is visible
        in the projection". Callers (Seal deciders) translate None to
        the appropriate domain error (`CredentialNotFoundError` per
        the start_run -> PlanNotFoundError precedent) at the decider
        boundary.

        Credentials in EVERY status are returned (Active, Rotating,
        Revoked); the decider partitions on `status == "Active"` so it
        can distinguish "no credential at all" from "credential exists
        but Rotating/Revoked".
        """
        ...
