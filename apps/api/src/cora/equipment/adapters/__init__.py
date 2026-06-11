"""Equipment BC adapters.

`StubDoiMinter` is the test-tier `DoiMinter` adapter per
[[project-asset-persistent-id-write-design]] (slice F.1): a real
adapter that returns inert deterministic values, distinct from a
None / disabled port. Mirrors `AllowAllAuthorize` and
`AlwaysCoveredClearanceLookup` test-bypass convention. The
production `DataCiteDoiMinter` adapter is deferred to slice F.2.

`PostgresAssetLookup` is the production `AssetLookup` adapter per
Session 5 Slice 7B (cross-BC Supply.containing_asset_id binding +
future Slice 8 Asset.facility_id binding). Reads
`proj_equipment_asset_summary`; the test-tier `InMemoryAssetLookup`
lives at `cora.infrastructure.adapters` mirroring the
`FacilityLookup` split.

`PostgresRoleLookup` is the production `RoleLookup` adapter per
Layer 3 sub-slice 3A of [[project-role-aggregate-design]]. Reads
`proj_equipment_role_summary`; the test-tier `InMemoryRoleLookup`
lives at `cora.infrastructure.adapters` mirroring the
`AssetLookup` / `FacilityLookup` split.

`PostgresFamilyLookup` is the production `FamilyLookup` adapter per
Layer 3 sub-slice 3B. Reads `proj_equipment_family_summary` (with
the presents_as + affordances columns added by 3B); consumed by
3D's `bind_plan_role` handler.

`PostgresAssemblyLookup` is the production `AssemblyLookup` adapter
per Layer 3 sub-slice 3D follow-up. Reads
`proj_equipment_assembly_summary` (with the presents_as column
added by 3C); consumed by `bind_plan_role` so the role_kind
satisfaction path ORs-in the Assembly branch on top of the Family
disjunction (Lock 17 worked-example coverage).
"""

from cora.equipment.adapters.postgres_assembly_lookup import PostgresAssemblyLookup
from cora.equipment.adapters.postgres_asset_lookup import PostgresAssetLookup
from cora.equipment.adapters.postgres_family_lookup import PostgresFamilyLookup
from cora.equipment.adapters.postgres_role_lookup import PostgresRoleLookup

__all__ = [
    "PostgresAssemblyLookup",
    "PostgresAssetLookup",
    "PostgresFamilyLookup",
    "PostgresRoleLookup",
]
