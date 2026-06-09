"""Enclosure BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_enclosure_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry. Enclosure is a single-
aggregate BC: today only `EnclosureSummaryProjection` exists.
"""

from cora.enclosure.projections import EnclosureSummaryProjection
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry


def register_enclosure_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Enclosure-owned projection on the worker registry."""
    _ = deps
    registry.register(EnclosureSummaryProjection())


__all__ = ["register_enclosure_projections"]
