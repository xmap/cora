"""The status relay: a small, standalone process meant to run on a host
that has internet reach (for CORA's 2-BM deployment: `lyra`, the jump host
outside the beamline's own controls network), receiving a live snapshot
pushed OUTBOUND from a CORA deployment that itself has no inbound
reachability (see `cora.api._status_push` for the producer side and
docs/deployments/2-bm for the network topology this exists to bridge).

Deliberately imports nothing from `cora`. This is a host-layer artifact,
the same category as `infra/backup/`, not an application module; it must
run with nothing but the standard library plus `websockets` installed,
independent of the CORA deployment's own environment.

Holds the single most-recent snapshot, a bounded ring of up to
`_RUN_HISTORY_CACHE_SIZE` pushed run histories, every enclosure timeline
ever received, and the last `_ACTIVITY_BUFFER_SECONDS` of activity
events, all in process-local memory only. It is not a database and is
not meant to be one: nothing about the beamline persists to disk here,
so a relay restart has no retention question, just a smaller blast
radius than before -- a compromise of this box now exposes the last
snapshot (~20 KB), up to 20 cached run histories, every enclosure's
permit/lifecycle history, and a few minutes of event metadata, still
never anything not already pushed to it, still never anything on disk.

Six endpoints, one port, one library (`websockets`' `process_request`
hook answers plain HTTP so a WebSocket-only library can still serve the
static page and JS). Every path but `/ingest` requires HTTP Basic auth
(`websockets.asyncio.server.basic_auth`, `STATUS_RELAY_VIEWER_USER` /
`STATUS_RELAY_VIEWER_PASSWORD`): a second, independent gate on top of the
existing SSH-tunnel/loopback-bind posture, added specifically because
`/run-history/<id>` below can now reach ANY run in the record, not only
the up-to-20 most recently pushed one:

  - `GET /`                   the status page (page.html, served verbatim)
  - `GET /scrubber.js`        the REWIND scrubber's script (served verbatim)
  - `GET /run-history`        the current run-history index (id, name,
                              status, terminal, generated_at per cached
                              run, newest first) -- the picker's fallback
                              for a page load before any index frame
                              arrives over `/watch`
  - `GET /run-history/<id>`   one run's full history. Served from THIS
                              relay's own cache when present; on a cache
                              miss, asked of the live producer on demand
                              (`_request_run_history_from_producer`) if one
                              is connected, so this reaches any run in the
                              record, not only a cached one. 404 when the
                              producer confirms the run does not exist,
                              503 when neither the cache nor a live
                              producer can answer, 502/504 for the
                              producer's own error/unauthorized/timeout
                              outcomes
  - `WS  /ingest`             the producer connects here (Authorization:
                              Bearer <token> required; rejected at the HTTP
                              layer, before the WebSocket handshake
                              completes, when the token is wrong or absent;
                              this is the ONE path Basic auth does not
                              guard, since the caller here is the producer,
                              not a human viewer)
  - `WS  /watch`              a browser connects here; sent the current
                              snapshot (or a "no producer yet" state), the
                              run-history index, every cached enclosure
                              timeline, and a backfill of the last
                              `_ACTIVITY_BUFFER_SECONDS` of activity events
                              immediately on connect, then every subsequent
                              snapshot, run-history index update,
                              enclosure-timeline update, and activity
                              event, live, plus producer connect /
                              disconnect transitions. Enclosure timelines
                              and activity are pure pass-through PLUS a
                              replay cache (unlike run history's
                              cache-or-ask-the-producer shape): at pilot
                              scale there are only a handful of enclosures
                              and a bounded few minutes of activity, so
                              both fit in memory with no on-demand request
                              path needed at all

Run: `STATUS_RELAY_TOKEN=<token> STATUS_RELAY_VIEWER_USER=<user>
STATUS_RELAY_VIEWER_PASSWORD=<password> python relay.py [--host 0.0.0.0]
[--port 8099]`
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import websockets
from websockets.asyncio.server import ServerConnection, basic_auth, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

_log = logging.getLogger("status_relay")

_HTTP_OK = 200
_RUN_HISTORY_CACHE_SIZE = 20
"""Bounded ring of pushed run histories this relay keeps, evicting the
oldest past this cap. The producer keeps its own independent ring
(`cora.api._status_push._RunHistoryTail`); this one exists so a relay
that outlives many producer reconnects still bounds its own memory."""

_MAX_INFLIGHT_REQUESTS = 4
"""Cap on concurrently outstanding `run_history_request`s this relay will
have open against the producer at once. Several browser HTTP handlers can
race to ask for different runs; past this cap the relay refuses a new
request as busy rather than queuing behind the producer's own
`status_push_request_max_per_tick` drain rate."""
_REQUEST_TIMEOUT_SECONDS = 6.0
"""How long this relay waits for a `run_history_response` before giving
up on one request. Comfortably above the producer's own worst case
(`_REQUEST_PHASE_BUDGET_SECONDS` plus one tick), so a real answer is not
mistaken for a timeout under ordinary load."""
_SEND_TIMEOUT_SECONDS = 2.0
"""How long this relay waits to hand a request frame to the producer
socket's own send buffer. Not the round-trip: only the local write."""
_OPEN_TIMEOUT_SECONDS = 15
"""`websockets.serve`'s own `open_timeout` (default 10s), bumped so this
relay's async `process_request` -- which can now await a full producer
round-trip on a `/run-history/<id>` cache miss -- never exceeds it.
Exceeding `open_timeout` aborts the TCP handshake with no HTTP response
at all, turning a legitimate 504 into an unexplained `Failed to fetch`."""

_ACTIVITY_BUFFER_SECONDS = 24 * 60 * 60
"""How long this relay backfills a freshly-connecting watcher with recent
`"activity"` events, mirroring `page.html`'s own `FLOWING_WINDOW_MS`: a
separate literal, not a shared constant, since this relay imports nothing
from `cora` and `page.html` is served verbatim with no build step either
(see the module docstring). Keeping the two in sync matters only in the
direction that this value should be >= the browser's own window --
buffering less would leave a visible gap on reconnect, buffering more is
harmless since the browser prunes anything older than its own window on
receipt (`pruneFlowingBuffer`)."""

_ACTIVITY_BUFFER_MAX_EVENTS = 40_000
"""Hard ceiling on buffered events, independent of their age. At the measured
2-BM rate (228 events in the busiest hour) a day is roughly 5,500 events, so
this is about seven times the expected peak and exists for the case the
measurement does not cover: a backfill, a migration, or any burst that would
otherwise let one day of wall-clock consume unbounded memory on the jump host
and arrive at a browser as one enormous replay message. When it bites, the
OLDEST events are dropped and `_activity_buffer_truncated` says so, because a
buffer that silently starts later than it claims makes a busy morning look
like a quiet one."""

_activity_buffer_truncated = False
"""Whether the event cap has ever dropped anything this process. Reported to
watchers in the replay message: absent data must not read as an absence of
activity."""

_PAGE_PATH = Path(__file__).parent / "page.html"
_SCRUBBER_JS_PATH = Path(__file__).parent / "scrubber.js"

# Process-local only, by design; see the module docstring.
_latest_snapshot: dict[str, Any] | None = None
_producer_connected = False
_producer_sock: ServerConnection | None = None
_producer_id: str | None = None
"""The current producer connection's own `producer_id` (every message it
sends carries one), used purely to detect an app restart on the OTHER
end of an otherwise-unchanged-looking reconnect: a mere network blip
reconnect keeps the same `producer_id` (it is minted once per process
lifetime, not per connection), while a real restart mints a new one.
Either way, `_handle_producer`'s own connect/disconnect already fails
every pending request eagerly; this is the belt for the case a stale
response would otherwise be mistaken for a fresh one."""
_producer_send_lock = asyncio.Lock()
"""Not needed for frame-safety (concurrent `send`s are not actually
frame-unsafe for unfragmented strings in the installed `websockets`
version), but taken anyway: several concurrent HTTP handlers can send at
once, and a future maintainer should not need to know `websockets`
internals to convince themselves that is safe."""
_pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
"""In-flight `run_history_request`s, keyed by `request_id`, capped at
`_MAX_INFLIGHT_REQUESTS`."""
_watchers: set[ServerConnection] = set()
_run_histories: OrderedDict[str, dict[str, Any]] = OrderedDict()
_enclosure_timelines: dict[str, dict[str, Any]] = {}
"""Every enclosure this relay has ever received a timeline for, keyed by
`enclosure_id`. A plain dict, not an `OrderedDict` with a cap like
`_run_histories`: at pilot scale there are only a handful of Enclosures,
so the whole subject set fits in memory with no eviction, and REWIND
reaching any of them needs no producer round trip the way reaching any
RUN does -- see `cora.api._status_push._EnclosureTimelineTail`'s own
docstring for why."""
_activity_buffer: list[dict[str, Any]] = []
"""Individual events (not whole `"activity"` messages) from the last
`_ACTIVITY_BUFFER_SECONDS`, flattened across however many producer
messages they arrived in, pruned by `occurred_at` on every new arrival
and again right before a replay. Exists purely so a watcher that connects
mid-quiet-period still gets caught up: before this, flowing mode was a
pure pass-through with no way for a fresh connection (or a browser
refresh, or a resumed SSH tunnel) to see anything that happened before it
attached, unlike the snapshot and enclosure-timeline rings which already
replay on connect."""


def _require_token() -> str:
    token = os.environ.get("STATUS_RELAY_TOKEN")
    if not token:
        print("STATUS_RELAY_TOKEN must be set (the producer's status_push_token).")
        sys.exit(1)
    return token


def _require_viewer_credentials() -> tuple[str, str]:
    """The shared Basic-auth login every path but `/ingest` requires. Both
    vars are required, not optional-with-a-permissive-default: the whole
    point of this gate is that `/run-history/<id>` can now reach any run
    in the record, and that widening should never run unauthenticated by
    a missing env var."""
    user = os.environ.get("STATUS_RELAY_VIEWER_USER")
    password = os.environ.get("STATUS_RELAY_VIEWER_PASSWORD")
    if not user or not password:
        print(
            "STATUS_RELAY_VIEWER_USER and STATUS_RELAY_VIEWER_PASSWORD must both be "
            "set (the shared login every viewer path but /ingest requires)."
        )
        sys.exit(1)
    return user, password


def _connection_state_message() -> str:
    return json.dumps({"producer_connected": _producer_connected})


def _run_history_index() -> dict[str, Any]:
    """The index frame: one summary row per cached run, newest first, no
    bodies -- a few hundred bytes regardless of how large the cached
    histories themselves are."""
    return {
        "kind": "run_history_index",
        "runs": [
            {
                "run_id": message["run_id"],
                "name": message["name"],
                "status": message["status"],
                "terminal": message["terminal"],
                "generated_at": message["generated_at"],
            }
            for message in reversed(_run_histories.values())
        ],
    }


def _broadcast_connection_state() -> None:
    if _watchers:
        websockets.broadcast(_watchers, _connection_state_message())


def _broadcast_run_history_index() -> None:
    if _watchers:
        websockets.broadcast(_watchers, json.dumps(_run_history_index()))


def _store_run_history(message: dict[str, Any]) -> None:
    run_id = message.get("run_id")
    if not isinstance(run_id, str):
        _log.warning("producer.malformed_run_history")
        return
    _run_histories[run_id] = message
    _run_histories.move_to_end(run_id)
    while len(_run_histories) > _RUN_HISTORY_CACHE_SIZE:
        _run_histories.popitem(last=False)


def _store_enclosure_timeline(message: dict[str, Any]) -> None:
    enclosure_id = message.get("enclosure_id")
    if not isinstance(enclosure_id, str):
        _log.warning("producer.malformed_enclosure_timeline")
        return
    _enclosure_timelines[enclosure_id] = message


def _prune_activity_buffer() -> None:
    cutoff = datetime.now(UTC).timestamp() - _ACTIVITY_BUFFER_SECONDS
    global _activity_buffer, _activity_buffer_truncated  # noqa: PLW0603
    _activity_buffer = [event for event in _activity_buffer if _event_epoch(event) >= cutoff]
    if len(_activity_buffer) > _ACTIVITY_BUFFER_MAX_EVENTS:
        dropped = len(_activity_buffer) - _ACTIVITY_BUFFER_MAX_EVENTS
        _activity_buffer = _activity_buffer[-_ACTIVITY_BUFFER_MAX_EVENTS:]
        _activity_buffer_truncated = True
        _log.warning("activity_buffer.capped", extra={"dropped": dropped})


def _event_epoch(event: dict[str, Any]) -> float:
    """`occurred_at` as a Unix timestamp, or `-inf` for a malformed/missing
    one so it prunes out on the next pass rather than wedging the buffer
    open forever."""
    occurred_at = event.get("occurred_at")
    if not isinstance(occurred_at, str):
        return float("-inf")
    try:
        return datetime.fromisoformat(occurred_at).timestamp()
    except ValueError:
        return float("-inf")


def _store_activity_events(message: dict[str, Any]) -> None:
    events = message.get("events")
    if not isinstance(events, list):
        _log.warning("producer.malformed_activity")
        return
    _activity_buffer.extend(events)
    _prune_activity_buffer()


def _activity_replay_message() -> dict[str, Any] | None:
    """One synthetic `"activity"` message backfilling a freshly-connecting
    watcher, in the exact shape `build_activity_message` already produces
    (`page.html`'s `handleActivity` just concatenates `events`, so it needs
    no replay-specific handling). `None` when the buffer is empty, mirroring
    the producer's own "never sent when rows is empty" convention."""
    _prune_activity_buffer()
    if not _activity_buffer:
        return None
    return {
        "kind": "activity",
        "schema_version": 1,
        "producer_id": _producer_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "events": list(_activity_buffer),
        # Only ever sent on a replay, and only true when something was
        # actually dropped: a watcher that panned to the left edge would
        # otherwise read the start of this buffer as the start of the record.
        "replay_truncated": _activity_buffer_truncated,
        "retained_seconds": _ACTIVITY_BUFFER_SECONDS,
    }


def _fail_all_pending(reason: str) -> None:
    """Resolve every in-flight `run_history_request` with an exception
    immediately, rather than letting each one sit until its own
    `_REQUEST_TIMEOUT_SECONDS` elapses. Called on producer disconnect and
    on a detected `producer_id` change (an app restart on the other end);
    `_request_run_history_from_producer`'s own `finally` still pops each
    entry from `_pending`, so this only needs to resolve the futures."""
    if not _pending:
        return
    _log.warning(
        "producer.failing_pending_requests", extra={"reason": reason, "count": len(_pending)}
    )
    for fut in _pending.values():
        if not fut.done():
            fut.set_exception(ConnectionClosed(None, None))


async def _handle_producer(ws: ServerConnection) -> None:
    global _producer_connected, _producer_sock  # noqa: PLW0603
    _producer_connected = True
    _producer_sock = ws
    _log.info("producer.connected")
    _broadcast_connection_state()
    try:
        async for message in ws:
            global _latest_snapshot, _producer_id  # noqa: PLW0603
            try:
                payload = json.loads(message)
            except (TypeError, ValueError):
                _log.warning("producer.malformed_message")
                continue
            kind = payload.get("kind", "snapshot") if isinstance(payload, dict) else "snapshot"
            incoming_producer_id = payload.get("producer_id") if isinstance(payload, dict) else None
            if (
                isinstance(incoming_producer_id, str)
                and _producer_id is not None
                and incoming_producer_id != _producer_id
            ):
                _fail_all_pending("producer_restarted")
            if isinstance(incoming_producer_id, str):
                _producer_id = incoming_producer_id
            if kind == "snapshot":
                _latest_snapshot = payload
                if _watchers:
                    websockets.broadcast(_watchers, message)
            elif kind == "run_history":
                _store_run_history(payload)
                _broadcast_run_history_index()
            elif kind == "enclosure_timeline":
                # Unlike `activity`, DOES cache (in `_enclosure_timelines`,
                # replayed to every new watcher in `_handle_watcher`): a
                # REWIND viewer picking an enclosure needs its timeline to
                # still be here after connecting, not only future updates.
                # Unlike `run_history`, needs no producer round trip on a
                # cache miss: there is no cache miss at pilot scale, since
                # every enclosure's timeline is pushed on every producer
                # (re)connect (see `_EnclosureTimelineTail.on_reconnect`).
                _store_enclosure_timeline(payload)
                if _watchers:
                    websockets.broadcast(_watchers, message)
            elif kind == "activity":
                # Buffered (`_store_activity_events`) AND passed through
                # live: a watcher connecting mid-flow gets the buffer as a
                # replay in `_handle_watcher`, then this same broadcast
                # keeps it current, same as it already does for the live
                # tables.
                _store_activity_events(payload)
                if _watchers:
                    websockets.broadcast(_watchers, message)
            elif kind == "run_history_response":
                request_id = payload.get("request_id") if isinstance(payload, dict) else None
                history = payload.get("history") if isinstance(payload, dict) else None
                if payload.get("status") == "ok" and isinstance(history, dict):
                    # Cache unconditionally, even if the HTTP handler that
                    # triggered this already gave up (timed out, or its
                    # Future was abandoned by a producer-restart epoch
                    # change): the DB read already happened on arcturus,
                    # so a later retry deserves to hit cache rather than
                    # pay for it twice.
                    _store_run_history(history)
                    _broadcast_run_history_index()
                fut = _pending.get(request_id) if isinstance(request_id, str) else None
                if fut is not None and not fut.done():
                    fut.set_result(payload)
            else:
                # Forward compatibility: a newer producer's message kind
                # must never wedge an older relay.
                _log.warning("producer.unknown_kind", extra={"kind": kind})
    finally:
        _producer_connected = False
        _producer_sock = None
        _fail_all_pending("producer_disconnected")
        _log.info("producer.disconnected")
        _broadcast_connection_state()


async def _handle_watcher(ws: ServerConnection) -> None:
    _watchers.add(ws)
    _log.info("watcher.connected", extra={"count": len(_watchers)})
    try:
        if _latest_snapshot is not None:
            await ws.send(json.dumps(_latest_snapshot))
        await ws.send(_connection_state_message())
        await ws.send(json.dumps(_run_history_index()))
        for message in _enclosure_timelines.values():
            await ws.send(json.dumps(message))
        activity_replay = _activity_replay_message()
        if activity_replay is not None:
            await ws.send(json.dumps(activity_replay))
        async for _ in ws:
            pass  # watchers never send anything meaningful; drain and ignore
    finally:
        _watchers.discard(ws)
        _log.info("watcher.disconnected", extra={"count": len(_watchers)})


async def _handler(ws: ServerConnection) -> None:
    path = ws.request.path if ws.request is not None else ""
    if path == "/ingest":
        await _handle_producer(ws)
    elif path == "/watch":
        await _handle_watcher(ws)
    else:
        await ws.close(code=1008, reason="unknown path")


def _plain_response(
    status_code: int,
    body: bytes,
    *,
    content_type: str,
    extra_headers: dict[str, str] | None = None,
) -> Response:
    headers = Headers()
    headers["Content-Type"] = content_type
    headers["Content-Length"] = str(len(body))
    for key, value in (extra_headers or {}).items():
        headers[key] = value
    reason = "OK" if status_code == _HTTP_OK else "Error"
    return Response(status_code, reason, headers, body)


def _json_response(
    status_code: int, obj: dict[str, Any], *, extra_headers: dict[str, str] | None = None
) -> Response:
    return _plain_response(
        status_code,
        json.dumps(obj).encode(),
        content_type="application/json",
        extra_headers=extra_headers,
    )


async def _request_run_history_from_producer(run_id: str) -> Response:
    """Ask the live producer for one run's full history, on a relay cache
    miss. The caller (`_process_request`) has already checked the cache
    first, so reaching here at all means the cache could not answer;
    degradation from here is: producer connected -> answer live below,
    producer disconnected -> the 503 immediately below, neither of which
    is a confirmed "the run does not exist" the way a producer-reported
    `not_found` is.
    """
    if _producer_sock is None:
        return _json_response(
            503, {"detail": "producer not connected; try again once the live feed reconnects"}
        )
    if len(_pending) >= _MAX_INFLIGHT_REQUESTS:
        return _json_response(
            503,
            {"detail": "too many run-history requests in flight; try again shortly"},
            extra_headers={"Retry-After": "2"},
        )

    request_id = str(uuid4())
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[dict[str, Any]] = loop.create_future()
    _pending[request_id] = fut
    frame = json.dumps(
        {
            "kind": "run_history_request",
            "schema_version": 1,
            "request_id": request_id,
            "run_id": run_id,
        }
    )
    try:
        async with _producer_send_lock, asyncio.timeout(_SEND_TIMEOUT_SECONDS):
            await _producer_sock.send(frame)
        async with asyncio.timeout(_REQUEST_TIMEOUT_SECONDS):
            response = await fut
    except TimeoutError:
        return _json_response(504, {"detail": "producer did not respond in time"})
    except ConnectionClosed:
        return _json_response(503, {"detail": "producer disconnected while answering"})
    finally:
        # Discarded regardless of outcome: `_handle_producer` already
        # caches a successful `history` body unconditionally, whether or
        # not a waiter is still here to receive it.
        _pending.pop(request_id, None)

    return _run_history_response_to_http(response, run_id)


def _run_history_response_to_http(response: dict[str, Any], run_id: str) -> Response:
    """Map one `run_history_response` payload to an HTTP response. Kept
    apart from `_request_run_history_from_producer` so the mapping itself
    -- the part most worth testing in isolation -- needs no socket."""
    status = response.get("status")
    if status == "ok" and isinstance(response.get("history"), dict):
        return _json_response(200, response["history"])
    if status == "not_found":
        return _json_response(404, {"detail": f"run {run_id} was not found in CORA's record"})
    if status == "unauthorized":
        return _json_response(
            502, {"detail": "the producer's read principal is not authorized for this run"}
        )
    # "malformed" / "unsupported" / "error" / an "ok" with no usable body /
    # any status this relay does not recognize: all mean the producer
    # could not give a usable answer, which is this relay's own upstream
    # failure to surface, not the browser's.
    return _json_response(502, {"detail": f"producer reported status={status!r}"})


_RUN_HISTORY_PATH_PREFIX = "/run-history/"


async def _process_request(
    connection: ServerConnection,
    request: Request,
    *,
    expected_token: str,
    check_viewer_auth: Callable[[ServerConnection, Request], Awaitable[Response | None]],
) -> Response | None:
    """Answer plain HTTP requests directly; return `None` to let a `/ingest`
    or `/watch` request proceed to the normal WebSocket handshake.

    Every path but `/ingest` is gated by `check_viewer_auth`
    (`websockets.asyncio.server.basic_auth`) first: the producer
    authenticates with its own bearer token below, a human viewer with
    this shared login instead.
    """
    if request.path != "/ingest":
        denied = await check_viewer_auth(connection, request)
        if denied is not None:
            return denied
    if request.path == "/":
        body = _PAGE_PATH.read_bytes()
        return _plain_response(200, body, content_type="text/html; charset=utf-8")
    if request.path == "/scrubber.js":
        body = _SCRUBBER_JS_PATH.read_bytes()
        return _plain_response(200, body, content_type="text/javascript; charset=utf-8")
    if request.path == "/run-history":
        return _json_response(200, _run_history_index())
    if request.path.startswith(_RUN_HISTORY_PATH_PREFIX):
        raw_id = request.path[len(_RUN_HISTORY_PATH_PREFIX) :]
        try:
            run_id = str(UUID(raw_id))
        except ValueError:
            return _json_response(400, {"detail": "malformed run id"})
        cached = _run_histories.get(run_id)
        if cached is not None:
            return _json_response(200, cached)
        return await _request_run_history_from_producer(run_id)
    if request.path == "/ingest":
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {expected_token}":
            return _plain_response(401, b"unauthorized", content_type="text/plain")
        return None
    if request.path == "/watch":
        return None
    return _plain_response(404, b"not found", content_type="text/plain")


async def _run(host: str, port: int, token: str, viewer_user: str, viewer_password: str) -> None:
    check_viewer_auth = basic_auth(realm="cora-status", credentials=(viewer_user, viewer_password))

    async def process_request(connection: ServerConnection, request: Request) -> Response | None:
        return await _process_request(
            connection, request, expected_token=token, check_viewer_auth=check_viewer_auth
        )

    async with serve(
        _handler,
        host,
        port,
        process_request=process_request,
        open_timeout=_OPEN_TIMEOUT_SECONDS,
    ):
        _log.info("relay.started", extra={"host": host, "port": port})
        await asyncio.get_running_loop().create_future()  # run forever


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")  # noqa: S104 -- operator-run relay, not a library default
    parser.add_argument("--port", type=int, default=8099)
    args = parser.parse_args()
    token = _require_token()
    viewer_user, viewer_password = _require_viewer_credentials()
    asyncio.run(_run(args.host, args.port, token, viewer_user, viewer_password))


if __name__ == "__main__":
    main()
