"""StatusPush runtime: pushes a live, read-only snapshot outbound to an
external relay, for a status page served from a host outside this
deployment's own network.

## Why this exists, and why it is not a `list_*` consumer over HTTP

2-BM's deployment runs on a host with no inbound reachability from outside
its own controls network (see docs/deployments/2-bm's serving design). A
status page that should be viewable from elsewhere therefore cannot be
served FROM this host; instead this host must PUSH state OUT to a relay on
a host that does have reach, over a connection this host itself opens. That
asymmetry, push rather than serve, is the entire reason this module exists
alongside the `list_*` REST/MCP surfaces rather than instead of them.

## Why this is a bespoke loop, not `_flag_watcher.flag_watcher_lifespan`

Every other composition-root watcher in this package (`_calibration_watcher`,
`_clearance_watcher`, `_procedure_watcher`, `_campaign_watcher`) does one
self-contained unit of work per tick: drain a query, compare against a rule,
maybe append one Decision. `flag_watcher_lifespan` is built for exactly that
shape. This module instead holds one PERSISTENT outbound connection across
many ticks (reopening it every 1-2 seconds would be pure handshake overhead
for a live feed), and reconnects with backoff when the relay is unreachable
rather than treating each drop as an isolated tick failure. That is closer
to `_run_witness.py`'s hand-rolled shape than to the flag-watcher family.

## Current scope

Each tick reads open Runs (`Running` + `Held`) via the existing `list_runs`
handler and pushes `{run_id, name, status}` per run. No progress data yet,
and no other domains yet. The payload is a full snapshot every push, never
a delta: a fresh viewer, a reconnecting viewer, and a restarted relay are
all served by "here is the current one".

## Principal identity: a deliberate simplification, revisit before widening

Every other watcher here authenticates as its own seeded Agent (a real
Actor with its own grant set, so a missing grant is auditable per-agent).
This one reads a single command (`ListRuns`) and authors nothing, so this
uses `SYSTEM_PRINCIPAL_ID` rather than standing up a full Agent+Actor seed
for one read. Once the read scope widens to Subject / Campaign / Dataset /
Decision / Clearance / Enclosure, a dedicated seeded identity (mirroring
`agent/seed_calibration_watcher.py`) earns its keep: its grant set becomes
independently auditable, and `probe_read_grant` becomes worth calling once
per command rather than being skipped as it is here.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
from typing import TYPE_CHECKING, Any

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from cora.infrastructure.logging import get_logger
from cora.infrastructure.record_export import render_value
from cora.infrastructure.routing import NIL_SENTINEL_ID, SYSTEM_PRINCIPAL_ID
from cora.run.errors import UnauthorizedError
from cora.run.features.list_runs import ListRuns

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cora.infrastructure.kernel import Kernel
    from cora.run.features.list_runs.handler import Handler as ListRunsHandler

_log = get_logger(__name__)

_LOG_PREFIX = "status_push"
_OPEN_RUN_STATUSES = ("Running", "Held")
_PAGE_LIMIT = 100
_HEARTBEAT_TICKS = 5
"""Push unconditionally every this-many ticks even with no change, so a
receiver can tell "nothing changed" apart from "the producer died"; the
relay's own staleness clock is the other half of that distinction."""

_RECONNECT_INITIAL_SECONDS = 1.0
_RECONNECT_MAX_SECONDS = 60.0


async def _drain_open_runs(list_runs: ListRunsHandler, deps: Kernel) -> list[dict[str, Any]]:
    """Page through list_runs for each open status, rendering JSON-safe rows."""
    rows: list[dict[str, Any]] = []
    for status in _OPEN_RUN_STATUSES:
        cursor: str | None = None
        while True:
            page = await list_runs(
                ListRuns(status=status, cursor=cursor, limit=_PAGE_LIMIT),
                principal_id=SYSTEM_PRINCIPAL_ID,
                correlation_id=deps.id_generator.new_id(),
                surface_id=NIL_SENTINEL_ID,
            )
            rows.extend(
                {
                    "run_id": render_value(item.run_id),
                    "name": item.name,
                    "status": item.status,
                }
                for item in page.items
            )
            if page.next_cursor is None:
                break
            cursor = page.next_cursor
    return rows


def _content_hash(runs: list[dict[str, Any]]) -> str:
    """Stable hash over the change-relevant payload, excluding generated_at
    and sequence, so an unchanged tick can be told apart from a real change."""
    canonical = json.dumps(runs, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_snapshot(
    *, runs: list[dict[str, Any]], sequence: int, generated_at: str, producer_id: str
) -> dict[str, Any]:
    """Assemble the pushed payload. A pure function so it is unit-testable
    without a socket, a database, or a clock."""
    return {
        "schema_version": 1,
        "producer_id": producer_id,
        "sequence": sequence,
        "generated_at": generated_at,
        "runs": runs,
    }


async def _push_loop(
    deps: Kernel, *, list_runs: ListRunsHandler, producer_id: str, url: str
) -> None:
    """Reconnect-with-backoff outer loop; one open connection sends many
    ticks. `websockets`' own `InvalidStatus` (bad token) and `ConnectionClosed`
    (relay restarted, network blip) both fall through to a fresh backoff
    reconnect; nothing here distinguishes them further, since v1's only
    remedy for either is "try again"."""
    token = deps.settings.status_push_token
    headers = {"Authorization": f"Bearer {token.get_secret_value()}"} if token is not None else {}

    backoff = _RECONNECT_INITIAL_SECONDS
    sequence = 0
    last_hash: str | None = None
    tick_seconds = deps.settings.status_push_tick_seconds

    while True:
        try:
            async with connect(url, additional_headers=headers) as sock:
                _log.info(f"{_LOG_PREFIX}.connected", url=url)
                backoff = _RECONNECT_INITIAL_SECONDS
                last_hash = None  # force one full push right after (re)connect
                ticks_since_push = _HEARTBEAT_TICKS  # push immediately on connect
                while True:
                    runs = await _drain_open_runs(list_runs, deps)
                    content_hash = _content_hash(runs)
                    changed = content_hash != last_hash
                    heartbeat_due = ticks_since_push >= _HEARTBEAT_TICKS
                    if changed or heartbeat_due:
                        sequence += 1
                        snapshot = build_snapshot(
                            runs=runs,
                            sequence=sequence,
                            generated_at=deps.clock.now().isoformat(),
                            producer_id=producer_id,
                        )
                        await sock.send(json.dumps(snapshot))
                        last_hash = content_hash
                        ticks_since_push = 0
                    else:
                        ticks_since_push += 1
                    await asyncio.sleep(tick_seconds)
        except asyncio.CancelledError:
            raise
        except UnauthorizedError:
            _log.exception(f"{_LOG_PREFIX}.read_unauthorized")
            await asyncio.sleep(tick_seconds)
        except (ConnectionClosed, InvalidStatus, OSError) as err:
            _log.warning(f"{_LOG_PREFIX}.disconnected", reason=str(err), retry_in=backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _RECONNECT_MAX_SECONDS)


@contextlib.asynccontextmanager
async def status_push_lifespan(deps: Kernel, *, list_runs: ListRunsHandler) -> AsyncGenerator[None]:
    """Spawn the StatusPush loop for the duration of the context.

    No-op unless `settings.status_push_enabled` is True (default off) AND
    `settings.status_push_url` is configured; the latter mirrors the
    `LLM_ENABLED`-without-a-key posture elsewhere in this file, log once and
    stand down rather than crash the app over a deployment that has not
    finished configuring this feature. `producer_id` is drawn from
    `deps.id_generator` lazily, here, rather than accepted as a caller-supplied
    parameter, so booting the app with this feature off (the default, and
    every test's `create_app()`) never consumes an id from a test's
    `FixedIdGenerator` queue.
    """
    if not deps.settings.status_push_enabled:
        _log.info(f"{_LOG_PREFIX}.skipped", reason="disabled")
        yield
        return
    url = deps.settings.status_push_url
    if not url:
        _log.warning(f"{_LOG_PREFIX}.skipped", reason="no_url_configured")
        yield
        return

    producer_id = str(deps.id_generator.new_id())
    _log.info(
        f"{_LOG_PREFIX}.started",
        tick_seconds=deps.settings.status_push_tick_seconds,
    )
    task = asyncio.create_task(
        _push_loop(deps, list_runs=list_runs, producer_id=producer_id, url=url),
        name="status-push",
    )
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        _log.info(f"{_LOG_PREFIX}.stopped")


__all__ = ["build_snapshot", "status_push_lifespan"]
