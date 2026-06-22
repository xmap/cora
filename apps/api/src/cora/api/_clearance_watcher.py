"""ClearanceWatcher runtime: the 4th ACTIVE agent (first pure flag-only).

A periodic background task, hosted at the composition root (`cora.api`) because
it reads the Safety BC AND composes Decision BC events; only `cora.api` may
depend on both (same placement rationale as `_clearance_expirer`,
`_run_supervisor`, and `_enclosure_permit_observer`). The agent-invariant
mechanics (the staleness rule, the per-episode Decision id, the
DecisionRegistered envelope, and the periodic loop / lifespan) live in
`cora.api._flag_watcher`; this module owns only what is specific to clearances,
chiefly the UnderReview review-step fold. See [[project-clearance-watcher-design]].

## What v1 does

Each tick it lists Clearances in the three pre-Active states (`Submitted` /
`UnderReview` / `Approved`), selects those that have sat past the
operator-config staleness window without progressing toward Active, and records
one `Decision(context=ClearanceProgress, choice=Flag)` per stall EPISODE. It is
FLAG-ONLY: it issues NO command (it cannot make a review faster; it surfaces the
stall so a human acts before the clearance blocks a Run at `start_run`). It is
the front-of-lifecycle / observe-only counterpart to `ClearanceExpirer`
(back-of-lifecycle / acts).

## Staleness clock and the active-review false-positive guard

`stalled_seconds = now - last_progress_at`, where
`last_progress_at = max(last_status_changed_at, last_review_step_at)`.

For `Submitted` / `Approved` there are no review steps, so
`last_status_changed_at` (on the list projection) is the correct clock. For
`UnderReview`, `ClearanceReviewStepAppended` is a deliberate NO-OP in the list
projection, so `last_status_changed_at` does NOT advance while reviewers append
steps; keying on it alone would FALSE-FLAG an actively-progressing review.
Therefore an `UnderReview` candidate that already looks stale by its status
timestamp gets ONE per-candidate `get_clearance` read to fold in the latest
`ReviewStep.decided_at` before it is flagged. Bounding that read to
already-looks-stale UnderReview candidates keeps the per-tick cost low.

## Idempotency / edge-trigger: one Flag per stall episode

The Decision id is `uuid5(namespace, "decision:{clearance_id}:{last_progress_at}")`,
so re-ticks while the clearance is still stalled hit the same id
(`ConcurrencyError` no-op). A new review step or status change advances
`last_progress_at`, opening a fresh episode that can flag again if it re-stalls.

## Fail-safe and bounded

Flag-only and reversible by construction: the worst outcome is an advisory
Decision a human can ignore. The runtime gates on `Actor.active`, so
deactivating the agent Actor stops it. Off by default
(`settings.clearance_watcher_enabled`).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from uuid import UUID

from cora.access.aggregates.actor import load_actor
from cora.agent.seed_clearance_watcher import CLEARANCE_WATCHER_AGENT_ID
from cora.api._flag_watcher import (
    derive_watcher_decision_id,
    flag_watcher_lifespan,
    is_stalled,
    record_watcher_decision,
)
from cora.decision.aggregates.decision import DECISION_CONTEXT_CLEARANCE_PROGRESS
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.safety.features.get_clearance import GetClearance
from cora.safety.features.list_clearances import ListClearances

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from datetime import datetime

    from cora.infrastructure.kernel import Kernel
    from cora.safety.features.get_clearance.handler import Handler as GetClearanceHandler
    from cora.safety.features.list_clearances import ClearanceSummaryItem
    from cora.safety.features.list_clearances.handler import Handler as ListClearancesHandler
    from cora.safety.features.list_clearances.query import ClearanceStatusFilter

_LOG_PREFIX = "clearance_watcher"
_RULE = "agent:ClearanceWatcher:v1"
_COMMAND_NAME = "ClearanceWatcherTick"
_PAGE_LIMIT = 100
_CHOICE_FLAG = "Flag"
_STATUS_UNDER_REVIEW = "UnderReview"

# The three pre-Active lifecycle states the watcher surveys. Defined (a draft
# not yet submitted) and the terminal/Active states are out of scope (Active +
# its expiry are ClearanceExpirer's territory).
_WATCHED_STATUSES: tuple[ClearanceStatusFilter, ...] = ("Submitted", "UnderReview", "Approved")

# Stable namespace for deriving the deterministic Decision id from the clearance
# id + the stall-episode timestamp (ffff block, distinct from the seed envelope
# ids), so one Flag is written per stall episode and re-ticks are no-ops.
_DECISION_NAMESPACE = UUID("01900000-0000-7000-8000-0000ffff0002")


def _derive_decision_id(clearance_id: UUID, last_progress_at: datetime) -> UUID:
    """Deterministic ClearanceProgress Decision id for one stall episode."""
    return derive_watcher_decision_id(_DECISION_NAMESPACE, clearance_id, last_progress_at)


async def _record_decision(
    deps: Kernel,
    *,
    clearance_id: UUID,
    status: str,
    last_progress_at: datetime,
    now: datetime,
) -> None:
    """Append one DecisionRegistered(context=ClearanceProgress, choice=Flag)."""
    stalled_seconds = int((now - last_progress_at).total_seconds())
    await record_watcher_decision(
        deps,
        agent_id=CLEARANCE_WATCHER_AGENT_ID,
        context=DECISION_CONTEXT_CLEARANCE_PROGRESS,
        choice=_CHOICE_FLAG,
        rule=_RULE,
        command_name=_COMMAND_NAME,
        decision_id=_derive_decision_id(clearance_id, last_progress_at),
        entity_id=clearance_id,
        now=now,
        reasoning=(
            f"Clearance has been {status} for {stalled_seconds}s without progressing "
            "toward Active (past the staleness window); surfaced for operator follow-up."
        ),
        inputs={
            "clearance_id": str(clearance_id),
            "status": status,
            "last_progress_at": last_progress_at.isoformat(),
            "stalled_seconds": str(stalled_seconds),
            "occurred_at": now.isoformat(),
        },
        log_prefix=_LOG_PREFIX,
    )


async def _drain_watched_clearances(
    list_clearances: ListClearancesHandler, deps: Kernel
) -> list[ClearanceSummaryItem]:
    """Page through list_clearances for each watched pre-Active status."""
    items: list[ClearanceSummaryItem] = []
    for status in _WATCHED_STATUSES:
        cursor: str | None = None
        while True:
            page = await list_clearances(
                ListClearances(status=status, cursor=cursor, limit=_PAGE_LIMIT),
                principal_id=CLEARANCE_WATCHER_AGENT_ID,
                correlation_id=deps.id_generator.new_id(),
                surface_id=NIL_SENTINEL_ID,
            )
            items.extend(page.items)
            if page.next_cursor is None:
                break
            cursor = page.next_cursor
    return items


async def _last_review_step_at(
    get_clearance: GetClearanceHandler, deps: Kernel, clearance_id: UUID
) -> datetime | None:
    """The most recent ReviewStep.decided_at, or None if no steps / not found.

    Folds in the review-step recency the list projection omits (it NO-OPs
    ClearanceReviewStepAppended), so an actively-reviewed clearance is not
    falsely flagged as stalled.
    """
    clearance = await get_clearance(
        GetClearance(clearance_id=clearance_id),
        principal_id=CLEARANCE_WATCHER_AGENT_ID,
        correlation_id=deps.id_generator.new_id(),
        surface_id=NIL_SENTINEL_ID,
    )
    if clearance is None or not clearance.review_steps:
        return None
    return max(step.decided_at for step in clearance.review_steps)


async def _watch_tick(
    *,
    deps: Kernel,
    list_clearances: ListClearancesHandler,
    get_clearance: GetClearanceHandler,
) -> None:
    """One watch sweep over all pre-Active clearances."""
    actor = await load_actor(deps.event_store, CLEARANCE_WATCHER_AGENT_ID)
    if actor is None or not actor.active:
        # Agent not seeded yet, or deactivated by an operator: stand down.
        return

    now = deps.clock.now()
    stale_after = deps.settings.clearance_watcher_stale_after_seconds
    items = await _drain_watched_clearances(list_clearances, deps)
    for item in items:
        base = item.last_status_changed_at
        if base is None:
            # No status-change timestamp recorded: cannot evaluate; defer.
            continue
        if not is_stalled(base, now, stale_after):
            # Fresh by status timestamp. For UnderReview a recent review step
            # only makes it fresher, so skipping here cannot hide a stall.
            continue
        last_progress_at = base
        if item.status == _STATUS_UNDER_REVIEW:
            # Looks stale by status ts, but the list projection omits review-step
            # recency; confirm against the latest ReviewStep before flagging.
            step_at = await _last_review_step_at(get_clearance, deps, item.clearance_id)
            if step_at is not None and step_at > last_progress_at:
                last_progress_at = step_at
            if not is_stalled(last_progress_at, now, stale_after):
                continue  # active review: progressing, not stalled
        await _record_decision(
            deps,
            clearance_id=item.clearance_id,
            status=item.status,
            last_progress_at=last_progress_at,
            now=now,
        )


@contextlib.asynccontextmanager
async def clearance_watcher_lifespan(
    deps: Kernel,
    *,
    list_clearances: ListClearancesHandler,
    get_clearance: GetClearanceHandler,
    interval_seconds: float | None = None,
) -> AsyncGenerator[None]:
    """Spawn the ClearanceWatcher loop for the duration of the context.

    No-op unless `settings.clearance_watcher_enabled` is True (default off, so a
    deployment opts in explicitly).
    """

    async def tick() -> None:
        await _watch_tick(deps=deps, list_clearances=list_clearances, get_clearance=get_clearance)

    async with flag_watcher_lifespan(
        enabled=deps.settings.clearance_watcher_enabled,
        default_tick_seconds=deps.settings.clearance_watcher_tick_seconds,
        log_prefix=_LOG_PREFIX,
        task_name="clearance-watcher",
        tick=tick,
        interval_seconds=interval_seconds,
    ):
        yield


__all__ = ["clearance_watcher_lifespan", "is_stalled"]
