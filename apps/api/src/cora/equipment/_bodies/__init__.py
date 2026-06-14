"""Pydantic wire-format DTO subpackage for the Equipment BC.

Carved from the BC root once the private-module count crossed the ~10-file
threshold (see docs/reference/layout.md). Groups the request and response
body DTOs that mirror Equipment value objects on the REST and MCP edges.
Several of them (Drawing, Placement) are shared across multiple aggregates,
so they cannot live inside any single feature slice (slice-independence
forbids cross-slice imports); the shared home is here.

Re-exports the public surface so consumers import from the package
(`from cora.equipment._bodies import DrawingBody`).
"""

from ._alternate_identifier_body import AlternateIdentifierBody
from ._asset_owner_body import AssetOwnerBody
from ._asset_persistent_identifier_body import (
    AssignAssetPersistentIdRequest,
    AssignAssetPersistentIdResponse,
)
from ._drawing_body import DrawingBody
from ._fixture_persistent_identifier_body import (
    AssignFixturePersistentIdRequest,
    AssignFixturePersistentIdResponse,
)
from ._placement_body import PlacementBody
from ._sub_assembly_link_body import SubAssemblyLinkBody
from ._template_slot_body import TemplateSlotBody
from ._template_wire_body import TemplateWireBody

__all__ = [
    "AlternateIdentifierBody",
    "AssetOwnerBody",
    "AssignAssetPersistentIdRequest",
    "AssignAssetPersistentIdResponse",
    "AssignFixturePersistentIdRequest",
    "AssignFixturePersistentIdResponse",
    "DrawingBody",
    "PlacementBody",
    "SubAssemblyLinkBody",
    "TemplateSlotBody",
    "TemplateWireBody",
]
