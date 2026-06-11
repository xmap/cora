"""Slice-local cross-aggregate context for `bind_plan_role`.

Threads the Plan's bound Method, the candidate Asset, and the
Layer 3 sub-slice 3D RoleLookup + FamilyLookup + AssemblyLookup
results into the pure decider so the decider stays I/O-free.

`method` MAY be None when the Plan's `state.method_id` is None:
that would be a legacy Plan whose define-time event lacked the
field, and the decider treats this as `MethodNotFoundError`.

`role_lookup_result` is populated by the handler ONLY when the
matching RoleRequirement (looked up by role_name) carries
`role_kind` (the 3D path). None when the matching RoleRequirement
is family_id-only (the slice-1 anatomical escape hatch). Also
None when the role_name is not declared on the Method (decider
surfaces PlanRoleNameNotDeclaredError before consulting this).

`family_lookups` is a dict keyed by family_id mapping to the
FamilyLookupResult the handler loaded for each family in
`asset.family_ids`. Populated alongside `role_lookup_result` for
the 3D role_kind path; empty when the slice-1 family_id path is
in play (decider does not consult).

`assembly_lookup_result` is populated by the handler ONLY when
(a) the matching RoleRequirement carries `role_kind` AND (b) the
candidate Asset carries `fixture_id` (the Asset is part of a
materialized Assembly). The decider ORs-in
`role_kind in assembly.presents_as` on top of the Family
disjunction so a composed Assembly (e.g. MCTOptics) can satisfy
the Role even when no individual Family in `asset.family_ids`
declares it. None when the Asset is not in a Fixture or when
the Fixture / Assembly projection lookup misses (the Family path
may still succeed; if it does not the existing
PlanRoleAssetCannotPresentError fires).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from uuid import UUID

from cora.equipment.aggregates.asset import Asset
from cora.infrastructure.ports import (
    AssemblyLookupResult,
    FamilyLookupResult,
    RoleLookupResult,
)
from cora.recipe.aggregates.method import Method


@dataclass(frozen=True)
class BindPlanRoleContext:
    """Cross-aggregate inputs the bind_plan_role decider needs."""

    method: Method | None
    asset: Asset | None
    role_lookup_result: RoleLookupResult | None = None
    family_lookups: Mapping[UUID, FamilyLookupResult] = field(
        default_factory=dict[UUID, FamilyLookupResult]
    )
    assembly_lookup_result: AssemblyLookupResult | None = None
