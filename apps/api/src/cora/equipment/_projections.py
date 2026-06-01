"""Equipment BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_equipment_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry. Equipment is the first
multi-aggregate BC: Asset and Family each have their own
projection module under `cora.equipment.projections`.
"""

from cora.equipment.projections import (
    AssetFamilyMembershipProjection,
    AssetLocationProjection,
    AssetSummaryProjection,
    FamilySummaryProjection,
    FrameChildrenProjection,
    FrameConsumersProjection,
    FrameSummaryProjection,
    ModelSummaryProjection,
    MountChildrenProjection,
    MountLookupProjection,
    MountSummaryProjection,
)
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry


def register_equipment_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Equipment-owned projection on the worker registry."""
    _ = deps
    registry.register(AssetSummaryProjection())
    registry.register(AssetFamilyMembershipProjection())
    registry.register(FamilySummaryProjection())
    registry.register(ModelSummaryProjection())
    registry.register(FrameSummaryProjection())
    registry.register(FrameChildrenProjection())
    registry.register(FrameConsumersProjection())
    registry.register(MountSummaryProjection())
    registry.register(MountLookupProjection())
    registry.register(MountChildrenProjection())
    registry.register(AssetLocationProjection())


__all__ = ["register_equipment_projections"]
