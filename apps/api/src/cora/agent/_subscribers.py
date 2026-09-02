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

The deterministic subscribers (AuthorityRevocationHolder,
CautionPromoter) register independently of `kernel.llm`. The
LLM-backed subscribers (RunDebriefer, CautionDrafter) register only
when `kernel.llm` is wired, which needs BOTH `llm_enabled` (the
switch, default off) and `ANTHROPIC_API_KEY` (the credential); if it
is None they are skipped with a warning rather than refusing to boot a
deployment that wants to defer Agent rollout. These two are the seam
through which experiment metadata would leave the facility and tokens
would be spent, on every terminal Run, so the switch defaults off.

## Registered subscribers

  - `AuthorityRevocationHolderSubscriber` — DETERMINISTIC (no LLM),
    the kill-switch (K3): on a `PolicyGrantRevoked`, holds each
    in-flight Run the revoked principal drives (Running only) and
    records one `Decision(context="AuthorityRevocationHold")` per run.
    Registered UNCONDITIONALLY, on by default (a kill-switch that must
    be turned on is not a kill-switch; the hold is reversible).
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

The subscribers run concurrently and INDEPENDENTLY in the projection
worker. Each classifies as `Reaction` (the public sibling to
`Projection`) and pins `batch_size = 1` on the class so the worker
bounds the bookmark transaction to a single unit of work.

## Subscriber framework widening status

Per [[project-caution-drafter-design]] Q4 lock the original
widening triggers were "3rd subscriber / >50ms blocking / first
cross-subscriber ordering dependency". The >50ms-blocking trigger
FIRED at first-ship (each LLM call is 5-15 s), and the framework
widened minimally: the `Reaction` Protocol was added as the sibling
to `Projection` and per-subscriber `batch_size` enforcement landed
so the docstring's `batch_size=1` claim became real.

The operator escape-hatch for wedged bookmarks has since shipped as
the `dismiss_event_in_reaction` slice. Further widening (a separate
`ReactionWorker` with its own pool budget) stays deferred behind the
next named triggers: 3rd Reaction OR first wedged-bookmark incident.

## Subscriber agent designation

`settings.run_debriefer_agent_id` / `settings.caution_drafter_agent_id`
let a deployment designate a non-seeded Agent for either LLM
subscriber to act as (a deployment whose configured `llm_provider`
cannot reach the seeded agents' declared provider defines its own
Agent and names it here). `report_designated_agents(deps)`, called
from `cora.api.main` after both singleton seeds, logs which Agent is
effective for each subscriber and warns on a provider mismatch; it is
a report, not a gate, so it never blocks boot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.agent.aggregates.agent import load_agent
from cora.agent.build_llm import llm_unwired_reason
from cora.agent.seed_caution_drafter_external import CAUTION_DRAFTER_EXTERNAL_AGENT_ID
from cora.agent.seed_run_debriefer_external import RUN_DEBRIEFER_EXTERNAL_AGENT_ID
from cora.agent.subscribers.authority_revocation_holder import (
    make_authority_revocation_holder_subscriber,
)
from cora.agent.subscribers.caution_drafter import make_caution_drafter_subscriber
from cora.agent.subscribers.caution_promoter import make_caution_promoter_subscriber
from cora.agent.subscribers.ratification_hold import make_ratification_hold_subscriber
from cora.agent.subscribers.ratification_release import make_ratification_release_subscriber
from cora.agent.subscribers.run_debriefer import make_run_debriefer_subscriber
from cora.infrastructure.logging import get_logger

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.projection.registry import ProjectionRegistry

_log = get_logger(__name__)


def register_agent_subscribers(registry: ProjectionRegistry, deps: Kernel) -> None:
    """Register Agent BC's subscribers into the projection-worker registry."""
    # AuthorityRevocationHolder is the kill-switch (K3): DETERMINISTIC (no LLM)
    # and registered UNCONDITIONALLY, on by default. A kill-switch that must be
    # turned on is not a kill-switch; the hold it issues is reversible (resume_run
    # exists), so default-on matches the safety intent. Its gate is a fast
    # deterministic lookup (no LLM round-trip), so like CautionPromoter it does
    # not warrant the deferred ReactionWorker pool split.
    holder = make_authority_revocation_holder_subscriber(deps)
    registry.register(holder)
    _log.info(
        "agent_subscriber.registered",
        subscriber=holder.name,
        subscribed_event_types=sorted(holder.subscribed_event_types),
    )

    # RatificationEnforcer (consequence gate, Gate IV): a DETERMINISTIC subscriber
    # pair, registered UNCONDITIONALLY. The hold reacts to RatificationRequested
    # (park the run pending co-sign); the release reacts to RatificationGranted
    # (resume it). Both discharge into the same shared RunHeld/RunResumed hold the
    # kill-switch uses; no LLM, so no ReactionWorker pool split needed.
    ratification_hold = make_ratification_hold_subscriber(deps)
    registry.register(ratification_hold)
    _log.info(
        "agent_subscriber.registered",
        subscriber=ratification_hold.name,
        subscribed_event_types=sorted(ratification_hold.subscribed_event_types),
    )
    ratification_release = make_ratification_release_subscriber(deps)
    registry.register(ratification_release)
    _log.info(
        "agent_subscriber.registered",
        subscriber=ratification_release.name,
        subscribed_event_types=sorted(ratification_release.subscribed_event_types),
    )

    # CautionPromoter is DETERMINISTIC (no LLM), so it registers independently of
    # ANTHROPIC_API_KEY, gated by its own off-by-default setting. It is a
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
            reason=llm_unwired_reason(deps.settings),
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


async def report_designated_agents(deps: Kernel) -> None:
    """Log which Agent each LLM subscriber will act as, and whether its
    declared provider matches `settings.llm_provider`.

    Called from `cora.api.main` AFTER both singleton seeds, so the
    default (unset designation) case always resolves an Agent. This is
    a REPORT, never a gate: it does not skip, raise, or refuse boot on a
    mismatch. The LLM adapter already refuses a request whose
    `model_ref.provider` isn't its own and is the authority on whether
    the pairing works; a second gate here would re-decide a verdict
    that already exists. The warning exists only because the adapter's
    refusal arrives per-event, hours later, as a deferred Decision that
    never names the mismatch -- an operator reading the boot log should
    see it up front instead.

    A designated-but-missing Agent (misconfiguration) logs a warning
    and moves on; the subscriber's own per-apply gate is what actually
    skips work for that case.
    """
    for subscriber_name, agent_id in (
        ("run_debriefer", deps.settings.run_debriefer_agent_id or RUN_DEBRIEFER_EXTERNAL_AGENT_ID),
        (
            "caution_drafter",
            deps.settings.caution_drafter_agent_id or CAUTION_DRAFTER_EXTERNAL_AGENT_ID,
        ),
    ):
        agent = await load_agent(deps.event_store, agent_id)
        if agent is None:
            _log.warning(
                "agent_subscriber.designated_agent_not_found",
                subscriber=subscriber_name,
                agent_id=str(agent_id),
            )
            continue
        _log.info(
            "agent_subscriber.designated_agent",
            subscriber=subscriber_name,
            agent_id=str(agent_id),
            agent_name=agent.name.value,
            agent_kind=agent.kind.value,
            provider=agent.model_ref.provider,
            model=agent.model_ref.model,
        )
        if agent.model_ref.provider != deps.settings.llm_provider:
            _log.warning(
                "agent_subscriber.designated_agent_provider_mismatch",
                subscriber=subscriber_name,
                agent_id=str(agent_id),
                agent_provider=agent.model_ref.provider,
                configured_llm_provider=deps.settings.llm_provider,
            )


__all__ = ["register_agent_subscribers", "report_designated_agents"]
