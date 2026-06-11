"""FamilyLookup port: cross-aggregate query for Equipment BC's Family projection.

Used by cross-BC consumers that hold a `family_id` from the wire
and need to validate the Family exists (and inspect its
`affordances` + `presents_as` for satisfaction checks) before
committing a command.

Layer 3 consumers (per [[project-role-aggregate-design]]):
  - 3D `bind_plan_role` handler: walks Asset.family_ids ->
    FamilyLookup.lookup -> presents_as ∩ affordance-superset using
    Lock 17 ANY-single-family disjunction. The handler loads each
    Family's projection row at the edge and threads the results
    into the decider.

3B ships the port + adapters here so the cross-BC interface lands
in the same slice that introduces the `presents_as` column.

## Convention

This is a cross-aggregate port (within Equipment BC; second after
`AssetLookup`): Equipment BC ships `PostgresFamilyLookup` reading
`proj_equipment_family_summary`. Lives in
`cora.infrastructure.ports` per the existing pattern (`AssetLookup`,
`FacilityLookup`, `CredentialLookup`, `RoleLookup`, etc.).

## No BC imports in the port

`affordances` is typed as `frozenset[str]` (NOT
`frozenset[Affordance]`) so this port stays inside
`cora.infrastructure`'s `depends_on = []` tach contract. The values
match the Affordance StrEnum string values; consumer deciders cast
to typed enums at their BC boundary if they want the discipline.

`status` is typed `str` (not the `FamilyStatus` StrEnum) for the
same tach reason. Consumers partition on the literal
("Defined" / "Versioned" / "Deprecated").

`presents_as` is typed `frozenset[UUID]` (not `frozenset[RoleId]`);
consumers cast at their BC boundary if they need the typed
identity.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class FamilyLookupResult:
    """Summary row from `proj_equipment_family_summary` for cross-aggregate checks.

    Carries the minimal columns cross-BC consumers need to validate
    cross-aggregate invariants before commit. Loaded by the handler
    via `FamilyLookup.lookup` and handed to the decider in the
    slice's context object (mirrors `RoleLookupResult` shape).

    `affordances` is the Family's current Affordance value strings
    (post-version-replace semantics: state always holds the latest
    declaration). 3D's `bind_plan_role` checks superset of the
    Role's `required_affordances`.

    `presents_as` is the set of global Role contract ids this
    Family advertises. Layer-3 sub-slice 3B populates this column
    incrementally via `add_family_presents_as` / removes via
    `remove_family_presents_as`.

    `status` is the FSM stage as a plain string ("Defined" /
    "Versioned" / "Deprecated"); consumer decides whether
    Deprecated Families are acceptable bindings (today's posture:
    accept; deprecation is advisory).

    `name` is the operator-readable display name; useful for
    surfacing in cross-BC error messages.
    """

    id: UUID
    name: str
    status: str
    affordances: frozenset[str]
    presents_as: frozenset[UUID]


class FamilyLookup(Protocol):
    """Cross-aggregate port: query Equipment's Family projection by id."""

    async def lookup(self, family_id: UUID) -> FamilyLookupResult | None:
        """Return the projection row for `family_id`, or None if not found.

        Returning None signals "no Family with that id is visible in
        the projection". Callers translate None to the appropriate
        domain error at the decider boundary (3D's `bind_plan_role`
        raises a Plan-side `PlanRoleFamilyNotResolvableError`).

        Families in EVERY status are returned (Defined, Versioned,
        Deprecated); the consumer partitions on `status` if it needs
        to distinguish "no Family at all" from "Family exists but
        Deprecated" (today's posture: accept all statuses).
        """
        ...


__all__ = ["FamilyLookup", "FamilyLookupResult"]
