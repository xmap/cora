"""Agent BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_agent_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry. Agent BC's projections
ship per the Path C lock (state stays decider-minimal; lifecycle
timestamps live on the projection, mirroring
Method/Plan/Practice/Family/Capability).
"""

from cora.agent.projections import AgentSummaryProjection, LanguageModelSummaryProjection
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry


def register_agent_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Agent-owned projection on the worker registry."""
    _ = deps
    registry.register(AgentSummaryProjection())
    registry.register(LanguageModelSummaryProjection())


__all__ = ["register_agent_projections"]
