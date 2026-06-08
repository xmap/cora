"""FacilityLookup port: cross-aggregate query for Federation BC's Facility projection.

Used by Federation BC's `register_facility` handler to validate
parent.kind=Site at cross-stream boundary (Slice 6 closes the
Slice 5 deferral). Future consumers (Slice 6 Sub-Slice B's
`add_facility_trust_anchor_credential` decider) will also consume
this port for parent-existence + tier-membership checks.

## Convention

This is a cross-aggregate port (within Federation BC; second after
`CredentialLookup` if counted by Federation-internal consumers):
one implementor (Federation BC ships `PostgresFacilityLookup` reading
`proj_federation_facility_summary` from Slice 5 Sub-Slice B), many
potential consumers (`register_facility` parent validation today;
`add_facility_trust_anchor_credential` decider in Sub-Slice B;
post-Slice-6 Equipment / Supply / Safety BC consumers when slices
7-9 land cross-BC Facility binding). Lives in
`cora.infrastructure.ports` per the existing pattern (`Authorize`,
`ClearanceLookup`, `CautionLookup`, `SupplyLookup`, `SecretStore`,
`CredentialLookup`).

The port is shaped around the CONSUMER's need: `register_facility`
decider needs "what is this parent Facility's kind, for the
parent.kind=Site invariant at registration time". Adapters translate
the projection's columns to this shape.

## Modern DDD alignment

Per Khononov / Cockburn / Herberto Graca: cross-aggregate integration
at command time should go through a port that the consumer shapes,
with the implementor providing the adapter. The replicated read model
(`proj_federation_facility_summary`) is the modern recommendation over
synchronous replay of the Facility aggregate, because the projection
is already a denormalized cross-stream view + already covers the
two-tier identity (id + code).

## No BC imports in the port

`kind` and `status` are typed as `str` (not the Federation BC's
`FacilityKind` / `FacilityStatus` StrEnums) so this port stays
inside `cora.infrastructure`'s `depends_on = []` tach contract. The
values match the StrEnum string values; deciders partition by literal
comparison (`kind == "Site"`, `status == "Active"`).

`trust_anchor_credential_ids` is typed `frozenset[UUID]` (not
`frozenset[CredentialId]`) for the same tach reason; Federation BC
callers cast at the boundary if they want the NewType discipline.

`id` is typed `UUID` not `FacilityId` for the same reason; consumers
cast at the Federation BC boundary.

`code` is typed `FacilityCode` per the locked two-tier facility
identity design: `FacilityCode` lives in `cora.infrastructure`
itself (post Slice 3 hoist) and is the cross-deployment convergent
identity. The adapter constructs it from the raw `TEXT` column.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.shared.facility_code import FacilityCode


@dataclass(frozen=True)
class FacilityLookupResult:
    """Summary row from `proj_federation_facility_summary` for cross-aggregate checks.

    Carries the minimal columns the Federation deciders need to validate
    cross-aggregate invariants before commit. Loaded by the handler via
    `FacilityLookup.lookup` and handed to the decider in the slice's
    context object (mirrors `CredentialLookupResult` shape).

    `kind` and `status` are the StrEnum values as plain strings (matches
    the projection's `TEXT` columns); the decider partitions on
    `kind == "Site"` / `"Area"` and `status == "Active"`.

    `code` is a `FacilityCode` value object per the two-tier
    facility-identity design; the adapter constructs the VO from the raw
    `TEXT` column. A malformed code at the projection-row tier raises
    `InvalidFacilityCodeError` at adapter construction time, which
    surfaces upstream as a port-level integrity error.

    `trust_anchor_credential_ids` is the projection's JSONB array of
    credential id strings, materialized as a `frozenset[UUID]`. Empty
    for `kind=Area` Facilities (Area inherits the parent Site's trust
    posture).
    """

    id: UUID
    code: FacilityCode
    kind: str
    status: str
    trust_anchor_credential_ids: frozenset[UUID]


class FacilityLookup(Protocol):
    """Cross-aggregate port: query Federation's facility projection by id."""

    async def lookup(self, facility_id: UUID) -> FacilityLookupResult | None:
        """Return the projection row for `facility_id`, or None if not found.

        Returning None signals "no Facility with that id is visible in
        the projection". Callers (`register_facility` parent-validation,
        future `add_facility_trust_anchor_credential` decider)
        translate None to the appropriate domain error
        (`FacilityParentNotFoundError` per the start_run ->
        PlanNotFoundError precedent) at the decider boundary.

        Facilities in EVERY status are returned (Active, Decommissioned);
        the decider partitions on `status` to distinguish "no facility
        at all" from "facility exists but Decommissioned".
        """
        ...


__all__ = ["FacilityLookup", "FacilityLookupResult"]
