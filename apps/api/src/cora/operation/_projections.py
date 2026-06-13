"""Operation BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_operation_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry. Operation is a single-
aggregate BC: the Procedure summary plus the per-iteration read model.
"""

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry
from cora.operation.projections import (
    ProcedureIterationsProjection,
    ProcedureSummaryProjection,
)


def register_operation_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Operation-owned projection on the worker registry."""
    _ = deps
    registry.register(ProcedureSummaryProjection())
    registry.register(ProcedureIterationsProjection())


__all__ = ["register_operation_projections"]
