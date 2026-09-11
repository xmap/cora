"""AssemblyLookup port: cross-aggregate query for Equipment BC's Assembly projection.

Used by cross-aggregate consumers that hold an `assembly_id` from a
loaded Fixture and need to inspect the Assembly's `presents_as` set
before committing a command.

Layer 3 consumers (per [[project-role-aggregate-design]]):
  - 3D `bind_plan_role` handler: when the candidate Asset carries
    `fixture_id`, the handler loads the Fixture (via
    `load_fixture`), then `AssemblyLookup.lookup(fixture.assembly_id)`,
    so the decider can OR-in the Assembly satisfaction path on top of
    the existing Family disjunction. Without this lookup the
    Microscope-Assembly worked example from the design memo would not
    actually work (3C's `presents_as` field would have no consumer).

## Convention

Cross-aggregate port: Equipment BC ships `PostgresAssemblyLookup`
reading `proj_equipment_assembly_summary`. Lives in
`cora.infrastructure.ports` per the existing pattern (`AssetLookup`,
`FamilyLookup`, `FacilityLookup`, `CredentialLookup`, `RoleLookup`).

## No BC imports in the port

`status` is a `Literal` alias rather than bare `str` (not the
`AssemblyStatus` StrEnum), so this port stays inside
`cora.infrastructure`'s `depends_on = []` tach contract: `Literal`
comes from `typing`, so the alias pins the enum's value set without
importing the enum. A fitness test pins the alias to the enum and
fails if the two ever drift. Adapters produce a member's `.value`,
which narrows to exactly the alias, so no cast is needed. Consumers
partition on the literal if they want to distinguish Defined /
Versioned / Deprecated.

`presents_as` is typed `frozenset[UUID]` (not `frozenset[RoleId]`);
consumers cast at their BC boundary if they need the typed identity.

## No affordance set today

Assembly does NOT carry an `affordances` field. Per the 3C state
docstring: Assembly affordances derive from the constituent Family
union at register_fixture time, not Assembly template time. The
Role satisfaction check on the Assembly path is therefore
membership-only (`role_kind in assembly.presents_as`). The
affordance-superset check stays the Family responsibility.
"""

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

AssemblyStatusValue = Literal["Defined", "Versioned", "Deprecated"]


@dataclass(frozen=True)
class AssemblyLookupResult:
    """Summary row from `proj_equipment_assembly_summary` for cross-aggregate checks.

    Carries the minimal columns the 3D bind_plan_role role_kind path
    needs to evaluate the Assembly satisfaction branch.

    `presents_as` is the set of global Role contract ids this
    Assembly advertises. Layer-3 sub-slice 3C populates this column
    incrementally via `add_assembly_presents_as` / removes via
    `remove_assembly_presents_as`.

    `status` is a `Literal` alias pinning `AssemblyStatus`'s value
    set ("Defined" / "Versioned" / "Deprecated"); the bind_plan_role
    decider accepts every status (mirrors the Family-path posture:
    deprecation is advisory, not blocking).

    `name` is the operator-readable display name; useful for
    surfacing in cross-BC error messages.
    """

    id: UUID
    name: str
    status: AssemblyStatusValue
    presents_as: frozenset[UUID]


class AssemblyLookup(Protocol):
    """Cross-aggregate port: query Equipment's Assembly projection by id."""

    async def lookup(self, assembly_id: UUID) -> AssemblyLookupResult | None:
        """Return the projection row for `assembly_id`, or None if not found.

        Returning None signals "no Assembly with that id is visible in
        the projection". The 3D bind_plan_role decider treats None as
        a missed Assembly satisfaction (the Family disjunction may
        still succeed; if it does not, PlanRoleAssetCannotPresentError
        fires).

        Assemblies in EVERY status are returned (Defined, Versioned,
        Deprecated); the consumer partitions on `status` if it needs
        to distinguish "no Assembly at all" from "Assembly exists but
        Deprecated".
        """
        ...


__all__ = ["AssemblyLookup", "AssemblyLookupResult", "AssemblyStatusValue"]
