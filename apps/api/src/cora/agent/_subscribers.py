"""Agent BC subscriber registration for the projection worker.

ROLE: This module is the REGISTRATION HELPER
(`register_agent_subscribers(registry, deps)`), NOT the home for
the subscribers themselves. Subscribers live in
`cora.agent.subscribers/` (the sub-package); this leading-underscore
module is the bridge between that package and the projection
worker's `ProjectionRegistry`.

The split mirrors the per-BC `register_<bc>_projections` convention
(`cora.<bc>._projections` registers what lives in `cora.<bc>.projections/`).
Agent BC has no `_projections` because it owns no projections (read-
side); it only owns SIDE-EFFECTING subscribers that emit new events.

## Conditional registration

If `kernel.llm is None` (`ANTHROPIC_API_KEY` unset), no subscribers
are registered and a warning is logged. The alternative (raising at
app startup) would refuse to boot a deployment that wants to defer
Agent rollout.

## Registered subscribers

  - `RunDebrieferSubscriber` — terminal Run -> one
    advisory Decision with AAR narrative + 6-value choice.
  - `CautionDrafterSubscriber` — terminal Run -> one
    `DecisionRegistered(context="CautionProposal")` with 5-value
    choice + optional proposed-Caution tuple. Operator-promoted
    via the `promote_caution_proposal` slice.
  - `CautionPromoterSubscriber` — DETERMINISTIC (no LLM): a
    high-confidence Notice-only CautionProposal -> auto-promoted live
    Caution + one `DecisionRegistered(context="CautionPromotion")`.
    Gated by `settings.caution_promoter_enabled` (default off).

Both subscribers run concurrently and INDEPENDENTLY in the
projection worker. Both classify as `Reaction` (the public sibling
to `Projection`) and pin `batch_size = 1` on the class so the
worker bounds the bookmark transaction to a single LLM round-trip.

## Subscriber framework widening status

Per [[project-caution-drafter-design]] Q4 lock the original
widening triggers were "3rd subscriber / >50ms blocking / first
cross-subscriber ordering dependency". The >50ms-blocking trigger
FIRED at first-ship (each LLM call is 5-15 s), and the framework
widened minimally: the `Reaction` Protocol was added as the sibling
to `Projection` and per-subscriber `batch_size` enforcement landed
so the docstring's `batch_size=1` claim became real.

Further widening (separate `ReactionWorker` with its own pool
budget, operator escape-hatch for wedged bookmarks via
`dismiss_event_in_reaction`) stays deferred behind the next named
triggers: 3rd Reaction OR first wedged-bookmark incident.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.agent.subscribers.caution_drafter import make_caution_drafter_subscriber
from cora.agent.subscribers.caution_promoter import make_caution_promoter_subscriber
from cora.agent.subscribers.run_debriefer import make_run_debriefer_subscriber
from cora.infrastructure.logging import get_logger

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.projection.registry import ProjectionRegistry

_log = get_logger(__name__)


def register_agent_subscribers(registry: ProjectionRegistry, deps: Kernel) -> None:
    """Register Agent BC's subscribers into the projection-worker registry."""
    # CautionPromoter is DETERMINISTIC (no LLM), so it registers independently of
    # ANTHROPIC_API_KEY, gated by its own off-by-default setting. It is the 3rd
    # projection-worker Reaction; its gate is a fast deterministic check (no
    # 5-15s LLM round-trip), so it does not warrant the deferred ReactionWorker
    # pool split that the LLM Reactions' latency motivated.
    if deps.settings.caution_promoter_enabled:
        caution_promoter = make_caution_promoter_subscriber(deps)
        registry.register(caution_promoter)
        _log.info(
            "agent_subscriber.registered",
            subscriber=caution_promoter.name,
            subscribed_event_types=sorted(caution_promoter.subscribed_event_types),
        )

    if deps.llm is None:
        _log.warning(
            "agent_subscriber.skipped",
            subscribers=["run_debriefer", "caution_drafter"],
            reason="kernel.llm is None (ANTHROPIC_API_KEY not configured)",
        )
        return

    run_debriefer = make_run_debriefer_subscriber(deps)
    registry.register(run_debriefer)
    _log.info(
        "agent_subscriber.registered",
        subscriber=run_debriefer.name,
        subscribed_event_types=sorted(run_debriefer.subscribed_event_types),
    )

    caution_drafter = make_caution_drafter_subscriber(deps)
    registry.register(caution_drafter)
    _log.info(
        "agent_subscriber.registered",
        subscriber=caution_drafter.name,
        subscribed_event_types=sorted(caution_drafter.subscribed_event_types),
    )


__all__ = ["register_agent_subscribers"]
