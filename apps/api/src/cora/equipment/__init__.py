"""Equipment bounded context.

Owns the equipment-and-family concerns of CORA:
  - `Family` (technique-class catalog; what an equipment type
    can do, equipment-agnostic, cross-facility). Referenced by
    `Recipe.Method.needed_family_ids` to express a Method's
    hardware contract.
  - `Asset` (physical equipment instance; hierarchical, lifecycle-
    managed). Referenced by `Recipe.Plan` and `Operation.Procedure`.

Foundation-tier BC: every Track A and Track B BC depends on
Family and/or Asset. Built before Recipe so Method's
`needed_family_ids` resolves to real Family ids instead of
bare UUIDs (the eventual-consistency fallback that Trust uses for
Conduit's zone refs).

## Asset.tier posture (ISA-88-derived, conventional not enforced)

`Asset.tier` follows the ISA-88 equipment tiers (Unit / Component /
Device) as a single-word StrEnum; facility-envelope scope is owned by
the Facility aggregate, not an Asset tier. The single-parent tree rule
(`parent_id` chain, no cycles) IS structurally enforced; the tier
ordering is NOT. CORA permits Device-in-Device parent chains when the
parent is an addressable control surface (smart instruments,
networked subassemblies). Operator guidance: default to strict
ordering; reach for nesting only when the physical hardware genuinely
composes that way (per [[project-bc-map]] +
glossary). The state.py docstring carries the canonical phrasing;
this BC docstring surfaces the posture so operators reading the BC
introduction find it without spelunking into the aggregate file.

Layout:
    aggregates/<aggregate>/   -- aggregate state, events union, evolver, read
    features/<verb>_<noun>/   -- vertical slice: command/query + decider? + handler + route + tool
    wire.py                   -- EquipmentHandlers bundle + wire_equipment(deps)
    routes.py                 -- register_equipment_routes(app)
"""

from cora.equipment._bootstrap import bootstrap_equipment
from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.asset import (
    AssetPersistentIdAlreadyAssignedError,
    AssetPersistentIdAssigned,
    AssetPersistentIdAssignmentForbiddenError,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.routes import register_equipment_routes
from cora.equipment.tools import register_equipment_tools
from cora.equipment.wire import EquipmentHandlers, wire_equipment
from cora.shared.ports.doi_minter import (
    DoiMinter,
    PersistentIdentifierMintError,
)

__all__ = [
    "AssetPersistentIdAlreadyAssignedError",
    "AssetPersistentIdAssigned",
    "AssetPersistentIdAssignmentForbiddenError",
    "DoiMinter",
    "EquipmentHandlers",
    "PersistentIdentifierMintError",
    "UnauthorizedError",
    "bootstrap_equipment",
    "register_equipment_projections",
    "register_equipment_routes",
    "register_equipment_tools",
    "wire_equipment",
]
