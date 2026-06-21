"""RoleLookup port: cross-aggregate query for Equipment BC's Role projection.

Used by cross-BC and cross-aggregate consumers that hold a `RoleId`
from the wire and need to validate the Role exists (and inspect its
`required_affordances` for the satisfaction superset check) before
committing a command.

Layer 3 consumers (per [[project-role-aggregate-design]]):
  - 3B `add_family_presents_as` decider: validates the role_id
    resolves AND verifies `Family.affordances` superset
    `Role.required_affordances` (`FamilyCannotPresentAsError` on
    failure).
  - 3C `add_assembly_presents_as` decider: validates role_id
    resolves (affordance-superset check deferred to register_fixture
    layer; Assembly affordances derive from constituent Family union
    at fixture time, not template time).
  - 3D `add_method_required_role` handler: handler-side precondition
    that `role_kind` resolves (RoleNotFoundError); kept at handler
    edge so the decider signature stays at 3 kwargs and the
    `make_update_handler` factory contract is preserved.
  - 3D `bind_plan_role` handler: walks Asset.family_ids ->
    a gather of FamilyLookup.lookup (one call per family) ->
    RoleLookup.lookup for the role_kind satisfaction path. The role's
    required_affordances drive the per-Family superset comparison
    (Lock 17 ANY-single-family disjunction).
  - 3E `update_capability_suggested_roles` handler: validates every
    proposed RoleId resolves (Lock 10 documentation-only event;
    existence is the only gate).

## Convention

This is a cross-aggregate port (Equipment BC ships the production
adapter `PostgresRoleLookup` reading `proj_equipment_role_summary`;
Equipment + Recipe + future BC handlers consume it). Lives in
`cora.infrastructure.ports` per the existing pattern (`AssetLookup`,
`FacilityLookup`, `CredentialLookup`, etc.).

## No BC imports in the port

`required_affordances` is typed as `frozenset[str]` (NOT
`frozenset[Affordance]`) so this port stays inside
`cora.infrastructure`'s `depends_on = []` tach contract. The values
match the Affordance StrEnum string values; consumer deciders cast
back to typed enums at their BC boundary if they want the
discipline.

`id` is typed `UUID` (not `RoleId` NewType) for the same reason:
RoleId lives at `cora.equipment.aggregates._value_types` and would
cross the infrastructure-tier boundary. Consumers wrap at their BC
edge if they need the typed identity.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class RoleLookupResult:
    """Summary row from `proj_equipment_role_summary` for cross-aggregate checks.

    Carries the minimal columns cross-BC consumers need to validate
    cross-aggregate invariants before commit. Loaded by the handler
    via `RoleLookup.lookup` and handed to the decider in the slice's
    context object (mirrors `FacilityLookupResult` / `AssetLookupResult`
    shape).

    `required_affordances` is the Affordance-value-string set the
    satisfying Family / Assembly affordances MUST superset. Carried as
    `frozenset[str]` (port stays free of Equipment-BC enum imports);
    consumers compare via string equality or cast to typed enums at
    their BC boundary.

    `optional_affordances` is informative (3A): Method authoring time
    surfaces but no decider gates on it at this slice. Carried for
    parity with `required_affordances`; future slices that gate on
    optional-set membership do so at the consumer boundary.

    `name` is the operator-readable display name (1-200 chars per
    `RoleName` VO); useful for surfacing in cross-BC error messages
    that name the Role operators recognize rather than a bare UUID.
    """

    id: UUID
    name: str
    required_affordances: frozenset[str]
    optional_affordances: frozenset[str]


class RoleLookup(Protocol):
    """Cross-aggregate port: query Equipment's Role projection by id."""

    async def lookup(self, role_id: UUID) -> RoleLookupResult | None:
        """Return the projection row for `role_id`, or None if not found.

        Returning None signals "no Role with that id is visible in the
        projection". Callers (3B add_family_presents_as decider,
        3D bind_plan_role handler, 3E update_capability_suggested_roles
        handler) translate None to the appropriate domain error at
        the decider boundary (`RoleNotFoundError` is the canonical
        translation across consumers).
        """
        ...


__all__ = ["RoleLookup", "RoleLookupResult"]
