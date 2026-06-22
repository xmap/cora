"""Shared scaffold for the deterministic flag-only watcher agents.

Three near-identical composition-root watchers (ClearanceWatcher,
CalibrationWatcher, ProcedureWatcher) fired the rule-of-three: each is a periodic
loop that drains a list query, clocks each candidate against an operator
staleness window, and records ONE flag `Decision` per stall EPISODE, issuing no
command. The agent-INVARIANT mechanics live here; what genuinely differs per
agent (which list query it drains, which timestamp clocks it, whether it folds in
a recency signal to avoid false-flagging an active entity, and the Decision
context/choice vocabulary) stays in each watcher's own `_watch_tick`.

This module owns four invariants:

- `is_stalled` -- the pure staleness comparison (inclusive `>=` boundary).
- `derive_watcher_decision_id` -- the per-episode deterministic id
  (`uuid5(namespace, "decision:{entity_id}:{episode_at}")`) that makes a re-flag
  of the same stall episode a `ConcurrencyError` no-op.
- `record_watcher_decision` -- the `DecisionRegistered` envelope + append, including
  the idempotent ConcurrencyError swallow. The caller passes the per-agent
  vocabulary (context / choice / rule) and the already-formatted reasoning +
  inputs (which carry entity-specific fields).
- `flag_watcher_lifespan` -- the off-by-default gate, the periodic loop (a failed
  tick is logged and retried, cancellation propagates), and task teardown. The
  caller passes its `tick` closure (which closes over its own query handlers).

Each watcher keeps a thin per-agent `_record_decision` / `_derive_decision_id` /
`is_stalled` surface delegating here, so its behavior (and its tests) are
unchanged by the extraction.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from cora.api.errors import WatcherReadUnauthorizedError
from cora.decision.aggregates.decision import (
    DecisionChoice,
    DecisionConfidenceSource,
    DecisionContext,
    DecisionRegistered,
    DecisionRule,
    event_type_name,
    to_payload,
    validate_confidence,
    validate_inputs,
    validate_reasoning,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import ConcurrencyError, Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable
    from datetime import datetime

    from cora.infrastructure.kernel import Kernel

_log = get_logger(__name__)

_STREAM_TYPE = "Decision"


async def probe_read_grant(
    deps: Kernel,
    *,
    agent_id: UUID,
    read_command: str,
    log_prefix: str,
    strict: bool,
) -> None:
    """Startup probe: warn (or, in strict mode, refuse boot) when an ENABLED
    watcher's agent principal lacks the read grant it needs every tick.

    A no-op under a permissive Authorize (every authorize returns Allow), so dev
    / test never trip it; under a real policy a missing grant is the silent
    worse-than-none failure, so it is surfaced loudly at boot when an operator is
    watching. Probes the exact tuple the runtime drain uses (the read
    `command_name`, NIL conduit + surface). `strict` (operator opt-in via
    `settings.watcher_authz_strict`) escalates the warning to a boot refusal.
    """
    decision = await deps.authz.authorize(
        principal_id=agent_id,
        command_name=read_command,
        conduit_id=NIL_SENTINEL_ID,
        surface_id=NIL_SENTINEL_ID,
    )
    if not isinstance(decision, Deny):
        return
    if strict:
        raise WatcherReadUnauthorizedError(
            query_name=read_command, principal_id=agent_id, reason=decision.reason
        )
    _log.warning(
        f"{log_prefix}.read_unauthorized_at_startup",
        command_name=read_command,
        principal_id=str(agent_id),
        reason=decision.reason,
    )


def is_stalled(at: datetime, now: datetime, stale_after_seconds: float) -> bool:
    """Pure rule: an entity is stalled once it has sat past the staleness window
    without progress.

    Inclusive boundary: elapsed == window FLAGS (`>=`).
    """
    return (now - at).total_seconds() >= stale_after_seconds


def derive_watcher_decision_id(namespace: UUID, entity_id: UUID, episode_at: datetime) -> UUID:
    """Deterministic flag-Decision id for one stall episode of one entity."""
    return uuid5(namespace, f"decision:{entity_id}:{episode_at.isoformat()}")


async def record_watcher_decision(
    deps: Kernel,
    *,
    agent_id: UUID,
    context: str,
    choice: str,
    rule: str,
    command_name: str,
    decision_id: UUID,
    entity_id: UUID,
    now: datetime,
    reasoning: str,
    inputs: dict[str, str],
    log_prefix: str,
) -> None:
    """Append one DecisionRegistered flag for a stall episode.

    Idempotent: `decision_id` is the per-episode deterministic id (the caller
    derives it via `derive_watcher_decision_id` with its own namespace), so a re-flag
    of the same episode is a ConcurrencyError no-op. The caller owns the per-agent
    vocabulary and the entity-specific reasoning / inputs; `entity_id` is carried
    for the log line.
    """
    domain_event = DecisionRegistered(
        decision_id=decision_id,
        decided_by=ActorId(agent_id),
        context=DecisionContext(context).value,
        choice=DecisionChoice(choice).value,
        parent_id=None,
        override_kind=None,
        rule=DecisionRule(rule).value,
        reasoning=validate_reasoning(reasoning),
        confidence=validate_confidence(None),
        confidence_source=DecisionConfidenceSource.SELF_REPORTED,
        alternatives=(),
        inputs=validate_inputs(inputs),
        reasoning_signature=None,
        occurred_at=now,
    )
    new_event = to_new_event(
        event_type=event_type_name(domain_event),
        payload=to_payload(domain_event),
        occurred_at=now,
        event_id=uuid5(decision_id, "event:0"),
        command_name=command_name,
        correlation_id=deps.id_generator.new_id(),
        causation_id=None,
        principal_id=agent_id,
    )
    try:
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=decision_id,
            expected_version=0,
            events=[new_event],
        )
    except ConcurrencyError:
        _log.info(f"{log_prefix}.decision_already_written", entity_id=str(entity_id))
        return
    _log.info(f"{log_prefix}.flagged", entity_id=str(entity_id))


async def _watch_loop(
    tick: Callable[[], Awaitable[None]], interval_seconds: float, log_prefix: str
) -> None:
    """Periodic watch loop. A failed tick is logged; the next tick retries.

    A read-denial (`WatcherReadUnauthorizedError`, the watchdog blinded by a
    missing grant) is a FIRST-CLASS failure mode, caught before the generic
    handler and surfaced as a distinct, loud, edge-triggered warning: warn once
    per denial episode (not every tick -> no log spam), and log a recovery when a
    later tick reads successfully. The `read_denied` flag is a per-task loop local
    (each watcher runs its own loop), so per-watcher isolation is automatic.
    """
    read_denied = False
    while True:
        try:
            await tick()
            if read_denied:
                _log.info(f"{log_prefix}.read_authorized_recovered")
                read_denied = False
        except asyncio.CancelledError:
            raise
        except WatcherReadUnauthorizedError as err:
            if not read_denied:
                _log.warning(
                    f"{log_prefix}.read_unauthorized",
                    query_name=err.query_name,
                    principal_id=str(err.principal_id),
                    reason=err.reason,
                )
                read_denied = True
        except Exception:
            _log.exception(f"{log_prefix}.tick_failed")
        await asyncio.sleep(interval_seconds)


@contextlib.asynccontextmanager
async def flag_watcher_lifespan(
    *,
    enabled: bool,
    default_tick_seconds: float,
    log_prefix: str,
    task_name: str,
    tick: Callable[[], Awaitable[None]],
    startup_probe: Callable[[], Awaitable[None]] | None = None,
    interval_seconds: float | None = None,
) -> AsyncGenerator[None]:
    """Spawn a flag-watcher loop for the duration of the context.

    No-op unless `enabled` is True (the watchers ship off by default, so a
    deployment opts in explicitly). The caller supplies the `tick` closure and
    its own settings-derived `enabled` / `default_tick_seconds`. When `enabled`,
    an optional `startup_probe` (a `probe_read_grant` closure) runs once before
    the loop spawns, so a missing read grant is surfaced (or, in strict mode,
    refuses boot) at startup rather than only at the first denied tick.
    """
    if not enabled:
        _log.info(f"{log_prefix}.skipped", reason="disabled")
        yield
        return

    if startup_probe is not None:
        await startup_probe()

    interval = interval_seconds if interval_seconds is not None else default_tick_seconds
    _log.info(f"{log_prefix}.started", interval_seconds=interval)
    task = asyncio.create_task(_watch_loop(tick, interval, log_prefix), name=task_name)
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        _log.info(f"{log_prefix}.stopped")


__all__ = [
    "WatcherReadUnauthorizedError",
    "derive_watcher_decision_id",
    "flag_watcher_lifespan",
    "is_stalled",
    "probe_read_grant",
    "record_watcher_decision",
]
