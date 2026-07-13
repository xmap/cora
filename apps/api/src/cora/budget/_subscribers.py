"""Budget BC subscriber registration for the projection worker.

The registration helper (`register_budget_subscribers(registry,
deps)`), NOT the home for the subscribers themselves; those live in
`cora.budget.subscribers/`. Mirrors the split
`cora.agent._subscribers` established (the leading-underscore module
bridges the subscriber package to the worker's registry).

One Reaction today: `AllocationSealerSubscriber`, DETERMINISTIC (no
LLM) and registered UNCONDITIONALLY, because the campaign-bound seal
is bookkeeping that must not depend on whether an LLM is configured;
its per-event work is one projection read plus (rarely) one ledger
SUM and one append.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.budget.subscribers.allocation_sealer import make_allocation_sealer_subscriber
from cora.infrastructure.logging import get_logger

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.projection.registry import ProjectionRegistry

_log = get_logger(__name__)


def register_budget_subscribers(registry: ProjectionRegistry, deps: Kernel) -> None:
    """Register budget BC's subscribers into the projection-worker registry."""
    sealer = make_allocation_sealer_subscriber(deps)
    registry.register(sealer)
    _log.info(
        "budget_subscriber.registered",
        subscriber=sealer.name,
        subscribed_event_types=sorted(sealer.subscribed_event_types),
    )


__all__ = ["register_budget_subscribers"]
