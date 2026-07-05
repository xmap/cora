"""Run BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_run_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry. Single-aggregate BC;
RunSummaryProjection is the only projection today.
"""

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry
from cora.run.projections import RunActorInvolvementProjection, RunSummaryProjection


def register_run_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Run-owned projection on the worker registry."""
    _ = deps
    registry.register(RunSummaryProjection())
    registry.register(RunActorInvolvementProjection())


__all__ = ["register_run_projections"]
