"""CampaignWatcher runtime: the 9th seeded agent (deterministic flag-only).

A periodic background task, hosted at the composition root (`cora.api`) because
it reads the Campaign BC AND composes Decision BC events; only `cora.api` may
depend on both (same placement rationale as `_clearance_watcher`,
`_calibration_watcher`, `_procedure_watcher`). The agent-invariant mechanics (the
staleness rule, the per-episode Decision id, the DecisionRegistered envelope, and
the periodic loop / lifespan) live in `cora.api._flag_watcher`; this module owns
only what is specific to campaigns. See [[project-campaign-watcher-design]].

## What v1 does

Each tick it lists `Held` campaigns (operator-paused), selects those whose
`last_status_changed_at` (the time they were held) has sat past the
operator-config staleness window without being resumed or closed, and records one
`Decision(context=CampaignProgress, choice=Stuck)` per stuck EPISODE. It is
FLAG-ONLY: it issues NO command (it surfaces the forgotten pause so a human
resumes or closes the campaign). v1 watches only `Held`; `Planned` (a campaign
that has legitimately not started yet) is deferred to a later variant with its
own window.

## No activity fold needed

Unlike `_procedure_watcher` (whose Running state churns activity without advancing
the status timestamp), `Held` makes no run-EXECUTION progress: `last_status_changed_at`
(set on `CampaignHeld`, advanced only by `resume_campaign` / `close_campaign`) is
the correct clock and no recency fold is required. Membership curation
(`add_run_to_campaign` / remove) is permitted while Held but deliberately touches
only `run_count`, never the status clock, so a long forgotten Hold still flags. A
defensive `status == Held` re-check guards a future filter widening (mirrors
`_calibration_watcher`).

## Idempotency / edge-trigger: one Stuck flag per episode

The Decision id is `uuid5(namespace, "decision:{campaign_id}:{last_status_changed_at}")`,
so re-ticks while the campaign is still Held hit the same id (`ConcurrencyError`
no-op). `resume_campaign` advances `last_status_changed_at` (and leaves Held), and
`close_campaign` / `abandon_campaign` leave the Held filter, so a resumed campaign
that is re-held opens a fresh episode.

## Fail-safe and bounded

Flag-only and reversible by construction: the worst outcome is an advisory
Decision a human can ignore. The runtime gates on `Actor.active`, so deactivating
the agent Actor stops it. Off by default (`settings.campaign_watcher_enabled`).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from uuid import UUID

from cora.access.aggregates.actor import load_actor
from cora.agent.seed_campaign_watcher import CAMPAIGN_WATCHER_AGENT_ID
from cora.api._flag_watcher import (
    WatcherReadUnauthorizedError,
    derive_watcher_decision_id,
    flag_watcher_lifespan,
    is_stalled,
    probe_read_grant,
    record_watcher_decision,
)
from cora.campaign.errors import UnauthorizedError
from cora.campaign.features.list_campaigns import ListCampaigns
from cora.decision.aggregates.decision import DECISION_CONTEXT_CAMPAIGN_PROGRESS
from cora.infrastructure.routing import NIL_SENTINEL_ID

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from datetime import datetime

    from cora.campaign.features.list_campaigns import CampaignSummaryItem
    from cora.campaign.features.list_campaigns.handler import Handler as ListCampaignsHandler
    from cora.infrastructure.kernel import Kernel

_LOG_PREFIX = "campaign_watcher"
_READ_COMMAND = "ListCampaigns"
_RULE = "agent:CampaignWatcher:v1"
_COMMAND_NAME = "CampaignWatcherTick"
_PAGE_LIMIT = 100
_CHOICE_STUCK = "Stuck"
_STATUS_HELD = "Held"

# Stable namespace for deriving the deterministic Decision id from the campaign
# id + the held-episode timestamp (cab1 block, distinct from the seed envelope
# ids), so one Stuck flag is written per stuck episode and re-ticks are no-ops.
_DECISION_NAMESPACE = UUID("01900000-0000-7000-8000-0000cab10002")


def _derive_decision_id(campaign_id: UUID, last_status_changed_at: datetime) -> UUID:
    """Deterministic CampaignProgress Decision id for one stuck episode."""
    return derive_watcher_decision_id(_DECISION_NAMESPACE, campaign_id, last_status_changed_at)


async def _record_decision(
    deps: Kernel,
    *,
    campaign_id: UUID,
    name: str,
    last_status_changed_at: datetime,
    now: datetime,
) -> None:
    """Append one DecisionRegistered(context=CampaignProgress, choice=Stuck)."""
    stuck_seconds = int((now - last_status_changed_at).total_seconds())
    await record_watcher_decision(
        deps,
        agent_id=CAMPAIGN_WATCHER_AGENT_ID,
        context=DECISION_CONTEXT_CAMPAIGN_PROGRESS,
        choice=_CHOICE_STUCK,
        rule=_RULE,
        command_name=_COMMAND_NAME,
        decision_id=_derive_decision_id(campaign_id, last_status_changed_at),
        entity_id=campaign_id,
        now=now,
        reasoning=(
            f"Campaign ({name}) has sat Held for {stuck_seconds}s without being resumed "
            "or closed (past the staleness window); surfaced for operator follow-up."
        ),
        inputs={
            "campaign_id": str(campaign_id),
            "name": name,
            "last_status_changed_at": last_status_changed_at.isoformat(),
            "stuck_seconds": str(stuck_seconds),
            "occurred_at": now.isoformat(),
        },
        log_prefix=_LOG_PREFIX,
    )


async def _drain_held_campaigns(
    list_campaigns: ListCampaignsHandler, deps: Kernel
) -> list[CampaignSummaryItem]:
    """Page through list_campaigns filtered to status Held."""
    items: list[CampaignSummaryItem] = []
    cursor: str | None = None
    while True:
        page = await list_campaigns(
            ListCampaigns(statuses=[_STATUS_HELD], cursor=cursor, limit=_PAGE_LIMIT),
            principal_id=CAMPAIGN_WATCHER_AGENT_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=NIL_SENTINEL_ID,
        )
        items.extend(page.items)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    return items


async def _watch_tick(
    *,
    deps: Kernel,
    list_campaigns: ListCampaignsHandler,
) -> None:
    """One watch sweep over all Held campaigns."""
    actor = await load_actor(deps.event_store, CAMPAIGN_WATCHER_AGENT_ID)
    if actor is None or not actor.active:
        # Agent not seeded yet, or deactivated by an operator: stand down.
        return

    now = deps.clock.now()
    stale_after = deps.settings.campaign_watcher_stale_after_seconds
    try:
        items = await _drain_held_campaigns(list_campaigns, deps)
    except UnauthorizedError as err:
        # The authz-gated drain was Denied: a missing read grant blinds the
        # watchdog. Re-raise as the scaffold type so the loop warns loudly
        # (edge-triggered) instead of burying it as a generic tick failure.
        raise WatcherReadUnauthorizedError(
            query_name=_READ_COMMAND,
            principal_id=CAMPAIGN_WATCHER_AGENT_ID,
            reason=str(err),
        ) from err
    for item in items:
        # Defensive: the drain filters to Held, but re-check so a future filter
        # change cannot widen what gets flagged.
        if item.status != _STATUS_HELD:
            continue
        if item.last_status_changed_at is None:
            # No status-change timestamp recorded: cannot evaluate; defer.
            continue
        if not is_stalled(item.last_status_changed_at, now, stale_after):
            continue
        await _record_decision(
            deps,
            campaign_id=item.campaign_id,
            name=item.name,
            last_status_changed_at=item.last_status_changed_at,
            now=now,
        )


@contextlib.asynccontextmanager
async def campaign_watcher_lifespan(
    deps: Kernel,
    *,
    list_campaigns: ListCampaignsHandler,
    interval_seconds: float | None = None,
) -> AsyncGenerator[None]:
    """Spawn the CampaignWatcher loop for the duration of the context.

    No-op unless `settings.campaign_watcher_enabled` is True (default off, so a
    deployment opts in explicitly).
    """

    async def tick() -> None:
        await _watch_tick(deps=deps, list_campaigns=list_campaigns)

    async def startup_probe() -> None:
        await probe_read_grant(
            deps,
            agent_id=CAMPAIGN_WATCHER_AGENT_ID,
            read_command=_READ_COMMAND,
            log_prefix=_LOG_PREFIX,
            strict=deps.settings.watcher_authz_strict,
        )

    async with flag_watcher_lifespan(
        enabled=deps.settings.campaign_watcher_enabled,
        default_tick_seconds=deps.settings.campaign_watcher_tick_seconds,
        log_prefix=_LOG_PREFIX,
        task_name="campaign-watcher",
        tick=tick,
        startup_probe=startup_probe,
        interval_seconds=interval_seconds,
    ):
        yield


__all__ = ["campaign_watcher_lifespan", "is_stalled"]
