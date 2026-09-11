"""FacilityLookup port: cross-aggregate query for Federation BC's Facility projection.

Used by Federation BC's `register_facility` handler to validate
parent.kind=Site at cross-stream boundary (Slice 6 closes the
Slice 5 deferral), Slice 6 Sub-Slice B's
`add_facility_trust_anchor_credential` decider for parent-existence
+ tier-membership checks, and Slice 7 cross-BC consumers
(`register_supply` resolves `command.facility_code` to a
`FacilityLookupResult` via the `lookup_by_code` arm) for
cross-deployment convergent-identity binding.

## Convention

This is a cross-aggregate port (within Federation BC; second after
`CredentialLookup` if counted by Federation-internal consumers):
one implementor (Federation BC ships `PostgresFacilityLookup` reading
`proj_federation_facility_summary` from Slice 5 Sub-Slice B), many
consumers (`register_facility` parent validation,
`add_facility_trust_anchor_credential` decider, and cross-BC
Supply / Asset / Safety binding in slices 7-9). Lives in
`cora.infrastructure.ports` per the existing pattern (`Authorize`,
`ClearanceLookup`, `CautionLookup`, `SupplyLookup`, `SecretStore`,
`CredentialLookup`).

## Two access methods

`lookup(facility_id)` keys by the internal-opaque UUID and serves
Federation BC's intra-BC parent-validation arms. `lookup_by_code`
keys by the cross-deployment convergent slug and serves cross-BC
binding sites where the consumer carries the bare-str slug across
the wire (Slice 7+; Permit / Credential / Seal aggregate state
already keys on `FacilityCode`). Both return the same
`FacilityLookupResult` shape with the full projection row; callers
partition on `kind` or `status` as needed.

## Modern DDD alignment

Per Khononov / Cockburn / Herberto Graca: cross-aggregate integration
at command time should go through a port that the consumer shapes,
with the implementor providing the adapter. The replicated read model
(`proj_federation_facility_summary`) is the modern recommendation over
synchronous replay of the Facility aggregate, because the projection
is already a denormalized cross-stream view + already covers the
two-tier identity (id + code).

## No BC imports in the port

`kind` stays typed `str` (not Federation BC's `FacilityKind`
StrEnum) and `status` is a `Literal` alias pinning Federation BC's
`FacilityStatus` StrEnum value set (not the StrEnum itself), so this
port stays inside `cora.infrastructure`'s `depends_on = []` tach
contract: `Literal` comes from `typing`, so the alias pins the
enum's value set without importing the enum. A fitness test pins
the alias to the enum and fails if the two ever drift. `kind`'s
values match the StrEnum's string values; deciders partition by
literal comparison (`kind == "Site"`, `status == "Active"`).

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

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from cora.shared.facility_code import FacilityCode

FacilityStatusValue = Literal["Active", "Decommissioned"]


@dataclass(frozen=True)
class FacilityLookupResult:
    """Summary row from `proj_federation_facility_summary` for cross-aggregate checks.

    Carries the minimal columns the Federation deciders need to validate
    cross-aggregate invariants before commit. Loaded by the handler via
    `FacilityLookup.lookup` and handed to the decider in the slice's
    context object (mirrors `CredentialLookupResult` shape).

    `kind` is the `FacilityKind` StrEnum value as a plain string;
    `status` is a `Literal` alias pinning `FacilityStatus`'s value set
    (both match the projection's `TEXT` columns). The decider
    partitions on `kind == "Site"` / `"Area"` and `status == "Active"`.

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
    status: FacilityStatusValue
    trust_anchor_credential_ids: frozenset[UUID]


class FacilityLookup(Protocol):
    """Cross-aggregate port: query Federation's facility projection by id."""

    async def lookup(self, facility_id: UUID) -> FacilityLookupResult | None:
        """Return the projection row for `facility_id`, or None if not found.

        Returning None signals "no Facility with that id is visible in
        the projection". Callers (`register_facility` parent-validation,
        `add_facility_trust_anchor_credential` decider) translate None
        to the appropriate domain error (`FacilityParentNotFoundError`
        per the start_run -> PlanNotFoundError precedent) at the decider
        boundary.

        Facilities in EVERY status are returned (Active, Decommissioned);
        the decider partitions on `status` to distinguish "no facility
        at all" from "facility exists but Decommissioned".
        """
        ...

    async def lookup_by_code(self, code: FacilityCode) -> FacilityLookupResult | None:
        """Return the projection row for `code`, or None if not found.

        Cross-deployment convergent-identity arm: callers carry the
        bare-str slug across the wire (Slice 7 `register_supply` is
        the first cross-BC consumer) and resolve it to the full
        projection row before threading into the decider. Same
        None-on-missing + every-status-returned contract as `lookup`.
        Code uniqueness is enforced by the projection's UNIQUE INDEX
        on `code`, so at most one row matches; the adapter applies
        `LIMIT 1` defensively.
        """
        ...

    async def list_active(self) -> Sequence[FacilityLookupResult]:
        """Return every Active facility (status='Active').

        Used by lifespan-time seeding hooks (Safety BC's
        `seed_clearance_templates` iterates one template-per-form-type
        per Active facility). Decommissioned facilities are filtered out:
        seeds are pre-flight gates, not historical replays. Order is
        implementation-defined; callers must not rely on it.

        Returns an empty Sequence when no Active facilities are
        registered (consistent with `lookup` returning None on miss --
        the seed hook short-circuits naturally).
        """
        ...


__all__ = ["FacilityLookup", "FacilityLookupResult", "FacilityStatusValue"]
