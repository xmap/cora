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
to `_run_translator.py`'s hand-rolled shape than to the flag-watcher family.

## Current scope

Each tick reads and pushes:

  - open Runs (`Running` + `Held`), each with `progress` from
    `RunTranslator.progress_readings()` and a `progress_trail` from
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
  - each Active Enclosure's permit/lifecycle timeline
    (`get_enclosure_history`), pushed as a FOURTH message kind whenever it
    changes (see `_EnclosureTimelineTail`, `build_enclosure_timeline_message`)
    -- REWIND's second subject, proving the timeline document scrubber.js
    renders is genuinely subject-neutral. Unlike run history, this needs
    NO on-demand request path: at pilot scale there are only a handful of
    Enclosures with a sparse transition rate, so the whole subject set
    fits in every push and there is nothing a bounded cache could ever
    fail to hold
  - event metadata (`stream_type`, `stream_id`, `event_type`, timestamps
    only, NEVER `payload`) tail-followed across the WHOLE `events` table
    since this process's own "now" (`_ActivityTail`,
    `EventActivityTrail`), pushed as a third message kind whenever
    something new has happened -- this is flowing mode's entire feed
  - answers, on demand, a relay-originated `run_history_request` for ONE
    run's full history (`_read_requests` / `_answer_request` /
    `build_run_history_response`), reusing the very same `get_run_history`
    read the periodic push above already makes -- this is REWIND's path to
    ANY run in the record, not only the up-to-20 most recently pushed one
    the relay happens to still be caching

The snapshot payload is a full snapshot every push, never a delta: a
fresh viewer, a reconnecting viewer, and a restarted relay are all served
by "here is the current one". Run-history messages are the opposite: each
one is pushed only when genuinely new (a fresh fetch or a terminal
checkpoint), never repeated, since `_RunHistoryTail.poll` already tracks
what is new itself.

Deliberately reads ONLY the in-memory `RunTranslator` for progress,
not the Postgres-durable `entries_run_observations` fallback
`PostgresRunChannelLookup` would offer for a run whose capture is not open
in this process: that path is capped at `capture_progress_flush_tick_seconds`
(10s by default) and never carries `commanded_total` (dropped at the
`ObservationInput` boundary), so it would not feel live and would silently
lack the "of M" figure. Revisit if this ever runs against a Run witnessed
by a different process than the one pushing.

## On-demand requests: one reader task, the tick loop stays the sole writer

The socket was write-only through Step 1: `sock.send` was called from
exactly one coroutine, and nothing ever called `sock.recv`. Answering a
relay-originated request needs the socket to read too, and the design
below is deliberately conservative about how.

`_read_requests` is a single reader task, created inside the same
`async with connect(...)` block as the tick loop, that ONLY parses
inbound frames onto a bounded inbox (`_REQUEST_INBOX_SIZE`); it never
sends and never touches `deps`. The tick loop remains the sole writer
AND the sole consumer of that inbox, draining up to
`status_push_request_max_per_tick` items per tick via `_serve_requests`,
after that tick's snapshot send and before its sleep -- so a slow or
misbehaving request delays only the NEXT tick's snapshot, never the
current one's, and snapshot cadence never depends on how many requests
happen to be waiting.

**The one rule that matters more than the others here**: `_answer_request`
must never let an exception escape, `UnauthorizedError` most of all. If it
did, the exception would propagate out of the tick loop into `_push_loop`'s
own `except _UNAUTHORIZED_ERRORS` / `except (ConnectionClosed, ...)`
handlers, which exit the `async with connect(...)` block and reopen
arcturus's only outbound channel. A browser could then force the
beamline's entire live feed to drop and reconnect just by requesting a
run it is not allowed to read. `_answer_request` therefore catches
`_UNAUTHORIZED_ERRORS` and any other `Exception` itself and turns each
into an ordinary `"unauthorized"` / `"error"` response instead.

A response is served from `_RunHistoryTail`'s own ring
(`_RunHistoryTail.cached_terminal`) when the requested run is already
cached there, and ONLY when that entry is marked terminal: a live run's
timeline already refreshes every `_RUN_HISTORY_REFRESH_TICKS`, so REWIND
on a running scan should never show a stale cached copy. That lookup is
read-only by design -- a request-triggered read must never insert into or
evict from the ring, whose eviction order otherwise mirrors only what
this tail has genuinely pushed.

## Principal identity: the widening trigger fired, and the seed is now wired

Every other watcher here authenticates as its own seeded Agent (a real
Actor with its own grant set, so a missing grant is auditable per-agent).
This module now authenticates as `STATUS_PUBLISHER_AGENT_ID`
(`agent/seed_status_publisher.py`) for every read: the read scope widened
past the single `ListRuns` command this module started with, to NINE
commands across seven BCs (`GetRunHistory` joins the Run BC's own
`ListRuns`; `GetEnclosureHistory` joins the Enclosure BC's own
`ListEnclosures`), which was the trigger this docstring named for
standing up a dedicated seeded identity (mirroring
`agent/seed_calibration_watcher.py`). A Trust Policy that denies any of
the nine read commands to `STATUS_PUBLISHER_AGENT_ID` blinds this
feature for that domain only (each drain is independently
try/except-guarded; see `_push_loop`), never the others.

The on-demand request path above makes `GetRunHistory` reachable from a
browser at any time, not only on this module's own fixed tick, which is
a materially larger claim on `STATUS_PUBLISHER_AGENT_ID` than the
periodic push alone -- it does not add a NINTH command (it is the same
`GetRunHistory` call the periodic push already makes, under the same
identity, with the same `_UNAUTHORIZED_ERRORS` catch), but it does mean a
wider surface can now trigger it on demand.

`_ActivityTail`'s read is a NINTH, and it is a different KIND of gap, not
just a bigger one: `EventActivityTrail` is a raw infrastructure port, not
a `list_*`/`get_*` command handler, so it never calls `deps.authz.authorize`
at all. Every other read here can be individually denied by a Trust Policy
naming its command; this one cannot be denied at all short of disabling
StatusPush entirely. That is acceptable for what it ships (event metadata
across every BC, never a value, never PII) but it is a real asymmetry with
the eight commands above, not an equivalent case of the same debt -- flagged
here so it is a deliberate, visible trade-off rather than something a future
reader has to rediscover by reading past the authorize call that is not
there.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from cora.agent.fleet_readiness import read_fleet_readiness
from cora.agent.seed_status_publisher import STATUS_PUBLISHER_AGENT_ID
from cora.campaign.errors import UnauthorizedError as _CampaignUnauthorizedError
from cora.campaign.features.list_campaigns import ListCampaigns
from cora.data.errors import UnauthorizedError as _DataUnauthorizedError
from cora.data.features.list_datasets import ListDatasets
from cora.decision.errors import UnauthorizedError as _DecisionUnauthorizedError
from cora.decision.features.list_decisions import ListDecisions
from cora.enclosure.errors import UnauthorizedError as _EnclosureUnauthorizedError
from cora.enclosure.features.get_enclosure_history import GetEnclosureHistory
from cora.enclosure.features.list_enclosures import ListEnclosures
from cora.infrastructure.adapters.in_memory_event_activity_trail import (
    InMemoryEventActivityTrail,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.adapters.postgres_event_activity_trail import (
    PostgresEventActivityTrail,
)
from cora.infrastructure.logging import get_logger
from cora.infrastructure.projection import encode_cursor
from cora.infrastructure.record_export import render_value
from cora.infrastructure.routing import SYSTEM_IN_PROCESS_SURFACE_ID
from cora.operation.errors import UnauthorizedError as _OperationUnauthorizedError
from cora.operation.features.list_procedures import ListProcedures
from cora.recipe.features.list_plans import ListPlans
from cora.run.errors import UnauthorizedError as _RunUnauthorizedError
from cora.run.features.get_run_history import GetRunHistory
from cora.run.features.list_runs import ListRuns
from cora.safety.errors import UnauthorizedError as _SafetyUnauthorizedError
from cora.safety.features.list_clearances import ListClearances
from cora.subject.errors import UnauthorizedError as _SubjectUnauthorizedError
from cora.subject.features.list_subjects import ListSubjects

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

    from websockets.asyncio.client import ClientConnection

    from cora.api._run_translator import RunTranslator
    from cora.campaign.features.list_campaigns.handler import Handler as ListCampaignsHandler
    from cora.campaign.features.list_campaigns.query import CampaignStatusFilter
    from cora.data.features.list_datasets.handler import Handler as ListDatasetsHandler
    from cora.decision.features.list_decisions.handler import Handler as ListDecisionsHandler
    from cora.enclosure.features.get_enclosure_history.handler import EnclosureHistoryView
    from cora.enclosure.features.get_enclosure_history.handler import (
        Handler as GetEnclosureHistoryHandler,
    )
    from cora.enclosure.features.list_enclosures.handler import Handler as ListEnclosuresHandler
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.ports.event_activity_trail import (
        EventActivityCursor,
        EventActivityRow,
        EventActivityTrail,
    )
    from cora.operation.features.list_procedures.handler import (
        Handler as ListProceduresHandler,
    )
    from cora.recipe.features.list_plans.handler import Handler as ListPlansHandler
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
of `RunTranslator`'s own retention -- the payload stays bounded even
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
_FLEET_READINESS_REFRESH_TICKS = 150
"""How often (in ticks) the agent fleet's readiness is re-read: 5 minutes at
the 2.0s default tick.

Reading it costs one event-store load per shipped agent, and the answer only
changes when an operator promotes, suspends or deprecates one, which is a rare
deliberate gesture rather than beamline traffic. Re-reading twenty streams at
2Hz to watch a value that moves monthly would be the most expensive thing in
the tick loop by a wide margin.

Not cached for the process's lifetime either, which is the other obvious
choice and the wrong one: an operator who has just run `promote_seeded_fleet`
is looking at this page to see whether it worked, and "restart the API to find
out" is not an answer."""
_ACTIVITY_PAGE_LIMIT = 500
"""Per-`read_since` call cap for `_ActivityTail`. Measured against the real
2-BM deployment (2026-08-28): 13,822 events total, ever, across 25 stream
types, with the busiest hour carrying 228. This limit is not a working
constraint at that volume; it exists so a pathological backlog (a long
disconnect, or a future higher-throughput deployment) cannot pull an
unbounded result set into memory in one call. `_ActivityTail.poll` loops
on this until it catches up, so no event is skipped, only batched."""
_MIN_UUID = UUID(int=0)
"""Sentinel id for `_DecisionTail`'s starting cursor: paired with "now" as
the cursor's time component, so the `(time, id) > (cursor_time, cursor_id)`
keyset predicate admits anything at or after this instant regardless of id,
rather than requiring an id greater than a real (and otherwise arbitrary)
UUID at the same microsecond."""

_REQUEST_INBOX_SIZE = 8
"""Bound on `_read_requests`' inbox queue: 2x the relay's own in-flight
cap (`_MAX_INFLIGHT_REQUESTS` in `relay.py`). Overflow past this means the
relay is misbehaving or the producer has fallen badly behind, not real
load; an overflowing frame is dropped and logged, never blocked on, so the
reader task can keep draining the socket."""
_REQUEST_PHASE_BUDGET_SECONDS = 1.5
"""Wall-clock budget for one tick's WHOLE request-serving phase (not a
per-item timeout), so worst-case tick skew stays a constant regardless of
how many items are drained. Worst case a tick becomes
`tick_seconds + 1.5s`; at the 2.0s default that is 3.5s, still inside the
10s heartbeat window `_HEARTBEAT_TICKS` already gives the relay to notice
a stall."""
_MAX_INBOUND_FRAME_BYTES = 16384
"""Passed as `max_size=` to `connect()`. A `run_history_request` frame is
on the order of 200 bytes; this is a pre-parse safety bound against a
misbehaving or compromised relay, not a working limit."""

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
    _OperationUnauthorizedError,
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


def _render_progress(run_id: UUID, translator: RunTranslator | None) -> dict[str, Any]:
    """The run's progress readings, JSON-safe, or `{}` when unavailable.

    `{}` covers three cases alike, deliberately not distinguished on the
    wire: witnessing is disabled entirely (`translator is None`), the
    capture behind this run is not open in this process, and the capture is
    open but has not produced a reading yet. All three mean the viewer has
    no progress number to show; none of them is an error.
    """
    if translator is None:
        return {}
    readings = translator.progress_readings().get(run_id)
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
    run_id: UUID, translator: RunTranslator | None
) -> dict[str, list[dict[str, Any]]]:
    """The run's recent progress trail per role, JSON-safe, or `{}` when
    unavailable. Same three-cases-alike `{}` posture as `_render_progress`.
    Tail-sliced to `_PROGRESS_TRAIL_POINTS` independent of the recorder's
    own retention, so the wire payload stays bounded either way."""
    if translator is None:
        return {}
    trails = translator.progress_trails().get(run_id)
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


async def _plan_names(list_plans: ListPlansHandler, deps: Kernel) -> dict[UUID, str]:
    """Every plan's name, by id.

    A Plan is a TEMPLATE: it has no lifetime of its own during a shift, so it
    is never a row on a live view. What a viewer needs is the other direction,
    which run is executing which plan, and that is an attribute of the run.
    Only the name travels; a `plan_id` alone would be an opaque uuid the page
    could only print back.

    Drained whole rather than looked up per run. The set is small, static
    across a shift, and `ListPlans` has no id filter, so N lookups for a
    handful of open runs would be more queries for the same rows.
    """
    items = await _drain_all(
        lambda cursor: list_plans(
            ListPlans(cursor=cursor, limit=_PAGE_LIMIT),
            principal_id=STATUS_PUBLISHER_AGENT_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=SYSTEM_IN_PROCESS_SURFACE_ID,
        )
    )
    return {item.plan_id: item.name for item in items}


async def _drain_open_runs(
    list_runs: ListRunsHandler,
    deps: Kernel,
    *,
    translator: RunTranslator | None,
    plan_names: dict[UUID, str],
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
                principal_id=STATUS_PUBLISHER_AGENT_ID,
                correlation_id=deps.id_generator.new_id(),
                surface_id=SYSTEM_IN_PROCESS_SURFACE_ID,
            )
        )
        for item in items:
            rows.append(
                {
                    "run_id": render_value(item.run_id),
                    "name": item.name,
                    "status": item.status,
                    # Structure, not decoration. `campaign_id` is what a Run
                    # belongs to and `subject_id` is what it is measuring, both
                    # already on the projection (they back `list_runs`'s own
                    # `?campaign_id=` filter); a consumer without them can show
                    # a Run but cannot place it among the others. `started_at`
                    # is `running_since` where the Run has actually started and
                    # `created_at` otherwise, so a span always has a left edge.
                    "campaign_id": render_value(item.campaign_id),
                    "subject_id": render_value(item.subject_id),
                    # The template this run is an instance OF, by name. A plan
                    # has no lifetime during a shift and so never earns a row
                    # of its own; naming it here is how the template layer
                    # becomes visible at all. Absent when the plan is not in
                    # the projection, which reads as unknown rather than as
                    # a run with no plan.
                    "plan_name": plan_names.get(item.plan_id),
                    "started_at": render_value(item.running_since or item.created_at),
                    "progress": _render_progress(item.run_id, translator),
                    "progress_trail": _render_progress_trail(item.run_id, translator),
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
                principal_id=STATUS_PUBLISHER_AGENT_ID,
                correlation_id=deps.id_generator.new_id(),
                surface_id=SYSTEM_IN_PROCESS_SURFACE_ID,
            )
        )
        rows.extend(
            {
                "subject_id": render_value(item.subject_id),
                "name": item.name,
                "status": item.status,
                "created_at": render_value(item.created_at),
            }
            for item in items
        )
    return rows


async def _drain_open_campaigns(
    list_campaigns: ListCampaignsHandler, deps: Kernel
) -> list[dict[str, Any]]:
    items = await _drain_all(
        lambda cursor: list_campaigns(
            ListCampaigns(statuses=_OPEN_CAMPAIGN_STATUSES, cursor=cursor, limit=_PAGE_LIMIT),
            principal_id=STATUS_PUBLISHER_AGENT_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=SYSTEM_IN_PROCESS_SURFACE_ID,
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
                principal_id=STATUS_PUBLISHER_AGENT_ID,
                correlation_id=deps.id_generator.new_id(),
                surface_id=SYSTEM_IN_PROCESS_SURFACE_ID,
            )
        )
        rows.extend(
            {
                "dataset_id": render_value(item.dataset_id),
                "name": item.name,
                "status": item.status,
                # Both ends of what a dataset came from. `producing_run_id`
                # was already here; `subject_id` is the same class of fact and
                # answers the question the run id cannot, which is what was
                # being measured when a dataset that no longer has an open run
                # was written.
                "producing_run_id": render_value(item.producing_run_id),
                "subject_id": render_value(item.subject_id),
            }
            for item in items
        )
    return rows


async def _drain_procedures_for_runs(
    list_procedures: ListProceduresHandler, deps: Kernel, *, run_ids: list[UUID]
) -> list[dict[str, Any]]:
    """Procedures belonging to an on-screen Run, one query per run_id.

    Bounded by the open-run count exactly as `_drain_datasets_for_runs` is,
    and for the same reason: what a live page needs is the phases of the runs
    on screen, never every Procedure the facility has ever registered.

    This is the third level of the containment tree -- campaign holds runs
    hold procedures -- and it is the level a consumer cannot reconstruct from
    the activity stream alone. That stream carries a Procedure's `stream_id`
    and so can tell one Procedure from another, but nothing in it says which
    Run a Procedure is a phase OF: `parent_run_id` lives on the projection and
    only here.

    `last_status_reason` is deliberately NOT sent. It is operator free text
    (see `cora.shared.text_bounds`), which is exactly the shape that carries
    incidental personal data, and nothing on a status page needs it. `kind`
    is a deployment-declared discriminator and `name` is the same class of
    value as the Run `name` already on this payload.
    """
    rows: list[dict[str, Any]] = []
    for run_id in run_ids:
        items = await _drain_all(
            lambda cursor, run_id=run_id: list_procedures(
                ListProcedures(parent_run_id=run_id, cursor=cursor, limit=_PAGE_LIMIT),
                principal_id=STATUS_PUBLISHER_AGENT_ID,
                correlation_id=deps.id_generator.new_id(),
                surface_id=SYSTEM_IN_PROCESS_SURFACE_ID,
            )
        )
        rows.extend(
            {
                "procedure_id": render_value(item.procedure_id),
                "name": item.name,
                "kind": item.kind,
                "parent_run_id": render_value(item.parent_run_id),
                "status": item.status,
                "registered_at": render_value(item.registered_at),
                "last_status_changed_at": render_value(item.last_status_changed_at),
                "iteration_count": item.iteration_count,
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
            principal_id=STATUS_PUBLISHER_AGENT_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=SYSTEM_IN_PROCESS_SURFACE_ID,
        )
    )
    return [
        {
            "clearance_id": render_value(item.clearance_id),
            "template_code": item.template_code,
            "risk_band": item.risk_band,
            "status": item.status,
            # A clearance is cover over a RANGE, so the viewer needs both ends
            # of it, not just when it runs out. `registered_at` is the
            # fallback the page draws from when cover was granted without an
            # explicit start.
            #
            # `title` and `last_status_reason` stay off the wire. The title is
            # operator-authored and the reason is free text written at the
            # moment of an incident, which is the shape that carries
            # incidental personal data; `template_code` names the clearance
            # without either.
            "valid_from": render_value(item.valid_from),
            "valid_until": render_value(item.valid_until),
            "registered_at": render_value(item.registered_at),
            # WHAT the cover covers. A clearance drawn as a bar over a range
            # says only that cover existed; these say whether it reaches the
            # run on screen, which is the question anyone looking at a
            # clearance on a live page is actually asking. Opaque ids of
            # entities the same payload already names.
            #
            # `asset_binding_ids` is left off: nothing on this page draws an
            # asset, so it would be a field on the wire that no consumer can
            # resolve to anything.
            "run_binding_ids": [render_value(i) for i in item.run_binding_ids],
            "procedure_binding_ids": [render_value(i) for i in item.procedure_binding_ids],
            "subject_binding_ids": [render_value(i) for i in item.subject_binding_ids],
        }
        for item in items
    ]


async def _drain_active_enclosures(
    list_enclosures: ListEnclosuresHandler, deps: Kernel
) -> tuple[list[dict[str, Any]], list[UUID]]:
    """Returns the rendered (JSON-safe) rows AND the raw enclosure_id
    UUIDs, mirroring `_drain_open_runs`: the rows go straight into the
    snapshot payload, but `_EnclosureTimelineTail.poll` needs real `UUID`
    objects to call `get_enclosure_history` with, not `render_value`'s
    string form.
    """
    items = await _drain_all(
        lambda cursor: list_enclosures(
            ListEnclosures(lifecycle=_ACTIVE_ENCLOSURE_LIFECYCLE, cursor=cursor, limit=_PAGE_LIMIT),
            principal_id=STATUS_PUBLISHER_AGENT_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=SYSTEM_IN_PROCESS_SURFACE_ID,
        )
    )
    rows: list[dict[str, Any]] = []
    raw_enclosure_ids: list[UUID] = []
    for item in items:
        rows.append(
            {
                "enclosure_id": render_value(item.enclosure_id),
                "name": item.name,
                "permit_status": item.permit_status,
                "facility_code": item.facility_code,
            }
        )
        raw_enclosure_ids.append(item.enclosure_id)
    return rows, raw_enclosure_ids


class _FleetReadinessTail:
    """Holds the fleet's readiness across ticks, re-reading it rarely.

    Unlike every other domain here this is not beamline traffic: it is a
    standing fact about the deployment, true between operator gestures
    and expensive to ask (one stream load per shipped agent). So it is
    read on the first tick and then only every
    `_FLEET_READINESS_REFRESH_TICKS`, and the held value rides every
    snapshot in between.

    Deliberately NOT skipped when the fleet is healthy. A page that shows
    the row only when something is wrong teaches its reader that an
    absent row means nothing to see, which is the same lesson that let a
    stranded fleet sit unnoticed for three months. "20 of 20 ready" is
    the row earning trust for the one day it says 4.
    """

    def __init__(self) -> None:
        self._held: dict[str, Any] | None = None
        self._ticks_since_read = 0

    async def poll(self, deps: Kernel) -> dict[str, Any]:
        due = self._held is None or self._ticks_since_read >= _FLEET_READINESS_REFRESH_TICKS
        if not due:
            self._ticks_since_read += 1
            return self._held if self._held is not None else {}
        readiness = await read_fleet_readiness(deps.event_store)
        self._ticks_since_read = 0
        # Names, never ids: this row exists to tell an operator which
        # agents will not act, and `RunTranslator` answers that where a uuid
        # does not. Nothing on the page can resolve an agent id anyway.
        self._held = {
            "ready": len(readiness.ready),
            "total": readiness.total,
            "not_ready": list(readiness.not_ready),
            "held": list(readiness.held),
            "absent": list(readiness.absent),
        }
        return self._held


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
                principal_id=STATUS_PUBLISHER_AGENT_ID,
                correlation_id=deps.id_generator.new_id(),
                surface_id=SYSTEM_IN_PROCESS_SURFACE_ID,
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
            principal_id=STATUS_PUBLISHER_AGENT_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=SYSTEM_IN_PROCESS_SURFACE_ID,
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

    def cached_terminal(self, run_id: UUID) -> dict[str, Any] | None:
        """The cached history message for `run_id`, if this tail is
        holding one AND it is marked terminal, else `None`.

        Read-only and terminal-only by design (see this module's "On-demand
        requests" section): a live run's timeline already refreshes every
        `_RUN_HISTORY_REFRESH_TICKS`, so an on-demand answer for an
        in-flight run should do a fresh read rather than risk a stale
        cached copy, and a request-triggered read must never insert into
        or evict from `_ring`, whose eviction order otherwise mirrors only
        what this tail has genuinely pushed."""
        message = self._ring.get(run_id)
        if message is None or not message.get("terminal"):
            return None
        return message


class _EnclosureTimelineTail:
    """Pushes each Active enclosure's redacted permit/lifecycle timeline
    to the relay whenever it changes, over the SAME outbound socket the
    snapshot uses, as a fourth message kind.

    Unlike `_RunHistoryTail`, this needs neither a ring nor a per-subject
    refresh clock. At pilot scale there are only a handful of Enclosures,
    and their transition rate is sparse: the `observe_enclosure_status`
    decider short-circuits an identical-status observation, so every
    `EnclosurePermitObserved` actually on the stream is a genuine change.
    Polling every enclosure's full history every tick is therefore cheap
    (an event-stream load with no observation join, unlike Run), and the
    whole subject set fits in a plain dict with no eviction needed. REWIND
    reaching any enclosure in the record needs no on-demand request path
    the way reaching any RUN did: there is nothing a bounded cache could
    ever fail to hold when it can hold every enclosure at once.

    `_last_hash` tracks each enclosure's last-pushed content hash so a
    quiet enclosure produces no repeat traffic tick over tick, the same
    role `_content_hash` plays for the snapshot itself -- and, like that
    hash, computed over `lanes` / `title` / `subtitle` / `truncated`
    ONLY, never the full document: `document["domain"]["to"]` is
    `generated_at`, which differs on every tick by construction, so
    hashing it would defeat the whole point of deduplication (an
    unchanged enclosure would never be recognized as unchanged).
    `on_reconnect()` clears it so a fresh relay connection, whose own
    cache is empty, gets one full repush of every enclosure -- the same
    repopulate-after-reconnect posture `_RunHistoryTail.on_reconnect`
    takes for the run-history ring.
    """

    def __init__(self) -> None:
        self._last_hash: dict[UUID, str] = {}

    def on_reconnect(self) -> None:
        self._last_hash.clear()

    async def poll(
        self,
        get_enclosure_history: GetEnclosureHistoryHandler,
        deps: Kernel,
        *,
        enclosure_ids: list[UUID],
        generated_at: str,
        producer_id: str,
    ) -> list[dict[str, Any]]:
        """Timeline messages that are NEW this tick, and only those."""
        messages: list[dict[str, Any]] = []
        for enclosure_id in enclosure_ids:
            view = await get_enclosure_history(
                GetEnclosureHistory(enclosure_id=enclosure_id),
                principal_id=STATUS_PUBLISHER_AGENT_ID,
                correlation_id=deps.id_generator.new_id(),
                surface_id=SYSTEM_IN_PROCESS_SURFACE_ID,
            )
            if view is None:
                continue
            message = build_enclosure_timeline_message(
                view=view, generated_at=generated_at, producer_id=producer_id
            )
            document = message["document"]
            # Excludes `domain` (its `to` is `generated_at`, which
            # differs every tick regardless of whether anything about
            # the enclosure itself changed -- see this class's own
            # docstring).
            content_hash = _content_hash(
                {
                    "lanes": document["lanes"],
                    "title": document["title"],
                    "subtitle": document["subtitle"],
                    "truncated": document["truncated"],
                }
            )
            if self._last_hash.get(enclosure_id) == content_hash:
                continue
            self._last_hash[enclosure_id] = content_hash
            messages.append(message)
        return messages


class _ActivityTail:
    """Tail-follows the whole `events` table for flowing mode's lanes:
    THAT something happened, and WHAT KIND, across every BC -- never the
    payload (see `cora.infrastructure.ports.event_activity_trail`'s module
    docstring for why). Pushed as a third message kind on the same
    outbound socket the snapshot and run-history messages use.

    Unlike `_DecisionTail` and `_RunHistoryTail`, there is no relay-side
    cache to repopulate on reconnect: flowing mode's window lives in the
    BROWSER, not the relay, so this tail carries no ring and needs no
    `on_reconnect()`. The cursor itself is enough -- constructed once,
    outside the reconnect loop, so a producer-side reconnect resumes
    exactly where it left off rather than replaying or dropping the gap.

    The cursor starts at `head()` (this process's own "now"), the same
    empty-until-something-happens posture `_DecisionTail` takes, not a
    replay of the whole event history: flowing mode is about recent
    activity, not full record recovery (REWIND already exists for that).
    """

    def __init__(self) -> None:
        self._cursor: EventActivityCursor | None = None

    async def poll(self, activity_trail: EventActivityTrail) -> list[EventActivityRow]:
        if self._cursor is None:
            self._cursor = await activity_trail.head()
            return []
        rows: list[EventActivityRow] = []
        while True:
            page, next_cursor = await activity_trail.read_since(
                cursor=self._cursor, limit=_ACTIVITY_PAGE_LIMIT
            )
            self._cursor = next_cursor
            if not page:
                break
            rows.extend(page)
            if len(page) < _ACTIVITY_PAGE_LIMIT:
                break
        return rows


@dataclass(frozen=True)
class _Inbound:
    """One inbound frame off the relay, already fully parsed and resolved.

    `status` is `None` for a well-formed request that still needs a real
    answer (`_answer_request` does the lookup); otherwise it is a terminal
    status `_parse_inbound` has already decided (`"malformed"` /
    `"unsupported"`), so `_answer_request` has exactly one shape either
    way: read `status`, and if it is set, echo it back without touching
    `deps` at all."""

    request_id: str
    run_id: UUID | None
    status: str | None


def _parse_inbound(message: str | bytes) -> _Inbound | None:
    """Parse one frame off the relay into an `_Inbound`, or `None` when it
    cannot be answered at all.

    `None` covers two cases, both logged and dropped rather than raised,
    mirroring `relay.py`'s own `producer.unknown_kind` posture: a frame
    that is not valid JSON, and a recognized-or-not `kind` with no usable
    `request_id` to reply against. A recognized `kind` with an unsupported
    `schema_version` is NOT one of these -- `request_id` is still usable
    there, so it gets an `"unsupported"` response rather than silence.
    """
    try:
        parsed: Any = json.loads(message)
    except (TypeError, ValueError):
        _log.warning(f"{_LOG_PREFIX}.malformed_inbound")
        return None
    if not isinstance(parsed, dict):
        _log.warning(f"{_LOG_PREFIX}.unknown_inbound_kind", kind=None)
        return None
    payload = cast("dict[str, Any]", parsed)
    if payload.get("kind") != "run_history_request":
        _log.warning(f"{_LOG_PREFIX}.unknown_inbound_kind", kind=payload.get("kind"))
        return None
    request_id = payload.get("request_id")
    if not isinstance(request_id, str):
        _log.warning(f"{_LOG_PREFIX}.request_missing_id")
        return None
    if payload.get("schema_version") != 1:
        return _Inbound(request_id=request_id, run_id=None, status="unsupported")
    raw_run_id = payload.get("run_id")
    try:
        run_id = UUID(raw_run_id) if isinstance(raw_run_id, str) else None
    except ValueError:
        run_id = None
    if run_id is None:
        return _Inbound(request_id=request_id, run_id=None, status="malformed")
    return _Inbound(request_id=request_id, run_id=run_id, status=None)


async def _read_requests(sock: ClientConnection, inbox: asyncio.Queue[_Inbound]) -> None:
    """Parses every inbound frame onto the bounded `inbox`, nothing else.

    This is the ONLY coroutine that calls `sock.recv` (implicitly, via
    `async for`); it never calls `sock.send` and never touches `deps`. The
    tick loop in `_push_loop` remains the sole writer and the sole
    consumer of `inbox` (see this module's "On-demand requests" section
    for why the split is this conservative)."""
    async for message in sock:
        item = _parse_inbound(message)
        if item is None:
            continue
        try:
            inbox.put_nowait(item)
        except asyncio.QueueFull:
            _log.warning(f"{_LOG_PREFIX}.request_inbox_full", request_id=item.request_id)


def build_run_history_response(
    *,
    request_id: str,
    status: str,
    generated_at: str,
    producer_id: str,
    source: str | None = None,
    history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble one answer to a relay's `run_history_request`. A pure
    function, same rationale as `build_snapshot`: unit-testable without a
    socket. `history`, when present, is byte-identical to
    `build_run_history_message`'s own output, so the relay can feed a
    successful response straight into its existing cache with zero
    transformation."""
    return {
        "kind": "run_history_response",
        "schema_version": 1,
        "producer_id": producer_id,
        "request_id": request_id,
        "generated_at": generated_at,
        "status": status,
        "source": source,
        "history": history,
    }


async def _answer_request(
    item: _Inbound,
    *,
    deps: Kernel,
    get_run_history: GetRunHistoryHandler,
    run_history_tail: _RunHistoryTail,
    producer_id: str,
    generated_at: str,
) -> dict[str, Any]:
    """Answer one relay-originated request. MUST NEVER raise: see this
    module's "On-demand requests" section for why an escaping exception
    here, `UnauthorizedError` most of all, is the single highest-severity
    failure mode in this whole feature."""
    if item.status is not None:
        return build_run_history_response(
            request_id=item.request_id,
            status=item.status,
            generated_at=generated_at,
            producer_id=producer_id,
        )
    assert item.run_id is not None  # status is None only when run_id parsed cleanly

    cached = run_history_tail.cached_terminal(item.run_id)
    if cached is not None:
        return build_run_history_response(
            request_id=item.request_id,
            status="ok",
            generated_at=generated_at,
            producer_id=producer_id,
            source="cache",
            history=cached,
        )

    try:
        view = await get_run_history(
            GetRunHistory(run_id=item.run_id),
            principal_id=STATUS_PUBLISHER_AGENT_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=SYSTEM_IN_PROCESS_SURFACE_ID,
        )
    except _UNAUTHORIZED_ERRORS:
        _log.warning(f"{_LOG_PREFIX}.request_unauthorized", run_id=str(item.run_id))
        return build_run_history_response(
            request_id=item.request_id,
            status="unauthorized",
            generated_at=generated_at,
            producer_id=producer_id,
        )
    except Exception:
        # See this module's "On-demand requests" section: anything else
        # unhandled here must still become a response, never a socket
        # teardown.
        _log.exception(f"{_LOG_PREFIX}.request_failed", run_id=str(item.run_id))
        return build_run_history_response(
            request_id=item.request_id,
            status="error",
            generated_at=generated_at,
            producer_id=producer_id,
        )

    if view is None:
        return build_run_history_response(
            request_id=item.request_id,
            status="not_found",
            generated_at=generated_at,
            producer_id=producer_id,
        )
    terminal = view.status not in _OPEN_RUN_STATUSES
    history = build_run_history_message(
        view=view, terminal=terminal, generated_at=generated_at, producer_id=producer_id
    )
    return build_run_history_response(
        request_id=item.request_id,
        status="ok",
        generated_at=generated_at,
        producer_id=producer_id,
        source="read",
        history=history,
    )


async def _serve_requests(
    inbox: asyncio.Queue[_Inbound],
    sock: ClientConnection,
    *,
    deps: Kernel,
    get_run_history: GetRunHistoryHandler,
    run_history_tail: _RunHistoryTail,
    producer_id: str,
    generated_at: str,
    max_per_tick: int,
) -> None:
    """Drain up to `max_per_tick` already-queued requests, within one
    shared wall-clock budget for the whole phase (`_REQUEST_PHASE_BUDGET_SECONDS`)
    rather than a per-item timeout, so worst-case tick skew stays a
    constant regardless of how many items are drained this tick. Called
    from `_push_loop` after the snapshot send and before the tick's sleep,
    so a slow request delays only the NEXT tick's snapshot, never the
    current one's."""
    if max_per_tick <= 0:
        return
    loop = asyncio.get_running_loop()
    deadline = loop.time() + _REQUEST_PHASE_BUDGET_SECONDS
    served = 0
    while served < max_per_tick and loop.time() < deadline:
        try:
            item = inbox.get_nowait()
        except asyncio.QueueEmpty:
            break
        response = await _answer_request(
            item,
            deps=deps,
            get_run_history=get_run_history,
            run_history_tail=run_history_tail,
            producer_id=producer_id,
            generated_at=generated_at,
        )
        await sock.send(json.dumps(response))
        served += 1


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
    procedures: list[dict[str, Any]],
    clearances: list[dict[str, Any]],
    enclosures: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    agents: dict[str, Any],
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
        "procedures": procedures,
        "clearances": clearances,
        "enclosures": enclosures,
        "decisions": decisions,
        "agents": agents,
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


_ENCLOSURE_GENESIS_PERMIT_STATE = "Unknown"
"""What `EnclosureRegistered` puts the permit axis into. Not carried in
that event's own payload -- the evolver seeds it from the event TYPE (see
`enclosure/aggregates/enclosure/evolver.py`) -- so this message builder
states it explicitly rather than reading a field that does not exist."""
_ENCLOSURE_GENESIS_LIFECYCLE_STATE = "Active"
_ENCLOSURE_DECOMMISSIONED_STATE = "Decommissioned"
_ENCLOSURE_PERMIT_TONE = {
    "Permitted": "good",
    "NotPermitted": "warn",
    "Unknown": "warn",
}
"""Scrubber readout tint per permit value. This is exactly the kind of
domain vocabulary `scrubber.js` itself must never hardcode (per its own
module docstring): a marker point's optional `tone` field lets a producer
supply it, and the Run lens simply never sets one."""


def build_enclosure_timeline_message(
    *,
    view: EnclosureHistoryView,
    generated_at: str,
    producer_id: str,
) -> dict[str, Any]:
    """Assemble one enclosure-timeline push: a subject-neutral timeline
    document (see `infra/status-relay/scrubber.js`'s own module
    docstring) over an Enclosure's permit and lifecycle axes -- the
    second subject this feed has ever pushed alongside Run, and the
    proof that the document shape is genuinely subject-neutral rather
    than shaped around Run specifically.

    Ships state transitions ONLY: `to_status` / `occurred_at` / the
    event's own type. NEVER `reason`, `monitor_ref`, `triggered_by`, or
    any substrate address. `EnclosurePermitObserved.reason` and
    `.monitor_ref` embed the PSS PV address behind the reading (e.g.
    "PSS permit observation via S02BM-PSS:StaA:SecureM"), which this
    repo's own export redaction tier already drops before anything
    leaves the facility (`_redact_tier2.py`'s `permit_probe.source_id`
    rationale: pairing a reachability failure with the exact substrate
    address is closer to a security disclosure about a safety system
    than to science). `get_enclosure_history`'s own view legitimately
    carries that detail for an on-network reader; this function is
    where it must stop, because this message is what actually leaves
    the beamline network for the external relay.

    Two marker lanes, both derived from the same event stream: `permit`
    (the primary / `subject_lane_id`, folded from
    `EnclosurePermitObserved.to_status` and `EnclosureRegistered`'s
    implicit genesis `Unknown`) and `lifecycle` (folded from
    `EnclosureRegistered`'s implicit genesis `Active` and
    `EnclosureDecommissioned`'s terminal `Decommissioned`) -- the same
    two orthogonal axes `evolver.py` folds onto aggregate state,
    preserved here at the event-log grain instead of collapsed to only
    the latest value.

    `domain.to` is `generated_at`, not the last event's own timestamp:
    unlike a Run, which closes, an Enclosure's permit status is a
    standing claim ("still Permitted as of now"), so the window should
    read as current through the moment this message was generated
    rather than stop dead at whatever the last transition happened to
    be.

    An event type this function does not recognize is skipped, not
    raised: a future Enclosure event a producer predates must never
    break the live feed, mirroring the relay's own
    `producer.unknown_kind` forward-compatibility posture."""
    permit_points: list[dict[str, Any]] = []
    lifecycle_points: list[dict[str, Any]] = []
    for event in view.events:
        occurred_at = render_value(event.occurred_at)
        if event.event_type == "EnclosureRegistered":
            permit_points.append(
                {
                    "t": occurred_at,
                    "label": _ENCLOSURE_GENESIS_PERMIT_STATE,
                    "state": _ENCLOSURE_GENESIS_PERMIT_STATE,
                    "tone": _ENCLOSURE_PERMIT_TONE[_ENCLOSURE_GENESIS_PERMIT_STATE],
                }
            )
            lifecycle_points.append(
                {
                    "t": occurred_at,
                    "label": _ENCLOSURE_GENESIS_LIFECYCLE_STATE,
                    "state": _ENCLOSURE_GENESIS_LIFECYCLE_STATE,
                }
            )
        elif event.event_type == "EnclosurePermitObserved":
            to_status = event.payload.get("to_status", _ENCLOSURE_GENESIS_PERMIT_STATE)
            permit_points.append(
                {
                    "t": occurred_at,
                    "label": to_status,
                    "state": to_status,
                    "tone": _ENCLOSURE_PERMIT_TONE.get(to_status, "warn"),
                }
            )
        elif event.event_type == "EnclosureDecommissioned":
            lifecycle_points.append(
                {
                    "t": occurred_at,
                    "label": _ENCLOSURE_DECOMMISSIONED_STATE,
                    "state": _ENCLOSURE_DECOMMISSIONED_STATE,
                }
            )

    domain_from = permit_points[0]["t"] if permit_points else generated_at
    document = {
        "domain": {"from": domain_from, "to": generated_at},
        "lanes": [
            {"lane_id": "permit", "label": "Permit", "render": "markers", "points": permit_points},
            {
                "lane_id": "lifecycle",
                "label": "Lifecycle",
                "render": "markers",
                "points": lifecycle_points,
            },
        ],
        "subject_lane_id": "permit",
        "title": view.name,
        "subtitle": view.permit_status,
        "truncated": {"events": view.events_truncated},
    }
    return {
        "kind": "enclosure_timeline",
        "schema_version": 1,
        "producer_id": producer_id,
        "generated_at": generated_at,
        "enclosure_id": render_value(view.enclosure_id),
        "document": document,
    }


def build_activity_message(
    *, rows: list[EventActivityRow], generated_at: str, producer_id: str
) -> dict[str, Any]:
    """Assemble one activity push -- flowing mode's entire feed. The
    browser accumulates these into its own rolling window; this producer
    holds no window of its own, only the tail cursor. Event metadata only
    (`stream_type`, `stream_id`, `event_type`, timestamps, and the three
    relationship fields): never `event.payload`, see `EventActivityTrail`'s
    own module docstring for why those three are not a breach of that rule.

    `schema_version` stays 1. Adding keys is additive by the repo's own
    versioning stance, and the relay and the producer deploy to different
    hosts, so a page served by an older relay must keep working against a
    newer producer and vice versa. Every consumer treats `correlation_id`,
    `causation_id` and `cause_occurred_at` as absent-by-default rather than
    required, which is also what makes this safe to roll out to the live
    2-BM page one host at a time.

    Unlike `build_snapshot`, never sent when `rows` is empty: there is no
    heartbeat need here, since "no message this tick" already means
    "nothing happened", exactly the information a heartbeat would
    otherwise carry. Caller checks `if rows:` before calling this."""
    return {
        "kind": "activity",
        "schema_version": 1,
        "producer_id": producer_id,
        "generated_at": generated_at,
        "events": [
            {
                "event_id": render_value(row.event_id),
                "stream_type": row.stream_type,
                "stream_id": render_value(row.stream_id),
                "event_type": row.event_type,
                "occurred_at": render_value(row.occurred_at),
                "recorded_at": render_value(row.recorded_at),
                "correlation_id": render_value(row.correlation_id),
                "causation_id": (
                    render_value(row.causation_id) if row.causation_id is not None else None
                ),
                "cause_occurred_at": (
                    render_value(row.cause_occurred_at)
                    if row.cause_occurred_at is not None
                    else None
                ),
            }
            for row in rows
        ],
    }


async def _build_payload_fields(
    deps: Kernel,
    *,
    list_runs: ListRunsHandler,
    list_subjects: ListSubjectsHandler,
    list_campaigns: ListCampaignsHandler,
    list_datasets: ListDatasetsHandler,
    list_procedures: ListProceduresHandler,
    list_clearances: ListClearancesHandler,
    list_plans: ListPlansHandler,
    list_enclosures: ListEnclosuresHandler,
    decision_tail: _DecisionTail,
    fleet_tail: _FleetReadinessTail,
    list_decisions: ListDecisionsHandler,
    run_history_tail: _RunHistoryTail,
    get_run_history: GetRunHistoryHandler,
    enclosure_timeline_tail: _EnclosureTimelineTail,
    get_enclosure_history: GetEnclosureHistoryHandler,
    activity_tail: _ActivityTail,
    activity_trail: EventActivityTrail,
    translator: RunTranslator | None,
    generated_at: str,
    producer_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Every domain's rows for one tick, plus any extra messages (run
    history, enclosure timelines, activity) that are new this tick. Each
    drain is independently guarded by the caller's
    `except _UNAUTHORIZED_ERRORS` (per-domain, not caught here) so a
    missing grant on one command blinds only that section of the page,
    never the whole tick.

    `fields` is `dict[str, Any]` rather than a dict of row lists because
    `agents` is not rows. Every other field answers "which instances are
    open"; that one answers "can this deployment's fleet act", which is a
    single standing fact and would be a lie as a list (a healthy fleet
    would have to be an empty one, and an empty list is exactly how every
    other field spells "none").

    Returns `(fields, extra_messages)`, not one dict: none of run
    history, enclosure timelines, or activity is a snapshot field (see
    `_RunHistoryTail`'s, `_EnclosureTimelineTail`'s, and `_ActivityTail`'s
    module docstrings), so none of them may enter `_content_hash`'s
    change-detection input."""
    runs, raw_run_ids = await _drain_open_runs(
        list_runs,
        deps,
        translator=translator,
        plan_names=await _plan_names(list_plans, deps),
    )
    enclosures, raw_enclosure_ids = await _drain_active_enclosures(list_enclosures, deps)
    fields = {
        "runs": runs,
        "subjects": await _drain_open_subjects(list_subjects, deps),
        "campaigns": await _drain_open_campaigns(list_campaigns, deps),
        "datasets": await _drain_datasets_for_runs(list_datasets, deps, run_ids=raw_run_ids),
        "procedures": await _drain_procedures_for_runs(list_procedures, deps, run_ids=raw_run_ids),
        "clearances": await _drain_active_clearances(list_clearances, deps),
        "enclosures": enclosures,
        "decisions": await decision_tail.poll(list_decisions, deps),
        "agents": await fleet_tail.poll(deps),
    }
    extra_messages = await run_history_tail.poll(
        get_run_history,
        deps,
        open_run_ids=raw_run_ids,
        generated_at=generated_at,
        producer_id=producer_id,
    )
    extra_messages.extend(
        await enclosure_timeline_tail.poll(
            get_enclosure_history,
            deps,
            enclosure_ids=raw_enclosure_ids,
            generated_at=generated_at,
            producer_id=producer_id,
        )
    )
    activity_rows = await activity_tail.poll(activity_trail)
    if activity_rows:
        extra_messages.append(
            build_activity_message(
                rows=activity_rows, generated_at=generated_at, producer_id=producer_id
            )
        )
    return fields, extra_messages


async def _push_loop(
    deps: Kernel,
    *,
    list_runs: ListRunsHandler,
    list_subjects: ListSubjectsHandler,
    list_campaigns: ListCampaignsHandler,
    list_datasets: ListDatasetsHandler,
    list_procedures: ListProceduresHandler,
    list_clearances: ListClearancesHandler,
    list_plans: ListPlansHandler,
    list_enclosures: ListEnclosuresHandler,
    list_decisions: ListDecisionsHandler,
    get_run_history: GetRunHistoryHandler,
    get_enclosure_history: GetEnclosureHistoryHandler,
    activity_trail: EventActivityTrail,
    producer_id: str,
    url: str,
    translator: RunTranslator | None,
    request_max_per_tick: int,
) -> None:
    """Reconnect-with-backoff outer loop; one open connection sends many
    ticks. `websockets`' own `InvalidStatus` (bad token) and `ConnectionClosed`
    (relay restarted, network blip) both fall through to a fresh backoff
    reconnect; nothing here distinguishes them further, since v1's only
    remedy for either is "try again".

    `decision_tail`, `run_history_tail`, `enclosure_timeline_tail` and
    `activity_tail` are each constructed ONCE, outside the reconnect loop
    below, so "recent decisions" / "which runs have already had their
    history pushed" / "which enclosure timelines have already been
    pushed" / "which events have already been tailed" mean since this
    process started, not since the last successful connection.

    A fresh `_read_requests` reader task is created PER connection, inside
    the `async with connect(...)` block below, and torn down in a
    `finally` before that block exits (cancel + gather, never
    `asyncio.TaskGroup`: see this module's "On-demand requests" section
    for why). `request_max_per_tick <= 0` skips creating the inbox and the
    reader task entirely, restoring the write-only socket byte for byte.
    """
    token = deps.settings.status_push_token
    headers = {"Authorization": f"Bearer {token.get_secret_value()}"} if token is not None else {}

    fleet_tail = _FleetReadinessTail()
    decision_tail = _DecisionTail(
        started_at_cursor=encode_cursor(created_at=deps.clock.now(), item_id=_MIN_UUID)
    )
    run_history_tail = _RunHistoryTail()
    enclosure_timeline_tail = _EnclosureTimelineTail()
    activity_tail = _ActivityTail()

    backoff = _RECONNECT_INITIAL_SECONDS
    sequence = 0
    last_hash: str | None = None
    tick_seconds = deps.settings.status_push_tick_seconds

    while True:
        try:
            async with connect(
                url, additional_headers=headers, max_size=_MAX_INBOUND_FRAME_BYTES
            ) as sock:
                _log.info(f"{_LOG_PREFIX}.connected", url=url)
                backoff = _RECONNECT_INITIAL_SECONDS
                last_hash = None  # force one full push right after (re)connect
                run_history_tail.on_reconnect()
                enclosure_timeline_tail.on_reconnect()
                ticks_since_push = _HEARTBEAT_TICKS  # push immediately on connect

                inbox: asyncio.Queue[_Inbound] | None = None
                reader_task: asyncio.Task[None] | None = None
                if request_max_per_tick > 0:
                    inbox = asyncio.Queue(maxsize=_REQUEST_INBOX_SIZE)
                    reader_task = asyncio.create_task(_read_requests(sock, inbox))
                try:
                    while True:
                        generated_at = deps.clock.now().isoformat()
                        fields, extra_messages = await _build_payload_fields(
                            deps,
                            list_runs=list_runs,
                            list_subjects=list_subjects,
                            list_campaigns=list_campaigns,
                            list_datasets=list_datasets,
                            list_procedures=list_procedures,
                            list_clearances=list_clearances,
                            list_plans=list_plans,
                            list_enclosures=list_enclosures,
                            decision_tail=decision_tail,
                            fleet_tail=fleet_tail,
                            list_decisions=list_decisions,
                            run_history_tail=run_history_tail,
                            get_run_history=get_run_history,
                            enclosure_timeline_tail=enclosure_timeline_tail,
                            get_enclosure_history=get_enclosure_history,
                            activity_tail=activity_tail,
                            activity_trail=activity_trail,
                            translator=translator,
                            generated_at=generated_at,
                            producer_id=producer_id,
                        )
                        # Extras (run history, activity) are exempt from the
                        # hash/heartbeat gate below by construction: each tail's
                        # `poll` only ever returns what is new this tick, so
                        # there is nothing to de-duplicate here.
                        for message in extra_messages:
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
                        # After the snapshot send, before the sleep: a slow
                        # or hung request delays only the NEXT tick, never
                        # this one (see this module's "On-demand requests"
                        # section).
                        if inbox is not None:
                            await _serve_requests(
                                inbox,
                                sock,
                                deps=deps,
                                get_run_history=get_run_history,
                                run_history_tail=run_history_tail,
                                producer_id=producer_id,
                                generated_at=generated_at,
                                max_per_tick=request_max_per_tick,
                            )
                        await asyncio.sleep(tick_seconds)
                finally:
                    if reader_task is not None:
                        reader_task.cancel()
                        await asyncio.gather(reader_task, return_exceptions=True)
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
    list_procedures: ListProceduresHandler,
    list_clearances: ListClearancesHandler,
    list_plans: ListPlansHandler,
    list_enclosures: ListEnclosuresHandler,
    list_decisions: ListDecisionsHandler,
    get_run_history: GetRunHistoryHandler,
    get_enclosure_history: GetEnclosureHistoryHandler,
    translator: RunTranslator | None = None,
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

    `translator` is `run_translator_lifespan`'s own yielded value, so the
    caller must enter that context manager first and bind it (`main.py`
    does this by ordering `run_translator_lifespan(...) as translator`
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
    # Constructed here, not threaded in as a caller-supplied parameter like
    # the eight query handlers above: this port has exactly one consumer
    # (this module), so it is not a Kernel field (see
    # `EventActivityTrail`'s own module docstring), and `deps.pool` /
    # `deps.event_store` are already on hand. Mirrors the
    # `if deps.pool is not None:` branch every BC's own `wire_<bc>` uses.
    activity_trail: EventActivityTrail
    if deps.pool is not None:
        activity_trail = PostgresEventActivityTrail(deps.pool)
    else:
        assert isinstance(deps.event_store, InMemoryEventStore), (
            "deps.pool is None implies every adapter is in-memory"
        )
        activity_trail = InMemoryEventActivityTrail(deps.event_store)
    task = asyncio.create_task(
        _push_loop(
            deps,
            list_runs=list_runs,
            list_subjects=list_subjects,
            list_campaigns=list_campaigns,
            list_datasets=list_datasets,
            list_procedures=list_procedures,
            list_clearances=list_clearances,
            list_plans=list_plans,
            list_enclosures=list_enclosures,
            list_decisions=list_decisions,
            get_run_history=get_run_history,
            get_enclosure_history=get_enclosure_history,
            activity_trail=activity_trail,
            producer_id=producer_id,
            url=url,
            translator=translator,
            request_max_per_tick=deps.settings.status_push_request_max_per_tick,
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


__all__ = [
    "build_enclosure_timeline_message",
    "build_run_history_message",
    "build_snapshot",
    "status_push_lifespan",
]
