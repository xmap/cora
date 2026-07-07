"""Trust BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_trust_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry. Trust is the third
multi-aggregate BC after Equipment and Recipe: each of Zone /
Conduit / Policy has its own projection module under
`cora.trust.projections`, all registered here.
"""

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry
from cora.trust.projections import (
    ConduitSummaryProjection,
    PolicySummaryProjection,
    RatificationCoverageProjection,
    SurfaceActiveVisitProjection,
    VisitPresenceProjection,
    VisitSummaryProjection,
    ZoneSummaryProjection,
)


def register_trust_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Trust-owned projection on the worker registry."""
    _ = deps
    registry.register(ZoneSummaryProjection())
    registry.register(ConduitSummaryProjection())
    registry.register(PolicySummaryProjection())
    registry.register(VisitSummaryProjection())
    registry.register(VisitPresenceProjection())
    registry.register(SurfaceActiveVisitProjection())
    registry.register(RatificationCoverageProjection())


__all__ = ["register_trust_projections"]
