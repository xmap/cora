"""Run BC's subscriber-registration entry point.

The composition root (`cora.api.main`) calls
`register_run_subscribers(registry, deps)` during the FastAPI lifespan to
populate the worker's registry with the Run BC's event-reaction
subscribers. One today: the authority-revocation kill-switch, which holds
a revoked principal's in-flight runs on a Trust PolicyGrantRevoked.

Deterministic (no LLM), gated by its own off-by-default setting, so it
registers independently of ANTHROPIC_API_KEY. Mirrors the Agent BC's
`register_agent_subscribers` shape.
"""

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.projection import ProjectionRegistry
from cora.run.subscribers import make_authority_revocation_holder_subscriber

_log = get_logger(__name__)


def register_run_subscribers(registry: ProjectionRegistry, deps: Kernel) -> None:
    """Register Run BC subscribers into the projection-worker registry."""
    if deps.settings.authority_revocation_holder_enabled:
        holder = make_authority_revocation_holder_subscriber(deps)
        registry.register(holder)
        _log.info(
            "run_subscriber.registered",
            subscriber=holder.name,
            subscribed_event_types=sorted(holder.subscribed_event_types),
        )


__all__ = ["register_run_subscribers"]
