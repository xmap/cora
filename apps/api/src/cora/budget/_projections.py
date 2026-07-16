"""Budget BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_budget_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry, mirroring the per-BC
`register_<bc>_projections` convention.
"""

from cora.budget.projections import AllocationSummaryProjection
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry


def register_budget_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every budget-owned projection on the worker registry."""
    _ = deps
    registry.register(AllocationSummaryProjection())


__all__ = ["register_budget_projections"]
