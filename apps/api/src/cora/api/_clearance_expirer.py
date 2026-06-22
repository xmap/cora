"""ClearanceExpirer runtime: the 3rd ACTIVE agent.

A periodic background task, hosted at the composition root (`cora.api`)
because it issues a Safety BC command AND composes Decision BC events; only
`cora.api` may depend on both (same placement rationale as `_run_supervisor`
and `_enclosure_permit_observer`, and the reason it sidesteps the
`test_no_cross_bc_features_imports` ban, which scans BC packages, not the
composition root). See [[project-clearance-window-expirer-design]].

## What v1 does

Each tick it lists Active safety Clearances, selects those whose validity
window has elapsed (`valid_until is not None and valid_until <= now`), and for
each issues `expire_clearance` (Active -> Expired) through the authorized
command path. On a SUCCESSFUL expiry it records one
`Decision(context=ClearanceExpiry, choice=Expire)` (a Decision exists only for
a real expiry, never for a race that found the clearance already gone). It
realizes Safety BC watch #7 (auto-expiry on `valid_until`, deferred there).

The agent's in-process filter is the SOLE window gate: the `expire_clearance`
decider is intentionally a pure `Active -> Expired` transition that does NOT
re-check `valid_until` (parity with the human expire path). It never touches
indefinite (`valid_until is None`) or non-Active clearances.

## Fail-safe and bounded

Expiry is wind-down only (it removes a stale authorization), so it can never
drive hardware or widen access. Over-expiry is operator-recoverable (amend /
new clearance) and the strict decider blocks double-expiry. A clearance that
changed under us (already Expired / Superseded) is a benign skip, not an error.
The runtime gates on `Actor.active`, so deactivating the agent Actor stops it.

## Authorization

`expire_clearance` flows through the normal bound handler (Authorize port +
decider). Under the default `AllowAllAuthorize` the agent is permitted; under
`TrustAuthorize` the operator's configured Policy must grant this principal
ExpireClearance. No bypass.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from cora.access.aggregates.actor import load_actor
from cora.agent.seed_clearance_expirer import CLEARANCE_EXPIRER_AGENT_ID
from cora.api._flag_watcher import WatcherReadUnauthorizedError, probe_read_grant
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_CLEARANCE_EXPIRY,
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
from cora.infrastructure.ports import ConcurrencyError
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.safety.aggregates.clearance import (
    ClearanceCannotExpireError,
    ClearanceNotFoundError,
    InvalidClearanceExpireReasonError,
)
from cora.safety.errors import UnauthorizedError
from cora.safety.features.expire_clearance import ExpireClearance
from cora.safety.features.list_clearances import ListClearances
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from datetime import datetime

    from cora.infrastructure.kernel import Kernel
    from cora.safety.features.expire_clearance.handler import Handler as ExpireClearanceHandler
    from cora.safety.features.list_clearances import ClearanceSummaryItem
    from cora.safety.features.list_clearances.handler import Handler as ListClearancesHandler

_log = get_logger(__name__)

_RULE = "agent:ClearanceExpirer:v1"
_COMMAND_NAME = "ClearanceExpirerTick"
_READ_COMMAND = "ListClearances"
_STREAM_TYPE = "Decision"
_PAGE_LIMIT = 100
_CHOICE_EXPIRE = "Expire"
_EXPIRE_REASON = "Validity window elapsed (valid_until passed); auto-expired by ClearanceExpirer."

# Stable namespace for deriving the deterministic CREATE Decision id from the
# clearance id, so a re-run cannot write a duplicate Decision (eeee block,
# distinct from the seed envelope ids).
_DECISION_NAMESPACE = UUID("01900000-0000-7000-8000-0000eeee0002")


def is_window_elapsed(valid_until: datetime | None, now: datetime) -> bool:
    """Pure rule: an Active clearance is due for expiry once its window passed.

    Inclusive boundary: `valid_until == now` EXPIRES. A clearance with no
    `valid_until` (indefinite) is never due.
    """
    return valid_until is not None and valid_until <= now


def _derive_decision_id(clearance_id: UUID) -> UUID:
    """Deterministic ClearanceExpiry Decision id from the clearance id."""
    return uuid5(_DECISION_NAMESPACE, f"decision:{clearance_id}")


async def _record_decision(
    deps: Kernel,
    *,
    decision_id: UUID,
    clearance_id: UUID,
    valid_until: datetime,
    now: datetime,
) -> None:
    """Append one DecisionRegistered(context=ClearanceExpiry) (idempotent).

    Mirrors `_run_supervisor._record_decision`. A ConcurrencyError means a prior
    run already wrote this id (the clearance was expired by an earlier tick);
    treat as success.
    """
    domain_event = DecisionRegistered(
        decision_id=decision_id,
        decided_by=ActorId(CLEARANCE_EXPIRER_AGENT_ID),
        context=DecisionContext(DECISION_CONTEXT_CLEARANCE_EXPIRY).value,
        choice=DecisionChoice(_CHOICE_EXPIRE).value,
        parent_id=None,
        override_kind=None,
        rule=DecisionRule(_RULE).value,
        reasoning=validate_reasoning(
            "Validity window elapsed: the clearance's valid_until passed while it "
            "was still Active, so the stale authorization was expired."
        ),
        confidence=validate_confidence(None),
        confidence_source=DecisionConfidenceSource.SELF_REPORTED,
        alternatives=(),
        inputs=validate_inputs(
            {
                "clearance_id": str(clearance_id),
                "valid_until": valid_until.isoformat(),
                "occurred_at": now.isoformat(),
            }
        ),
        reasoning_signature=None,
        occurred_at=now,
    )
    new_event = to_new_event(
        event_type=event_type_name(domain_event),
        payload=to_payload(domain_event),
        occurred_at=now,
        event_id=uuid5(decision_id, "event:0"),
        command_name=_COMMAND_NAME,
        correlation_id=deps.id_generator.new_id(),
        causation_id=None,
        principal_id=CLEARANCE_EXPIRER_AGENT_ID,
    )
    try:
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=decision_id,
            expected_version=0,
            events=[new_event],
        )
    except ConcurrencyError:
        _log.info("clearance_expirer.decision_already_written", clearance_id=str(clearance_id))


async def _expire_one(
    deps: Kernel,
    expire_clearance: ExpireClearanceHandler,
    *,
    clearance_id: UUID,
    valid_until: datetime,
    now: datetime,
) -> None:
    """Expire one elapsed clearance, then record its Decision on success."""
    try:
        await expire_clearance(
            ExpireClearance(clearance_id=clearance_id, reason=_EXPIRE_REASON),
            principal_id=CLEARANCE_EXPIRER_AGENT_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=NIL_SENTINEL_ID,
        )
    except (ClearanceNotFoundError, ClearanceCannotExpireError) as exc:
        # The clearance changed under us between the list read and the expire
        # (someone else expired / superseded / amended it): a benign no-op.
        _log.info(
            "clearance_expirer.expire_skipped",
            clearance_id=str(clearance_id),
            reason=type(exc).__name__,
        )
        return
    except InvalidClearanceExpireReasonError:
        # Cannot happen with the fixed reason; defensive guard so a future reason
        # change cannot wedge the loop.
        _log.warning("clearance_expirer.invalid_reason", clearance_id=str(clearance_id))
        return
    except UnauthorizedError:
        # Configuration fault: the principal is not granted ExpireClearance.
        # Log loudly; take no autonomous action.
        _log.warning("clearance_expirer.expire_unauthorized", clearance_id=str(clearance_id))
        return
    await _record_decision(
        deps,
        decision_id=_derive_decision_id(clearance_id),
        clearance_id=clearance_id,
        valid_until=valid_until,
        now=now,
    )
    _log.info("clearance_expirer.expired", clearance_id=str(clearance_id))


async def _drain_active_clearances(
    list_clearances: ListClearancesHandler, deps: Kernel
) -> list[ClearanceSummaryItem]:
    """Page through list_clearances for status=Active; return all rows."""
    items: list[ClearanceSummaryItem] = []
    cursor: str | None = None
    while True:
        page = await list_clearances(
            ListClearances(status="Active", cursor=cursor, limit=_PAGE_LIMIT),
            principal_id=CLEARANCE_EXPIRER_AGENT_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=NIL_SENTINEL_ID,
        )
        items.extend(page.items)
        if page.next_cursor is None:
            return items
        cursor = page.next_cursor


async def _expire_tick(
    *,
    deps: Kernel,
    list_clearances: ListClearancesHandler,
    expire_clearance: ExpireClearanceHandler,
) -> None:
    """One expiry sweep over all Active clearances."""
    actor = await load_actor(deps.event_store, CLEARANCE_EXPIRER_AGENT_ID)
    if actor is None or not actor.active:
        # Agent not seeded yet, or deactivated by an operator: stand down.
        return

    now = deps.clock.now()
    try:
        items = await _drain_active_clearances(list_clearances, deps)
    except UnauthorizedError as err:
        # The authz-gated drain was Denied: a missing ListClearances read grant
        # blinds the expirer. Re-raise as the scaffold type so the loop warns
        # loudly (edge-triggered) instead of burying it as a generic tick failure.
        raise WatcherReadUnauthorizedError(
            query_name=_READ_COMMAND,
            principal_id=CLEARANCE_EXPIRER_AGENT_ID,
            reason=str(err),
        ) from err
    for item in items:
        valid_until = item.valid_until
        if valid_until is None or not is_window_elapsed(valid_until, now):
            continue
        await _expire_one(
            deps,
            expire_clearance,
            clearance_id=item.clearance_id,
            valid_until=valid_until,
            now=now,
        )


async def _expire_loop(
    deps: Kernel,
    list_clearances: ListClearancesHandler,
    expire_clearance: ExpireClearanceHandler,
    interval_seconds: float,
) -> None:
    """Periodic expiry loop. A failed tick is logged; the next tick retries."""
    read_denied = False
    while True:
        try:
            await _expire_tick(
                deps=deps,
                list_clearances=list_clearances,
                expire_clearance=expire_clearance,
            )
            if read_denied:
                _log.info("clearance_expirer.read_authorized_recovered")
                read_denied = False
        except asyncio.CancelledError:
            raise
        except WatcherReadUnauthorizedError as err:
            # A missing ListClearances grant blinds the expirer; surface it loudly
            # (edge-triggered, once per denial episode) rather than as a generic
            # tick failure. The drain stands down for the tick.
            if not read_denied:
                _log.warning(
                    "clearance_expirer.read_unauthorized",
                    query_name=err.query_name,
                    principal_id=str(err.principal_id),
                    reason=err.reason,
                )
                read_denied = True
        except Exception:
            _log.exception("clearance_expirer.tick_failed")
        await asyncio.sleep(interval_seconds)


@contextlib.asynccontextmanager
async def clearance_expirer_lifespan(
    deps: Kernel,
    *,
    list_clearances: ListClearancesHandler,
    expire_clearance: ExpireClearanceHandler,
    interval_seconds: float | None = None,
) -> AsyncGenerator[None]:
    """Spawn the ClearanceExpirer loop for the duration of the context.

    No-op unless `settings.clearance_expirer_enabled` is True (default off, so a
    deployment opts in explicitly).
    """
    if not deps.settings.clearance_expirer_enabled:
        _log.info("clearance_expirer.skipped", reason="disabled")
        yield
        return

    await probe_read_grant(
        deps,
        agent_id=CLEARANCE_EXPIRER_AGENT_ID,
        read_command=_READ_COMMAND,
        log_prefix="clearance_expirer",
        strict=deps.settings.watcher_authz_strict,
    )

    interval = (
        interval_seconds
        if interval_seconds is not None
        else deps.settings.clearance_expirer_tick_seconds
    )
    _log.info("clearance_expirer.started", interval_seconds=interval)
    task = asyncio.create_task(
        _expire_loop(deps, list_clearances, expire_clearance, interval),
        name="clearance-expirer",
    )
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        _log.info("clearance_expirer.stopped")


__all__ = ["clearance_expirer_lifespan", "is_window_elapsed"]
