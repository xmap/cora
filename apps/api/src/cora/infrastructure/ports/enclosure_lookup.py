"""EnclosureLookup port: cross-BC query for Enclosure BC's enclosure projection.

Used by other BCs to ask "is this enclosure permitted?" before
admitting an Asset / Run / Procedure into a controlled area. The
port is shaped around the CONSUMER's need (permit + lifecycle
partitioning at the decider boundary + asset-binding fan-out) and
Enclosure BC provides the Postgres adapter reading
`proj_enclosure_summary`.

## Convention

This is a cross-BC port (one implementor, many potential consumers):
Enclosure BC ships `PostgresEnclosureLookup` reading
`proj_enclosure_summary` from the projection (per the prior register slice); consumers in
Run / Procedure / Operation BCs translate `None` (no row),
`lifecycle != "Active"` (tombstoned), or `permit_status !=
"Permitted"` (not currently permitted) to the appropriate domain
error at the decider boundary. Lives in `cora.infrastructure.ports`
per the existing pattern (`Authorize`, `ClearanceLookup`,
`CautionLookup`, `SupplyLookup`, `CredentialLookup`,
`FacilityLookup`).

The port carries two arms because the two consumer shapes are
distinct: `lookup(enclosure_id)` for the id-keyed single-row read,
and `find_for_assets(asset_ids=)` for the set-returning Supply /
Clearance family (gather every enclosure contained by any of these
Assets, fan out to per-asset partitioning at the decider).

## Modern DDD alignment

Per Khononov / Cockburn / Herberto Graca: cross-BC integration at
command time should go through a port that the consumer shapes,
with the implementor providing the adapter. The replicated read
model (`proj_enclosure_summary`) is the modern recommendation over
synchronous replay of the Enclosure aggregate, because the
projection is already a denormalized cross-stream view + already
covers the asset-binding fan-out via its `containing_asset_id`
column.

## Two orthogonal status axes

Enclosure has a two-axis FSM per the aggregate state's locked
design (`cora.enclosure.aggregates.enclosure.state`):

  - `permit_status` (operational): `"Permitted"` / `"NotPermitted"`
    / `"Unknown"`. Mutated by Monitor-driven observations.
  - `lifecycle` (structural): `"Active"` / `"Decommissioned"`.
    `Decommissioned` is terminal; `permit_status` is preserved
    as audit (a tombstoned enclosure can still read
    `permit_status="Permitted"` from before it was retired).

Both axes reach the port surface as bare `str`. The decider's
gate check is `lifecycle == "Active" AND permit_status ==
"Permitted"`.

## No BC imports in the port

Every field on `EnclosureReference` is typed as a bare `str` or
bare `UUID` (not the Enclosure BC's `EnclosureId` /
`EnclosurePermitStatus` / `EnclosureLifecycle` types) so this
port stays inside `cora.infrastructure.ports`'s `depends_on = []`
tach contract. The `permit_status` / `lifecycle` / `source_kind`
values match the StrEnum string values; deciders partition by
literal comparison. Enclosure BC callers cast at the boundary if
they want the NewType discipline.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class EnclosureReference:
    """Summary row from `proj_enclosure_summary` for cross-BC checks.

    Carries the minimal columns consumer deciders need to partition
    on enclosure permit + lifecycle before commit. Loaded by the
    handler via `EnclosureLookup.lookup` / `find_for_assets` and
    handed to the decider in the slice's context object (mirrors
    `FacilityLookupResult` shape).

    `permit_status` and `lifecycle` are the StrEnum values as plain
    strings (matches the projection's `TEXT` columns); the decider
    partitions on `permit_status == "Permitted"` and
    `lifecycle == "Active"`.

    `containing_asset_id` is the cross-BC opaque pointer to the
    Asset that physically contains the Enclosure. Carried as a bare
    `UUID` per the port's `depends_on = []` tach contract.

    `observed_at` / `source_kind` / `source_id` are optional
    epistemic provenance fields populated by
    `observe_enclosure_status`; they are `None` for
    enclosures that have never been observed (genesis-only state).
    """

    enclosure_id: UUID
    name: str
    containing_asset_id: UUID
    permit_status: str
    lifecycle: str
    observed_at: str | None
    source_kind: str | None
    source_id: str | None


class EnclosureLookup(Protocol):
    """Cross-BC port: query Enclosure's projection by id or by asset binding."""

    async def lookup(self, enclosure_id: UUID) -> EnclosureReference | None:
        """Return the projection row for `enclosure_id`, or None if not found.

        Returning None signals "no Enclosure with that id is visible
        in the projection". Callers translate None to the appropriate
        domain error (`EnclosureNotFoundError` per the start_run ->
        PlanNotFoundError precedent) at the decider boundary.

        Enclosures in EVERY status are returned (Permitted,
        NotPermitted, Unknown) and EVERY lifecycle (Active,
        Decommissioned); the decider partitions on both axes to
        distinguish "no enclosure at all" from "enclosure exists but
        tombstoned" from "enclosure exists, Active, but not currently
        permitted".
        """
        ...

    async def find_for_assets(self, *, asset_ids: frozenset[UUID]) -> list[EnclosureReference]:
        """Return every Active enclosure whose `containing_asset_id` is in `asset_ids`.

        Used by consumer deciders that hold a set of Asset ids (a Run's
        equipment, a Procedure's targets) and need to know which
        enclosures gate those Assets. Empty input returns `[]`; an
        Asset that contains no enclosure contributes zero rows (the
        decider treats absence as "no enclosure restricts this Asset",
        per Permit-by-default posture).

        Decommissioned enclosures are excluded by the adapter: a
        tombstoned enclosure does not gate runs. Permitted /
        NotPermitted / Unknown all flow through; the decider
        partitions each row on `permit_status` to distinguish
        "no enclosure binds this Asset" from "enclosure binds it but
        is currently NotPermitted".
        """
        ...


class AlwaysPermittedEnclosureLookup:
    """Stub: every enclosure id resolves to a synthetic Active+Permitted row.

    Default `EnclosureLookup` injected by `build_kernel` when no
    production factory is wired, and the default for tests that don't
    care about enclosure gating. Mirrors the abstract-adjective stub
    family (`AlwaysQuietCautionLookup`, `AlwaysCoveredClearanceLookup`,
    `AllSatisfiedSupplyLookup`, `AlwaysEmptyCapabilityLookup`): the
    name describes the always-pass posture rather than echoing the
    `Permitted` status string.

    `lookup` returns a synthetic `EnclosureReference` with
    `permit_status="Permitted"` and `lifecycle="Active"` for any
    UUID so consumer deciders running against a kernel without the
    Enclosure BC wired see the same permitted-by-default behavior
    they had before the BC existed. `containing_asset_id` is set to
    the queried `enclosure_id` (deterministic, harmless: the stub
    holds no real binding state, and `find_for_assets` is empty so
    the synthetic self-binding is never observed).

    `find_for_assets` returns the empty list because no Asset has any
    enclosure binding in the absence of seeded data; the decider's
    "no rows means no restriction" branch fires.

    Production deployments wire `PostgresEnclosureLookup` via
    `enclosure_lookup_factory` to replace this stub.
    """

    async def lookup(self, enclosure_id: UUID) -> EnclosureReference | None:
        return EnclosureReference(
            enclosure_id=enclosure_id,
            name="",
            containing_asset_id=enclosure_id,
            permit_status="Permitted",
            lifecycle="Active",
            observed_at=None,
            source_kind=None,
            source_id=None,
        )

    async def find_for_assets(self, *, asset_ids: frozenset[UUID]) -> list[EnclosureReference]:
        return []


__all__ = [
    "AlwaysPermittedEnclosureLookup",
    "EnclosureLookup",
    "EnclosureReference",
]
