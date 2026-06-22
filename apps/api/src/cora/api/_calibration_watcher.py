"""CalibrationWatcher runtime: the 7th seeded agent (deterministic flag-only).

A periodic background task, hosted at the composition root (`cora.api`) because
it reads the Calibration BC AND composes Decision BC events; only `cora.api` may
depend on both (same placement rationale as `_clearance_watcher`,
`_clearance_expirer`, `_run_supervisor`). The agent-invariant mechanics (the
staleness rule, the per-episode Decision id, the DecisionRegistered envelope, and
the periodic loop / lifespan) live in `cora.api._flag_watcher`; this module owns
only what is specific to calibrations. See [[project-calibration-watcher-design]].

## What v1 does

Each tick it lists calibrations whose latest revision is `Provisional`, selects
those whose newest revision (`last_revised_at`) has sat past the operator-config
staleness window without being verified or re-revised, and records one
`Decision(context=CalibrationVerification, choice=Stale)` per stale EPISODE. It
is FLAG-ONLY: it issues NO command (it cannot verify a calibration; it surfaces
the staleness so a human re-verifies before a Run acquires data against an
unverified value). A `Verified` calibration is out of scope (it has been
confirmed); an empty calibration (no revisions, `latest_revision_status` None)
falls out of the Provisional filter and is never flagged (cannot-tell -> defer).

## Idempotency / edge-trigger: one Stale flag per episode

The Decision id is `uuid5(namespace, "decision:{calibration_id}:{last_revised_at}")`,
so re-ticks while the calibration is still the same stale revision hit the same
id (`ConcurrencyError` no-op). Appending a new revision advances
`last_revised_at`, opening a fresh episode that can flag again if it re-stales.

## Fail-safe and bounded

Flag-only and reversible by construction: the worst outcome is an advisory
Decision a human can ignore. The runtime gates on `Actor.active`, so
deactivating the agent Actor stops it. Off by default
(`settings.calibration_watcher_enabled`).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from uuid import UUID

from cora.access.aggregates.actor import load_actor
from cora.agent.seed_calibration_watcher import CALIBRATION_WATCHER_AGENT_ID
from cora.api._flag_watcher import (
    derive_watcher_decision_id,
    flag_watcher_lifespan,
    is_stalled,
    record_watcher_decision,
)
from cora.calibration.features.list_calibrations import ListCalibrations
from cora.decision.aggregates.decision import DECISION_CONTEXT_CALIBRATION_VERIFICATION
from cora.infrastructure.routing import NIL_SENTINEL_ID

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from datetime import datetime

    from cora.calibration.features.list_calibrations import CalibrationSummaryItem
    from cora.calibration.features.list_calibrations.handler import (
        Handler as ListCalibrationsHandler,
    )
    from cora.infrastructure.kernel import Kernel

_LOG_PREFIX = "calibration_watcher"
_RULE = "agent:CalibrationWatcher:v1"
_COMMAND_NAME = "CalibrationWatcherTick"
_PAGE_LIMIT = 100
_CHOICE_STALE = "Stale"
_STATUS_PROVISIONAL = "Provisional"

# Stable namespace for deriving the deterministic Decision id from the
# calibration id + the stale-revision timestamp (ca11 block, distinct from the
# seed envelope ids), so one Stale flag is written per stale episode and re-ticks
# are no-ops.
_DECISION_NAMESPACE = UUID("01900000-0000-7000-8000-0000ca110002")


def _derive_decision_id(calibration_id: UUID, last_revised_at: datetime) -> UUID:
    """Deterministic CalibrationVerification Decision id for one stale episode."""
    return derive_watcher_decision_id(_DECISION_NAMESPACE, calibration_id, last_revised_at)


async def _record_decision(
    deps: Kernel,
    *,
    calibration_id: UUID,
    quantity: str,
    last_revised_at: datetime,
    now: datetime,
) -> None:
    """Append one DecisionRegistered(context=CalibrationVerification, choice=Stale)."""
    stale_seconds = int((now - last_revised_at).total_seconds())
    await record_watcher_decision(
        deps,
        agent_id=CALIBRATION_WATCHER_AGENT_ID,
        context=DECISION_CONTEXT_CALIBRATION_VERIFICATION,
        choice=_CHOICE_STALE,
        rule=_RULE,
        command_name=_COMMAND_NAME,
        decision_id=_derive_decision_id(calibration_id, last_revised_at),
        entity_id=calibration_id,
        now=now,
        reasoning=(
            f"Calibration ({quantity}) has had a Provisional revision unverified for "
            f"{stale_seconds}s (past the staleness window); surfaced for operator "
            "re-verification before a Run acquires against it."
        ),
        inputs={
            "calibration_id": str(calibration_id),
            "quantity": quantity,
            "last_revised_at": last_revised_at.isoformat(),
            "stale_seconds": str(stale_seconds),
            "occurred_at": now.isoformat(),
        },
        log_prefix=_LOG_PREFIX,
    )


async def _drain_provisional_calibrations(
    list_calibrations: ListCalibrationsHandler, deps: Kernel
) -> list[CalibrationSummaryItem]:
    """Page through list_calibrations filtered to latest-revision Provisional."""
    items: list[CalibrationSummaryItem] = []
    cursor: str | None = None
    while True:
        page = await list_calibrations(
            ListCalibrations(
                latest_revision_statuses=[_STATUS_PROVISIONAL],
                cursor=cursor,
                limit=_PAGE_LIMIT,
            ),
            principal_id=CALIBRATION_WATCHER_AGENT_ID,
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
    list_calibrations: ListCalibrationsHandler,
) -> None:
    """One watch sweep over all Provisional calibrations."""
    actor = await load_actor(deps.event_store, CALIBRATION_WATCHER_AGENT_ID)
    if actor is None or not actor.active:
        # Agent not seeded yet, or deactivated by an operator: stand down.
        return

    now = deps.clock.now()
    stale_after = deps.settings.calibration_watcher_stale_after_seconds
    for item in await _drain_provisional_calibrations(list_calibrations, deps):
        # Defensive: the drain filters to Provisional, but re-check so a future
        # filter change cannot widen what gets flagged.
        if item.latest_revision_status != _STATUS_PROVISIONAL:
            continue
        if not is_stalled(item.last_revised_at, now, stale_after):
            continue
        await _record_decision(
            deps,
            calibration_id=item.calibration_id,
            quantity=item.quantity,
            last_revised_at=item.last_revised_at,
            now=now,
        )


@contextlib.asynccontextmanager
async def calibration_watcher_lifespan(
    deps: Kernel,
    *,
    list_calibrations: ListCalibrationsHandler,
    interval_seconds: float | None = None,
) -> AsyncGenerator[None]:
    """Spawn the CalibrationWatcher loop for the duration of the context.

    No-op unless `settings.calibration_watcher_enabled` is True (default off, so a
    deployment opts in explicitly).
    """

    async def tick() -> None:
        await _watch_tick(deps=deps, list_calibrations=list_calibrations)

    async with flag_watcher_lifespan(
        enabled=deps.settings.calibration_watcher_enabled,
        default_tick_seconds=deps.settings.calibration_watcher_tick_seconds,
        log_prefix=_LOG_PREFIX,
        task_name="calibration-watcher",
        tick=tick,
        interval_seconds=interval_seconds,
    ):
        yield


__all__ = ["calibration_watcher_lifespan", "is_stalled"]
