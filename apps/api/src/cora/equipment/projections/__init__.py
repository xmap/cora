"""Equipment BC projections.

First multi-projection BC: each aggregate gets its own file under
this package. Add a new projection by creating a new module here +
re-exporting its class + adding it to `register_equipment_projections`.
"""

from cora.equipment.projections.assembly_summary import AssemblySummaryProjection
from cora.equipment.projections.asset import AssetSummaryProjection
from cora.equipment.projections.asset_family_membership import (
    AssetFamilyMembershipProjection,
)
from cora.equipment.projections.asset_location import AssetLocationProjection
from cora.equipment.projections.family import FamilySummaryProjection
from cora.equipment.projections.fixture_summary import FixtureSummaryProjection
from cora.equipment.projections.frame_children import FrameChildrenProjection
from cora.equipment.projections.frame_consumers import FrameConsumersProjection
from cora.equipment.projections.frame_summary import FrameSummaryProjection
from cora.equipment.projections.model import ModelSummaryProjection
from cora.equipment.projections.mount_children import MountChildrenProjection
from cora.equipment.projections.mount_slot_code import MountSlotCodeProjection
from cora.equipment.projections.mount_summary import MountSummaryProjection
from cora.equipment.projections.role import RoleSummaryProjection

__all__ = [
    "AssemblySummaryProjection",
    "AssetFamilyMembershipProjection",
    "AssetLocationProjection",
    "AssetSummaryProjection",
    "FamilySummaryProjection",
    "FixtureSummaryProjection",
    "FrameChildrenProjection",
    "FrameConsumersProjection",
    "FrameSummaryProjection",
    "ModelSummaryProjection",
    "MountChildrenProjection",
    "MountSlotCodeProjection",
    "MountSummaryProjection",
    "RoleSummaryProjection",
]
