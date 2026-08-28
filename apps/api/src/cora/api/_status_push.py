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
    `RunWitnessRecorder.progress_readings()` and a `progress_trail` from
    `progress_trails()` (`{}` when unavailable; see `_render_progress` /
    `_render_progress_trail`)
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
  - each open Run's full exact-timestamped history (`get_run_history`),
    pushed as a SEPARATE message kind on the same socket (see
    `_RunHistoryTail`, `build_run_history_message`), refreshed
    periodically while open and once more, marked terminal, the instant a
    run leaves the open set -- this is REWIND mode's entire feed

The snapshot payload is a full snapshot every push, never a delta: a
fresh viewer, a reconnecting viewer, and a restarted relay are all served
by "here is the current one". Run-history messages are the opposite: each
one is pushed only when genuinely new (a fresh fetch or a terminal
checkpoint), never repeated, since `_RunHistoryTail.poll` already tracks
what is new itself.

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
with, to EIGHT commands across seven BCs (`GetRunHistory` joins the
original seven, still within the Run BC), which is exactly the trigger this
docstring named for standing up a dedicated seeded identity (mirroring
`agent/seed_calibration_watcher.py`). That identity is NOT built in this
change; doing so is a follow-up, tracked so the deferral is visible rather
than silently indefinite. Until then, a Trust Policy that denies any of the
eight read commands to `SYSTEM_PRINCIPAL_ID` blinds this feature for that
domain only (each drain is independently try/except-guarded; see
`_push_loop`), never the others.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
from collections import OrderedDict, deque
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
from cora.run.features.get_run_history import GetRunHistory
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
    from cora.run.features.get_run_history.handler import Handler as GetRunHistoryHandler
    from cora.run.features.get_run_history.handler import RunHistoryView
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
_PROGRESS_TRAIL_POINTS = 30
"""Cap on how many trail points ride the wire per (run, role), independent
of `RunWitnessRecorder`'s own retention -- the payload stays bounded even
if that retention ever grows."""
_RUN_HISTORY_RING_SIZE = 20
"""Producer-side cap on how many run histories `_RunHistoryTail` tracks at
once, mirroring `_DECISION_RING_SIZE`'s reasoning. The relay keeps its own
independent cap; this one exists so a long shift with many runs cannot
grow this process's own memory without bound."""
_RUN_HISTORY_REFRESH_TICKS = 15
"""How often (in ticks) an open run's full history re-pushes: 30s at the
2.0s default tick. A run already visible in LIVE mode does not need its
REWIND timeline refreshed at the same 2Hz cadence; the terminal push (see
`_RunHistoryTail.poll`) guarantees the final version is always complete
regardless of where this clock happened to be when the run closed."""
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


def _render_progress_trail(
    run_id: UUID, witness_recorder: RunWitnessRecorder | None
) -> dict[str, list[dict[str, Any]]]:
    """The run's recent progress trail per role, JSON-safe, or `{}` when
    unavailable. Same three-cases-alike `{}` posture as `_render_progress`.
    Tail-sliced to `_PROGRESS_TRAIL_POINTS` independent of the recorder's
    own retention, so the wire payload stays bounded either way."""
    if witness_recorder is None:
        return {}
    trails = witness_recorder.progress_trails().get(run_id)
    if not trails:
        return {}
    return {
        role: [
            {
                "value": observation.value,
                "commanded_total": observation.commanded_total,
                "observed_at": render_value(observation.observed_at),
            }
            for observation in trail[-_PROGRESS_TRAIL_POINTS:]
        ]
        for role, trail in trails.items()
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
                    "progress_trail": _render_progress_trail(item.run_id, witness_recorder),
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


class _RunHistoryTail:
    """Pushes each open run's full exact-timestamped history to the relay
    at checkpoints, over the SAME outbound socket the snapshot uses, as a
    separate message kind -- never inside the snapshot payload itself.

    This is REWIND mode's entire feed. arcturus has no inbound
    reachability, so a browser cannot ask arcturus for one run's history
    on demand; instead arcturus proactively pushes full histories, and the
    relay caches a bounded ring of them for a browser to pull from later
    (`infra/status-relay/relay.py`). The cost is explicit and accepted:
    REWIND only reaches runs pushed since the relay's own cache was last
    populated, never arbitrary history from before this producer (or the
    relay) last restarted.

    A run's history refreshes every `_RUN_HISTORY_REFRESH_TICKS` while
    open (cheap: a run visible in LIVE mode does not need its REWIND
    timeline refreshed at the live tick's own cadence) and once more, the
    instant it leaves the open-run set, with `terminal=True` -- this is
    the checkpoint that lets the relay keep a completed run's history
    after it drops off the live tables. Ring-capped at
    `_RUN_HISTORY_RING_SIZE`, mirroring `_DecisionTail`'s reasoning:
    tracking every run this process has ever seen would grow without
    bound over a long shift.

    One instance lives for the whole `_push_loop` call, not
    per-connection, same as `_DecisionTail` -- `on_reconnect()` resets
    only the per-run refresh clocks (not the ring) after a reconnect, so
    every still-open run re-pushes promptly to repopulate the relay's own
    cache, which is gone after any relay restart.
    """

    def __init__(self) -> None:
        self._ring: OrderedDict[UUID, dict[str, Any]] = OrderedDict()
        self._ticks_since_refresh: dict[UUID, int] = {}
        self._open_last_tick: set[UUID] = set()

    def on_reconnect(self) -> None:
        self._ticks_since_refresh.clear()

    async def poll(
        self,
        get_run_history: GetRunHistoryHandler,
        deps: Kernel,
        *,
        open_run_ids: list[UUID],
        generated_at: str,
        producer_id: str,
    ) -> list[dict[str, Any]]:
        """Full history messages that are NEW this tick, and only those."""
        open_set = set(open_run_ids)
        messages: list[dict[str, Any]] = []

        for run_id in open_run_ids:
            due = (
                run_id not in self._ticks_since_refresh
                or self._ticks_since_refresh[run_id] >= _RUN_HISTORY_REFRESH_TICKS
            )
            if due:
                view = await self._fetch(get_run_history, deps, run_id)
                if view is not None:
                    messages.append(
                        self._store(
                            view, terminal=False, generated_at=generated_at, producer_id=producer_id
                        )
                    )
                self._ticks_since_refresh[run_id] = 0
            else:
                self._ticks_since_refresh[run_id] += 1

        for run_id in self._open_last_tick - open_set:
            view = await self._fetch(get_run_history, deps, run_id)
            if view is not None:
                messages.append(
                    self._store(
                        view, terminal=True, generated_at=generated_at, producer_id=producer_id
                    )
                )
            self._ticks_since_refresh.pop(run_id, None)

        self._open_last_tick = open_set
        return messages

    async def _fetch(
        self, get_run_history: GetRunHistoryHandler, deps: Kernel, run_id: UUID
    ) -> RunHistoryView | None:
        return await get_run_history(
            GetRunHistory(run_id=run_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=NIL_SENTINEL_ID,
        )

    def _store(
        self, view: RunHistoryView, *, terminal: bool, generated_at: str, producer_id: str
    ) -> dict[str, Any]:
        message = build_run_history_message(
            view=view, terminal=terminal, generated_at=generated_at, producer_id=producer_id
        )
        self._ring[view.run_id] = message
        self._ring.move_to_end(view.run_id)
        while len(self._ring) > _RUN_HISTORY_RING_SIZE:
            self._ring.popitem(last=False)
        return message


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
        "kind": "snapshot",
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


def build_run_history_message(
    *,
    view: RunHistoryView,
    terminal: bool,
    generated_at: str,
    producer_id: str,
) -> dict[str, Any]:
    """Assemble one run-history push, a second message kind on the same
    outbound socket the snapshot uses. Never folded into the snapshot
    payload itself: that would multiply the live feed's per-tick bytes by
    an order of magnitude to re-send history that has not changed. A pure
    function, same rationale as `build_snapshot`."""
    return {
        "kind": "run_history",
        "schema_version": 1,
        "producer_id": producer_id,
        "generated_at": generated_at,
        "run_id": render_value(view.run_id),
        "name": view.name,
        "status": view.status,
        "terminal": terminal,
        "events": [
            {
                "event_type": event.event_type,
                "occurred_at": render_value(event.occurred_at),
                "recorded_at": render_value(event.recorded_at),
                "payload": event.payload,
            }
            for event in view.events
        ],
        "observations": [
            {
                "channel_name": observation.channel_name,
                "value": observation.value,
                "categorical_value": observation.categorical_value,
                "units": observation.units,
                "sampled_at": render_value(observation.sampled_at),
            }
            for observation in view.observations
        ],
        "observations_truncated": view.observations_truncated,
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
    run_history_tail: _RunHistoryTail,
    get_run_history: GetRunHistoryHandler,
    witness_recorder: RunWitnessRecorder | None,
    generated_at: str,
    producer_id: str,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Every domain's rows for one tick, plus any run-history messages that
    are new this tick. Each drain is independently guarded by the caller's
    `except _UNAUTHORIZED_ERRORS` (per-domain, not caught here) so a
    missing grant on one command blinds only that section of the page,
    never the whole tick.

    Returns `(fields, history_messages)`, not one dict: the histories are
    not a snapshot field (see `_RunHistoryTail`'s module docstring), so
    they must never enter `_content_hash`'s change-detection input."""
    runs, raw_run_ids = await _drain_open_runs(list_runs, deps, witness_recorder=witness_recorder)
    fields = {
        "runs": runs,
        "subjects": await _drain_open_subjects(list_subjects, deps),
        "campaigns": await _drain_open_campaigns(list_campaigns, deps),
        "datasets": await _drain_datasets_for_runs(list_datasets, deps, run_ids=raw_run_ids),
        "clearances": await _drain_active_clearances(list_clearances, deps),
        "enclosures": await _drain_active_enclosures(list_enclosures, deps),
        "decisions": await decision_tail.poll(list_decisions, deps),
    }
    history_messages = await run_history_tail.poll(
        get_run_history,
        deps,
        open_run_ids=raw_run_ids,
        generated_at=generated_at,
        producer_id=producer_id,
    )
    return fields, history_messages


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
    get_run_history: GetRunHistoryHandler,
    producer_id: str,
    url: str,
    witness_recorder: RunWitnessRecorder | None,
) -> None:
    """Reconnect-with-backoff outer loop; one open connection sends many
    ticks. `websockets`' own `InvalidStatus` (bad token) and `ConnectionClosed`
    (relay restarted, network blip) both fall through to a fresh backoff
    reconnect; nothing here distinguishes them further, since v1's only
    remedy for either is "try again".

    `decision_tail` and `run_history_tail` are each constructed ONCE,
    outside the reconnect loop below, so "recent decisions" / "which runs
    have already had their history pushed" mean since this process
    started, not since the last successful connection.
    """
    token = deps.settings.status_push_token
    headers = {"Authorization": f"Bearer {token.get_secret_value()}"} if token is not None else {}

    decision_tail = _DecisionTail(
        started_at_cursor=encode_cursor(created_at=deps.clock.now(), item_id=_MIN_UUID)
    )
    run_history_tail = _RunHistoryTail()

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
                run_history_tail.on_reconnect()
                ticks_since_push = _HEARTBEAT_TICKS  # push immediately on connect
                while True:
                    generated_at = deps.clock.now().isoformat()
                    fields, history_messages = await _build_payload_fields(
                        deps,
                        list_runs=list_runs,
                        list_subjects=list_subjects,
                        list_campaigns=list_campaigns,
                        list_datasets=list_datasets,
                        list_clearances=list_clearances,
                        list_enclosures=list_enclosures,
                        decision_tail=decision_tail,
                        list_decisions=list_decisions,
                        run_history_tail=run_history_tail,
                        get_run_history=get_run_history,
                        witness_recorder=witness_recorder,
                        generated_at=generated_at,
                        producer_id=producer_id,
                    )
                    # Histories are exempt from the hash/heartbeat gate below
                    # by construction: `poll` only ever returns what is new
                    # this tick, so there is nothing to de-duplicate here.
                    for message in history_messages:
                        await sock.send(json.dumps(message))
                    content_hash = _content_hash(fields)
                    changed = content_hash != last_hash
                    heartbeat_due = ticks_since_push >= _HEARTBEAT_TICKS
                    if changed or heartbeat_due:
                        sequence += 1
                        snapshot = build_snapshot(
                            sequence=sequence,
                            generated_at=generated_at,
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
    get_run_history: GetRunHistoryHandler,
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
            get_run_history=get_run_history,
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


__all__ = ["build_run_history_message", "build_snapshot", "status_push_lifespan"]
