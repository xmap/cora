"""ProcedureWatcher runtime: the 8th seeded agent, third pure flag-only watcher.

A periodic background task, hosted at the composition root (`cora.api`) because
it reads the Operation BC AND composes Decision BC events; only `cora.api` may
depend on both (same placement rationale as `_clearance_watcher`,
`_calibration_watcher`, and `_run_supervisor`). The agent-invariant mechanics
(the staleness rule, the per-episode Decision id, the DecisionRegistered
envelope, and the periodic loop / lifespan) live in `cora.api._flag_watcher`;
this module owns only what is specific to procedures, chiefly the Running
activity-recency fold. See [[project-procedure-watcher-design]].

## What v1 does

Each tick it lists in-conduct procedures (`Running` and `Held`), selects those
that have sat past the operator-config staleness window without progressing, and
records one `Decision(context=ProcedureProgress, choice=Stall)` per stall
EPISODE. It is FLAG-ONLY: it issues NO command (it cannot un-stick a conduct; it
surfaces the stall so a human acts before an experiment hangs unnoticed
mid-procedure). Procedure is a distinct aggregate from Run, so this liveness gap
is one `_run_supervisor` does not cover.

## Staleness clock and the active-conduct false-positive guard

`stalled_seconds = now - last_progress_at`.

For `Held` the conduct is paused and accepts no activity, so
`last_status_changed_at` (the time it was held, on the list projection) is the
correct clock. For `Running`, `proj_operation_procedure_summary` advances
`last_status_changed_at` only on real lifecycle transitions and NO-OPs it for
`ProcedureActivitiesLogbookOpened` / `ProcedureIterationStarted` (activity is
orthogonal to lifecycle); so keying on it alone would FALSE-FLAG a procedure
that is actively logging steps. Therefore a `Running` candidate that already
looks stale by its status timestamp gets ONE per-candidate
`read_procedure_activity_recency` to fold in the latest activity `recorded_at`
before it is flagged. Bounding that read to already-looks-stale `Running`
candidates keeps the per-tick cost low. This mirrors `_clearance_watcher`
folding the latest `ReviewStep.decided_at` for an `UnderReview` clearance.

## Idempotency / edge-trigger: one Stall per stall episode

The Decision id is `uuid5(namespace, "decision:{procedure_id}:{last_progress_at}")`,
so re-ticks while the procedure is still stalled hit the same id
(`ConcurrencyError` no-op). A status change or a later activity advances
`last_progress_at`, opening a fresh episode that can flag again if it re-stalls.

## Fail-safe and bounded

Flag-only and reversible by construction: the worst outcome is an advisory
Decision a human can ignore. The runtime gates on `Actor.active`, so
deactivating the agent Actor stops it. Off by default
(`settings.procedure_watcher_enabled`).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from uuid import UUID

from cora.access.aggregates.actor import load_actor
from cora.agent.seed_procedure_watcher import PROCEDURE_WATCHER_AGENT_ID
from cora.api._flag_watcher import (
    WatcherReadUnauthorizedError,
    derive_watcher_decision_id,
    flag_watcher_lifespan,
    is_stalled,
    probe_read_grant,
    record_watcher_decision,
)
from cora.decision.aggregates.decision import DECISION_CONTEXT_PROCEDURE_PROGRESS
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.adapters.postgres_procedure_activity_lookup import (
    PostgresProcedureActivityLookup,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features.list_procedures import ListProcedures
from cora.operation.ports import InMemoryProcedureActivityLookup

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from datetime import datetime

    from cora.infrastructure.kernel import Kernel
    from cora.operation.features.list_procedures import ProcedureSummaryItem
    from cora.operation.features.list_procedures.handler import Handler as ListProceduresHandler
    from cora.operation.features.list_procedures.query import ProcedureStatusFilter
    from cora.operation.ports import ProcedureActivityLookup

_LOG_PREFIX = "procedure_watcher"
_READ_COMMAND = "ListProcedures"
_RULE = "agent:ProcedureWatcher:v1"
_COMMAND_NAME = "ProcedureWatcherTick"
_PAGE_LIMIT = 100
_CHOICE_STALL = "Stall"
_STATUS_RUNNING = "Running"

# The two in-conduct lifecycle states the watcher surveys. Defined (registered,
# not started) and the terminal states (Completed / Aborted / Truncated) are out
# of scope: only an active or paused conduct can hang mid-flight.
_WATCHED_STATUSES: tuple[ProcedureStatusFilter, ...] = ("Running", "Held")

# Stable namespace for deriving the deterministic Decision id from the procedure
# id + the stall-episode timestamp (0c0c block, distinct from the seed envelope
# ids), so one Stall is written per stall episode and re-ticks are no-ops.
_DECISION_NAMESPACE = UUID("01900000-0000-7000-8000-00000c0c0002")


def _derive_decision_id(procedure_id: UUID, last_progress_at: datetime) -> UUID:
    """Deterministic ProcedureProgress Decision id for one stall episode."""
    return derive_watcher_decision_id(_DECISION_NAMESPACE, procedure_id, last_progress_at)


def _default_activity_lookup(deps: Kernel) -> ProcedureActivityLookup:
    """Build the BC-local ProcedureActivityLookup: Postgres when a pool is
    present, the in-memory stub otherwise (the test / pool-less default)."""
    if deps.pool is not None:
        return PostgresProcedureActivityLookup(deps.pool)
    return InMemoryProcedureActivityLookup()


async def _record_decision(
    deps: Kernel,
    *,
    procedure_id: UUID,
    status: str,
    last_progress_at: datetime,
    now: datetime,
) -> None:
    """Append one DecisionRegistered(context=ProcedureProgress, choice=Stall)."""
    stalled_seconds = int((now - last_progress_at).total_seconds())
    await record_watcher_decision(
        deps,
        agent_id=PROCEDURE_WATCHER_AGENT_ID,
        context=DECISION_CONTEXT_PROCEDURE_PROGRESS,
        choice=_CHOICE_STALL,
        rule=_RULE,
        command_name=_COMMAND_NAME,
        decision_id=_derive_decision_id(procedure_id, last_progress_at),
        entity_id=procedure_id,
        now=now,
        reasoning=(
            f"Procedure has been {status} for {stalled_seconds}s without progressing "
            "(past the staleness window, no recent activity); surfaced for operator "
            "follow-up."
        ),
        inputs={
            "procedure_id": str(procedure_id),
            "status": status,
            "last_progress_at": last_progress_at.isoformat(),
            "stalled_seconds": str(stalled_seconds),
            "occurred_at": now.isoformat(),
        },
        log_prefix=_LOG_PREFIX,
    )


async def _drain_watched_procedures(
    list_procedures: ListProceduresHandler, deps: Kernel
) -> list[ProcedureSummaryItem]:
    """Page through list_procedures for each watched in-conduct status."""
    items: list[ProcedureSummaryItem] = []
    for status in _WATCHED_STATUSES:
        cursor: str | None = None
        while True:
            page = await list_procedures(
                ListProcedures(status=status, cursor=cursor, limit=_PAGE_LIMIT),
                principal_id=PROCEDURE_WATCHER_AGENT_ID,
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
    list_procedures: ListProceduresHandler,
    activity_lookup: ProcedureActivityLookup,
) -> None:
    """One watch sweep over all in-conduct procedures."""
    actor = await load_actor(deps.event_store, PROCEDURE_WATCHER_AGENT_ID)
    if actor is None or not actor.active:
        # Agent not seeded yet, or deactivated by an operator: stand down.
        return

    now = deps.clock.now()
    stale_after = deps.settings.procedure_watcher_stale_after_seconds
    try:
        items = await _drain_watched_procedures(list_procedures, deps)
    except UnauthorizedError as err:
        # The authz-gated drain was Denied: a missing read grant blinds the
        # watchdog. Re-raise as the scaffold type so the loop warns loudly
        # (edge-triggered) instead of burying it as a generic tick failure.
        raise WatcherReadUnauthorizedError(
            query_name=_READ_COMMAND,
            principal_id=PROCEDURE_WATCHER_AGENT_ID,
            reason=str(err),
        ) from err
    for item in items:
        if item.status not in _WATCHED_STATUSES:
            # Defensive guard against a future filter widening: only flag the
            # in-conduct states this watcher owns.
            continue
        base = item.last_status_changed_at
        if base is None:
            # No status-change timestamp recorded: cannot evaluate; defer.
            continue
        if not is_stalled(base, now, stale_after):
            # Fresh by status timestamp. For Running a later activity only makes
            # it fresher, so skipping here cannot hide a stall.
            continue
        last_progress_at = base
        if item.status == _STATUS_RUNNING:
            # Looks stale by status ts, but appending activity does NOT advance
            # it; confirm against the latest activity recorded_at before flagging.
            recency = await activity_lookup.read_procedure_activity_recency(
                procedure_id=item.procedure_id
            )
            activity_at = recency.latest_recorded_at
            if activity_at is not None and activity_at > last_progress_at:
                last_progress_at = activity_at
            if not is_stalled(last_progress_at, now, stale_after):
                continue  # actively logging: progressing, not stalled
        await _record_decision(
            deps,
            procedure_id=item.procedure_id,
            status=item.status,
            last_progress_at=last_progress_at,
            now=now,
        )


@contextlib.asynccontextmanager
async def procedure_watcher_lifespan(
    deps: Kernel,
    *,
    list_procedures: ListProceduresHandler,
    activity_lookup: ProcedureActivityLookup | None = None,
    interval_seconds: float | None = None,
) -> AsyncGenerator[None]:
    """Spawn the ProcedureWatcher loop for the duration of the context.

    No-op unless `settings.procedure_watcher_enabled` is True (default off, so a
    deployment opts in explicitly). `activity_lookup` defaults to the BC-local
    `_default_activity_lookup(deps)` (Postgres when a pool is present).
    """
    lookup = activity_lookup if activity_lookup is not None else _default_activity_lookup(deps)

    async def tick() -> None:
        await _watch_tick(deps=deps, list_procedures=list_procedures, activity_lookup=lookup)

    async def startup_probe() -> None:
        await probe_read_grant(
            deps,
            agent_id=PROCEDURE_WATCHER_AGENT_ID,
            read_command=_READ_COMMAND,
            log_prefix=_LOG_PREFIX,
            strict=deps.settings.watcher_authz_strict,
        )

    async with flag_watcher_lifespan(
        enabled=deps.settings.procedure_watcher_enabled,
        default_tick_seconds=deps.settings.procedure_watcher_tick_seconds,
        log_prefix=_LOG_PREFIX,
        task_name="procedure-watcher",
        tick=tick,
        startup_probe=startup_probe,
        interval_seconds=interval_seconds,
    ):
        yield


__all__ = ["is_stalled", "procedure_watcher_lifespan"]
