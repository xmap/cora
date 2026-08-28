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

Each tick reads and pushes:

  - open Runs (`Running` + `Held`), each with `progress` from
    `RunWitnessRecorder.progress_readings()` (`{}` when unavailable; see
    `_render_progress`)
  - open Subjects (`Received` / `Mounted` / `Measured` / `Removed`;
    `Returned` / `Stored` / `Discarded` are terminal and dropped)
  - open Campaigns (`Planned` / `Active` / `Held`; `Closed` / `Abandoned`
    are terminal and dropped)
  - Datasets produced by an on-screen Run (bounded by the open-run count,
    not a separate unbounded drain)
  - Active Clearances (the safety-gate status a viewer most wants: is
    something required to start a run currently in force)
  - Active Enclosures (permit status: the most direct "is it safe right
    now" answer CORA records)
  - the most recent Decisions since this process started, tail-followed
    (see `_DecisionTail`) rather than paged from the beginning, since
    Decisions have no "open" status to filter on and the table is
    unbounded

The payload is a full snapshot every push, never a delta: a fresh viewer,
a reconnecting viewer, and a restarted relay are all served by "here is
the current one".

Deliberately reads ONLY the in-memory `RunWitnessRecorder` for progress,
not the Postgres-durable `entries_run_observations` fallback
`PostgresRunChannelLookup` would offer for a run whose capture is not open
in this process: that path is capped at `capture_progress_flush_tick_seconds`
(10s by default) and never carries `commanded_total` (dropped at the
`ObservationInput` boundary), so it would not feel live and would silently
lack the "of M" figure. Revisit if this ever runs against a Run witnessed
by a different process than the one pushing.

## Principal identity: the widening trigger has now fired

Every other watcher here authenticates as its own seeded Agent (a real
Actor with its own grant set, so a missing grant is auditable per-agent).
This module still uses `SYSTEM_PRINCIPAL_ID` for every read: the read scope
has now widened past the single `ListRuns` command this module started
with, to seven commands across seven BCs, which is exactly the trigger this
docstring named for standing up a dedicated seeded identity (mirroring
`agent/seed_calibration_watcher.py`). That identity is NOT built in this
change; doing so is a follow-up, tracked so the deferral is visible rather
than silently indefinite. Until then, a Trust Policy that denies any of the
seven read commands to `SYSTEM_PRINCIPAL_ID` blinds this feature for that
domain only (each drain is independently try/except-guarded; see
`_push_loop`), never the others.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
from collections import deque
from typing import TYPE_CHECKING, Any
from uuid import UUID

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from cora.campaign.errors import UnauthorizedError as _CampaignUnauthorizedError
from cora.campaign.features.list_campaigns import ListCampaigns
from cora.data.errors import UnauthorizedError as _DataUnauthorizedError
from cora.data.features.list_datasets import ListDatasets
from cora.decision.errors import UnauthorizedError as _DecisionUnauthorizedError
from cora.decision.features.list_decisions import ListDecisions
from cora.enclosure.errors import UnauthorizedError as _EnclosureUnauthorizedError
from cora.enclosure.features.list_enclosures import ListEnclosures
from cora.infrastructure.logging import get_logger
from cora.infrastructure.projection import encode_cursor
from cora.infrastructure.record_export import render_value
from cora.infrastructure.routing import NIL_SENTINEL_ID, SYSTEM_PRINCIPAL_ID
from cora.run.errors import UnauthorizedError as _RunUnauthorizedError
from cora.run.features.list_runs import ListRuns
from cora.safety.errors import UnauthorizedError as _SafetyUnauthorizedError
from cora.safety.features.list_clearances import ListClearances
from cora.subject.errors import UnauthorizedError as _SubjectUnauthorizedError
from cora.subject.features.list_subjects import ListSubjects

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

    from cora.api._run_witness import RunWitnessRecorder
    from cora.campaign.features.list_campaigns.handler import Handler as ListCampaignsHandler
    from cora.campaign.features.list_campaigns.query import CampaignStatusFilter
    from cora.data.features.list_datasets.handler import Handler as ListDatasetsHandler
    from cora.decision.features.list_decisions.handler import Handler as ListDecisionsHandler
    from cora.enclosure.features.list_enclosures.handler import Handler as ListEnclosuresHandler
    from cora.infrastructure.kernel import Kernel
    from cora.run.features.list_runs.handler import Handler as ListRunsHandler
    from cora.safety.features.list_clearances.handler import Handler as ListClearancesHandler
    from cora.subject.features.list_subjects.handler import Handler as ListSubjectsHandler

_log = get_logger(__name__)

_LOG_PREFIX = "status_push"
_PAGE_LIMIT = 100
_HEARTBEAT_TICKS = 5
"""Push unconditionally every this-many ticks even with no change, so a
receiver can tell "nothing changed" apart from "the producer died"; the
relay's own staleness clock is the other half of that distinction."""

_RECONNECT_INITIAL_SECONDS = 1.0
_RECONNECT_MAX_SECONDS = 60.0

_OPEN_RUN_STATUSES = ("Running", "Held")
_OPEN_SUBJECT_STATUSES = ("Received", "Mounted", "Measured", "Removed")
_OPEN_CAMPAIGN_STATUSES: list[CampaignStatusFilter] = ["Planned", "Active", "Held"]
_ACTIVE_CLEARANCE_STATUS = "Active"
_ACTIVE_ENCLOSURE_LIFECYCLE = "Active"
_DECISION_RING_SIZE = 20
_MIN_UUID = UUID(int=0)
"""Sentinel id for `_DecisionTail`'s starting cursor: paired with "now" as
the cursor's time component, so the `(time, id) > (cursor_time, cursor_id)`
keyset predicate admits anything at or after this instant regardless of id,
rather than requiring an id greater than a real (and otherwise arbitrary)
UUID at the same microsecond."""

# Every BC's UnauthorizedError is its own class (no shared base, per the
# per-BC-application-error-namespace convention), so widening past one
# domain means widening this tuple, not the shape of the catch.
_UNAUTHORIZED_ERRORS = (
    _RunUnauthorizedError,
    _SubjectUnauthorizedError,
    _CampaignUnauthorizedError,
    _DataUnauthorizedError,
    _DecisionUnauthorizedError,
    _SafetyUnauthorizedError,
    _EnclosureUnauthorizedError,
)


async def _drain_all(call: Callable[[str | None], Awaitable[Any]]) -> list[Any]:
    """Page through a list_* handler call until `next_cursor` is `None`.

    `call` closes over everything but the cursor (the query's other
    filters, the handler, the principal), so this stays generic across
    every domain's distinct item shape.
    """
    items: list[Any] = []
    cursor: str | None = None
    while True:
        page = await call(cursor)
        items.extend(page.items)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    return items


def _render_progress(run_id: UUID, witness_recorder: RunWitnessRecorder | None) -> dict[str, Any]:
    """The run's progress readings, JSON-safe, or `{}` when unavailable.

    `{}` covers three cases alike, deliberately not distinguished on the
    wire: witnessing is disabled entirely (`witness_recorder is None`), the
    capture behind this run is not open in this process, and the capture is
    open but has not produced a reading yet. All three mean the viewer has
    no progress number to show; none of them is an error.
    """
    if witness_recorder is None:
        return {}
    readings = witness_recorder.progress_readings().get(run_id)
    if not readings:
        return {}
    return {
        role: {
            "value": observation.value,
            "commanded_total": observation.commanded_total,
            "observed_at": render_value(observation.observed_at),
        }
        for role, observation in readings.items()
    }


async def _drain_open_runs(
    list_runs: ListRunsHandler, deps: Kernel, *, witness_recorder: RunWitnessRecorder | None
) -> tuple[list[dict[str, Any]], list[UUID]]:
    """Returns the rendered (JSON-safe) rows AND the raw run_id UUIDs.

    Both are needed: the rows go straight into the payload, but a caller
    filtering a sibling domain by `producing_run_id` (`_drain_datasets_for_runs`)
    needs real `UUID` objects, not `render_value`'s string form -- a query
    built from the rendered strings would never match anything.
    """
    rows: list[dict[str, Any]] = []
    raw_run_ids: list[UUID] = []
    for status in _OPEN_RUN_STATUSES:
        items = await _drain_all(
            lambda cursor, status=status: list_runs(
                ListRuns(status=status, cursor=cursor, limit=_PAGE_LIMIT),
                principal_id=SYSTEM_PRINCIPAL_ID,
                correlation_id=deps.id_generator.new_id(),
                surface_id=NIL_SENTINEL_ID,
            )
        )
        for item in items:
            rows.append(
                {
                    "run_id": render_value(item.run_id),
                    "name": item.name,
                    "status": item.status,
                    "progress": _render_progress(item.run_id, witness_recorder),
                }
            )
            raw_run_ids.append(item.run_id)
    return rows, raw_run_ids


async def _drain_open_subjects(
    list_subjects: ListSubjectsHandler, deps: Kernel
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for status in _OPEN_SUBJECT_STATUSES:
        items = await _drain_all(
            lambda cursor, status=status: list_subjects(
                ListSubjects(status=status, cursor=cursor, limit=_PAGE_LIMIT),
                principal_id=SYSTEM_PRINCIPAL_ID,
                correlation_id=deps.id_generator.new_id(),
                surface_id=NIL_SENTINEL_ID,
            )
        )
        rows.extend(
            {"subject_id": render_value(item.subject_id), "name": item.name, "status": item.status}
            for item in items
        )
    return rows


async def _drain_open_campaigns(
    list_campaigns: ListCampaignsHandler, deps: Kernel
) -> list[dict[str, Any]]:
    items = await _drain_all(
        lambda cursor: list_campaigns(
            ListCampaigns(statuses=_OPEN_CAMPAIGN_STATUSES, cursor=cursor, limit=_PAGE_LIMIT),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=NIL_SENTINEL_ID,
        )
    )
    return [
        {
            "campaign_id": render_value(item.campaign_id),
            "name": item.name,
            "intent": item.intent,
            "status": item.status,
            "run_count": item.run_count,
        }
        for item in items
    ]


async def _drain_datasets_for_runs(
    list_datasets: ListDatasetsHandler, deps: Kernel, *, run_ids: list[UUID]
) -> list[dict[str, Any]]:
    """Datasets produced by an on-screen Run, one query per run_id.

    Bounded by the open-run count (small; see `_OPEN_RUN_STATUSES`), not a
    separate unbounded drain: a facility's whole dataset history is not
    something a live status page needs, only what the runs on screen just
    produced.
    """
    rows: list[dict[str, Any]] = []
    for run_id in run_ids:
        items = await _drain_all(
            lambda cursor, run_id=run_id: list_datasets(
                ListDatasets(producing_run_id=run_id, cursor=cursor, limit=_PAGE_LIMIT),
                principal_id=SYSTEM_PRINCIPAL_ID,
                correlation_id=deps.id_generator.new_id(),
                surface_id=NIL_SENTINEL_ID,
            )
        )
        rows.extend(
            {
                "dataset_id": render_value(item.dataset_id),
                "name": item.name,
                "status": item.status,
                "producing_run_id": render_value(item.producing_run_id),
            }
            for item in items
        )
    return rows


async def _drain_active_clearances(
    list_clearances: ListClearancesHandler, deps: Kernel
) -> list[dict[str, Any]]:
    items = await _drain_all(
        lambda cursor: list_clearances(
            ListClearances(status=_ACTIVE_CLEARANCE_STATUS, cursor=cursor, limit=_PAGE_LIMIT),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=NIL_SENTINEL_ID,
        )
    )
    return [
        {
            "clearance_id": render_value(item.clearance_id),
            "template_code": item.template_code,
            "risk_band": item.risk_band,
            "valid_until": render_value(item.valid_until),
        }
        for item in items
    ]


async def _drain_active_enclosures(
    list_enclosures: ListEnclosuresHandler, deps: Kernel
) -> list[dict[str, Any]]:
    items = await _drain_all(
        lambda cursor: list_enclosures(
            ListEnclosures(lifecycle=_ACTIVE_ENCLOSURE_LIFECYCLE, cursor=cursor, limit=_PAGE_LIMIT),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=NIL_SENTINEL_ID,
        )
    )
    return [
        {
            "enclosure_id": render_value(item.enclosure_id),
            "name": item.name,
            "permit_status": item.permit_status,
            "facility_code": item.facility_code,
        }
        for item in items
    ]


class _DecisionTail:
    """Tail-follows `list_decisions` since this instance was created,
    keeping only the most recent `_DECISION_RING_SIZE`.

    Decisions carry no "open" status to filter on and the table is
    unbounded, so re-draining from the beginning every tick (the shape
    every other domain in this module uses) is both wrong and slow: it
    would replay the facility's entire decision history into memory once
    per tick, forever. Instead this holds a cursor forward across ticks
    (and across reconnects: one instance lives for the whole `_push_loop`
    call, not per-connection) and only ever asks for what is new.

    The cursor starts at "now" rather than the beginning of the stream, so
    the ring is genuinely empty on construction and only ever fills with
    Decisions made after this process started; there is no cheap way to
    seek a keyset cursor to "the last N rows" without a descending query,
    which `list_decisions` does not offer.
    """

    def __init__(self, *, started_at_cursor: str) -> None:
        self._cursor: str | None = started_at_cursor
        self._ring: deque[dict[str, Any]] = deque(maxlen=_DECISION_RING_SIZE)

    async def poll(
        self, list_decisions: ListDecisionsHandler, deps: Kernel
    ) -> list[dict[str, Any]]:
        cursor = self._cursor
        newest_cursor = cursor
        while True:
            page = await list_decisions(
                ListDecisions(cursor=cursor, limit=_PAGE_LIMIT),
                principal_id=SYSTEM_PRINCIPAL_ID,
                correlation_id=deps.id_generator.new_id(),
                surface_id=NIL_SENTINEL_ID,
            )
            for item in page.items:
                self._ring.append(
                    {
                        "decision_id": render_value(item.decision_id),
                        "decided_by": render_value(item.decided_by),
                        "choice": item.choice,
                        "confidence_band": item.confidence_band,
                        "created_at": render_value(item.created_at),
                    }
                )
            if page.next_cursor is None:
                break
            newest_cursor = page.next_cursor
            cursor = page.next_cursor
        self._cursor = newest_cursor
        return list(self._ring)


def _content_hash(payload: dict[str, Any]) -> str:
    """Stable hash over the change-relevant payload, excluding generated_at
    and sequence, so an unchanged tick can be told apart from a real change."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_snapshot(
    *,
    runs: list[dict[str, Any]],
    subjects: list[dict[str, Any]],
    campaigns: list[dict[str, Any]],
    datasets: list[dict[str, Any]],
    clearances: list[dict[str, Any]],
    enclosures: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    sequence: int,
    generated_at: str,
    producer_id: str,
) -> dict[str, Any]:
    """Assemble the pushed payload. A pure function so it is unit-testable
    without a socket, a database, or a clock."""
    return {
        "schema_version": 1,
        "producer_id": producer_id,
        "sequence": sequence,
        "generated_at": generated_at,
        "runs": runs,
        "subjects": subjects,
        "campaigns": campaigns,
        "datasets": datasets,
        "clearances": clearances,
        "enclosures": enclosures,
        "decisions": decisions,
    }


async def _build_payload_fields(
    deps: Kernel,
    *,
    list_runs: ListRunsHandler,
    list_subjects: ListSubjectsHandler,
    list_campaigns: ListCampaignsHandler,
    list_datasets: ListDatasetsHandler,
    list_clearances: ListClearancesHandler,
    list_enclosures: ListEnclosuresHandler,
    decision_tail: _DecisionTail,
    list_decisions: ListDecisionsHandler,
    witness_recorder: RunWitnessRecorder | None,
) -> dict[str, list[dict[str, Any]]]:
    """Every domain's rows for one tick. Each drain is independently
    guarded by the caller's `except _UNAUTHORIZED_ERRORS` (per-domain, not
    caught here) so a missing grant on one command blinds only that
    section of the page, never the whole tick."""
    runs, raw_run_ids = await _drain_open_runs(list_runs, deps, witness_recorder=witness_recorder)
    return {
        "runs": runs,
        "subjects": await _drain_open_subjects(list_subjects, deps),
        "campaigns": await _drain_open_campaigns(list_campaigns, deps),
        "datasets": await _drain_datasets_for_runs(list_datasets, deps, run_ids=raw_run_ids),
        "clearances": await _drain_active_clearances(list_clearances, deps),
        "enclosures": await _drain_active_enclosures(list_enclosures, deps),
        "decisions": await decision_tail.poll(list_decisions, deps),
    }


async def _push_loop(
    deps: Kernel,
    *,
    list_runs: ListRunsHandler,
    list_subjects: ListSubjectsHandler,
    list_campaigns: ListCampaignsHandler,
    list_datasets: ListDatasetsHandler,
    list_clearances: ListClearancesHandler,
    list_enclosures: ListEnclosuresHandler,
    list_decisions: ListDecisionsHandler,
    producer_id: str,
    url: str,
    witness_recorder: RunWitnessRecorder | None,
) -> None:
    """Reconnect-with-backoff outer loop; one open connection sends many
    ticks. `websockets`' own `InvalidStatus` (bad token) and `ConnectionClosed`
    (relay restarted, network blip) both fall through to a fresh backoff
    reconnect; nothing here distinguishes them further, since v1's only
    remedy for either is "try again".

    `decision_tail` is constructed ONCE, outside the reconnect loop below,
    so "recent decisions" means since this process started, not since the
    last successful connection.
    """
    token = deps.settings.status_push_token
    headers = {"Authorization": f"Bearer {token.get_secret_value()}"} if token is not None else {}

    decision_tail = _DecisionTail(
        started_at_cursor=encode_cursor(created_at=deps.clock.now(), item_id=_MIN_UUID)
    )

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
                    fields = await _build_payload_fields(
                        deps,
                        list_runs=list_runs,
                        list_subjects=list_subjects,
                        list_campaigns=list_campaigns,
                        list_datasets=list_datasets,
                        list_clearances=list_clearances,
                        list_enclosures=list_enclosures,
                        decision_tail=decision_tail,
                        list_decisions=list_decisions,
                        witness_recorder=witness_recorder,
                    )
                    content_hash = _content_hash(fields)
                    changed = content_hash != last_hash
                    heartbeat_due = ticks_since_push >= _HEARTBEAT_TICKS
                    if changed or heartbeat_due:
                        sequence += 1
                        snapshot = build_snapshot(
                            sequence=sequence,
                            generated_at=deps.clock.now().isoformat(),
                            producer_id=producer_id,
                            **fields,
                        )
                        await sock.send(json.dumps(snapshot))
                        last_hash = content_hash
                        ticks_since_push = 0
                    else:
                        ticks_since_push += 1
                    await asyncio.sleep(tick_seconds)
        except asyncio.CancelledError:
            raise
        except _UNAUTHORIZED_ERRORS:
            _log.exception(f"{_LOG_PREFIX}.read_unauthorized")
            await asyncio.sleep(tick_seconds)
        except (ConnectionClosed, InvalidStatus, OSError) as err:
            _log.warning(f"{_LOG_PREFIX}.disconnected", reason=str(err), retry_in=backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _RECONNECT_MAX_SECONDS)


@contextlib.asynccontextmanager
async def status_push_lifespan(
    deps: Kernel,
    *,
    list_runs: ListRunsHandler,
    list_subjects: ListSubjectsHandler,
    list_campaigns: ListCampaignsHandler,
    list_datasets: ListDatasetsHandler,
    list_clearances: ListClearancesHandler,
    list_enclosures: ListEnclosuresHandler,
    list_decisions: ListDecisionsHandler,
    witness_recorder: RunWitnessRecorder | None = None,
) -> AsyncGenerator[None]:
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

    `witness_recorder` is `run_witness_lifespan`'s own yielded value, so the
    caller must enter that context manager first and bind it (`main.py`
    does this by ordering `run_witness_lifespan(...) as witness_recorder`
    before this call in the same `async with` group). `None` is a normal
    state, not a misconfiguration: it means witnessing is off, or shadow-only
    with no recorder built; either way progress is simply absent from every
    pushed run, per `_render_progress`.
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
        _push_loop(
            deps,
            list_runs=list_runs,
            list_subjects=list_subjects,
            list_campaigns=list_campaigns,
            list_datasets=list_datasets,
            list_clearances=list_clearances,
            list_enclosures=list_enclosures,
            list_decisions=list_decisions,
            producer_id=producer_id,
            url=url,
            witness_recorder=witness_recorder,
        ),
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
