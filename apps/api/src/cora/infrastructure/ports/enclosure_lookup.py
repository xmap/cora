"""EnclosureLookup port: cross-BC query for Enclosure BC's enclosure projection.

Used by other BCs to ask "is this enclosure permitted?" before
admitting a Run / Procedure into a controlled area. The port is
shaped around the CONSUMER's need (permit + lifecycle partitioning at
the decider boundary + id-set fan-in) and Enclosure BC provides the
Postgres adapter reading `proj_enclosure_summary`.

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
and `find_by_ids(enclosure_ids=)` for the set-returning family (fetch
the permit status of a known set of enclosure ids and fan out to
per-enclosure partitioning at the decider).

## Modern DDD alignment

Per Khononov / Cockburn / Herberto Graca: cross-BC integration at
command time should go through a port that the consumer shapes,
with the implementor providing the adapter. The replicated read
model (`proj_enclosure_summary`) is the modern recommendation over
synchronous replay of the Enclosure aggregate, because the
projection is already a denormalized cross-stream view keyed on
`enclosure_id`.

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

Every field on `EnclosureLookupResult` is typed as a bare `str` or
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
class EnclosureLookupResult:
    """Summary row from `proj_enclosure_summary` for cross-BC checks.

    Carries the minimal columns consumer deciders need to partition
    on enclosure permit + lifecycle before commit. Loaded by the
    handler via `EnclosureLookup.lookup` / `find_by_ids` and
    handed to the decider in the slice's context object (mirrors
    `FacilityLookupResult` shape).

    `permit_status` and `lifecycle` are the StrEnum values as plain
    strings (matches the projection's `TEXT` columns); the decider
    partitions on `permit_status == "Permitted"` and
    `lifecycle == "Active"`.

    `observed_at` / `source_kind` / `source_id` are optional
    epistemic provenance fields populated by
    `observe_enclosure_status`; they are `None` for
    enclosures that have never been observed (genesis-only state).
    """

    enclosure_id: UUID
    name: str
    permit_status: str
    lifecycle: str
    observed_at: str | None
    source_kind: str | None
    source_id: str | None


class EnclosureLookup(Protocol):
    """Cross-BC port: query Enclosure's projection by id or by id-set."""

    async def lookup(self, enclosure_id: UUID) -> EnclosureLookupResult | None:
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

    async def find_by_ids(self, *, enclosure_ids: frozenset[UUID]) -> list[EnclosureLookupResult]:
        """Return every Active enclosure whose `enclosure_id` is in `enclosure_ids`.

        Used by consumer deciders that hold a known set of enclosure
        ids and need their current permit status in one round trip.
        Empty input returns `[]`; an id with no projection row (or a
        Decommissioned one) contributes zero rows (the decider treats
        absence as "no enclosure restricts this", per Permit-by-default
        posture).

        Decommissioned enclosures are excluded by the adapter: a
        tombstoned enclosure does not gate runs. Permitted /
        NotPermitted / Unknown all flow through; the decider
        partitions each row on `permit_status` to distinguish
        "this enclosure does not restrict" from "enclosure is currently
        NotPermitted".
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

    `lookup` returns a synthetic `EnclosureLookupResult` with
    `permit_status="Permitted"` and `lifecycle="Active"` for any
    UUID so consumer deciders running against a kernel without the
    Enclosure BC wired see the same permitted-by-default behavior
    they had before the BC existed.

    `find_by_ids` returns the empty list because the stub holds no
    seeded rows; the decider's "no rows means no restriction" branch
    fires.

    Production deployments wire `PostgresEnclosureLookup` via
    `enclosure_lookup_factory` to replace this stub.
    """

    async def lookup(self, enclosure_id: UUID) -> EnclosureLookupResult | None:
        return EnclosureLookupResult(
            enclosure_id=enclosure_id,
            name="",
            permit_status="Permitted",
            lifecycle="Active",
            observed_at=None,
            source_kind=None,
            source_id=None,
        )

    async def find_by_ids(self, *, enclosure_ids: frozenset[UUID]) -> list[EnclosureLookupResult]:
        return []


__all__ = [
    "AlwaysPermittedEnclosureLookup",
    "EnclosureLookup",
    "EnclosureLookupResult",
]
