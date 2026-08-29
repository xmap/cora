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

Holds the single most-recent snapshot AND a bounded ring of up to
`_RUN_HISTORY_CACHE_SIZE` pushed run histories, both in process-local
memory only. It is not a database and is not meant to be one: nothing
about the beamline persists to disk here, so a relay restart has no
retention question, just a smaller blast radius than before -- a
compromise of this box now exposes the last snapshot (~20 KB) AND up to
20 cached run histories, still never anything not already pushed to it,
still never anything on disk.

Six endpoints, one port, one library (`websockets`' `process_request`
hook answers plain HTTP so a WebSocket-only library can still serve the
static page and JS):

  - `GET /`                   the status page (page.html, served verbatim)
  - `GET /scrubber.js`        the REWIND scrubber's script (served verbatim)
  - `GET /run-history`        the current run-history index (id, name,
                              status, terminal, generated_at per cached
                              run, newest first) -- the picker's fallback
                              for a page load before any index frame
                              arrives over `/watch`
  - `GET /run-history/<id>`   one cached run's full history, or 404 with a
                              plain "not pushed since the relay started"
                              body -- both are reads from THIS relay's own
                              cache, never a reach toward the producer
  - `WS  /ingest`             the producer connects here (Authorization:
                              Bearer <token> required; rejected at the HTTP
                              layer, before the WebSocket handshake
                              completes, when the token is wrong or absent)
  - `WS  /watch`              a browser connects here; sent the current
                              snapshot (or a "no producer yet" state) and
                              the run-history index immediately on connect,
                              then every subsequent snapshot, run-history
                              index update, and producer connect /
                              disconnect transition, live

Run: `STATUS_RELAY_TOKEN=<token> python relay.py [--host 0.0.0.0] [--port 8099]`
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any
from uuid import UUID

import websockets
from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

_log = logging.getLogger("status_relay")

_HTTP_OK = 200
_RUN_HISTORY_CACHE_SIZE = 20
"""Bounded ring of pushed run histories this relay keeps, evicting the
oldest past this cap. The producer keeps its own independent ring
(`cora.api._status_push._RunHistoryTail`); this one exists so a relay
that outlives many producer reconnects still bounds its own memory."""

_PAGE_PATH = Path(__file__).parent / "page.html"
_SCRUBBER_JS_PATH = Path(__file__).parent / "scrubber.js"

# Process-local only, by design; see the module docstring.
_latest_snapshot: dict[str, Any] | None = None
_producer_connected = False
_watchers: set[ServerConnection] = set()
_run_histories: OrderedDict[str, dict[str, Any]] = OrderedDict()


def _require_token() -> str:
    token = os.environ.get("STATUS_RELAY_TOKEN")
    if not token:
        print("STATUS_RELAY_TOKEN must be set (the producer's status_push_token).")
        sys.exit(1)
    return token


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


async def _handle_producer(ws: ServerConnection) -> None:
    global _producer_connected  # noqa: PLW0603
    _producer_connected = True
    _log.info("producer.connected")
    _broadcast_connection_state()
    try:
        async for message in ws:
            global _latest_snapshot  # noqa: PLW0603
            try:
                payload = json.loads(message)
            except (TypeError, ValueError):
                _log.warning("producer.malformed_message")
                continue
            kind = payload.get("kind", "snapshot") if isinstance(payload, dict) else "snapshot"
            if kind == "snapshot":
                _latest_snapshot = payload
                if _watchers:
                    websockets.broadcast(_watchers, message)
            elif kind == "run_history":
                _store_run_history(payload)
                _broadcast_run_history_index()
            elif kind == "activity":
                # No relay-side cache, unlike snapshot/run_history: flowing
                # mode's rolling window lives in each browser, not here, so
                # this is a pure pass-through. A watcher that connects mid-
                # flow simply starts receiving from that point on, same as
                # it already does for the live tables.
                if _watchers:
                    websockets.broadcast(_watchers, message)
            else:
                # Forward compatibility: a newer producer's message kind
                # must never wedge an older relay.
                _log.warning("producer.unknown_kind", extra={"kind": kind})
    finally:
        _producer_connected = False
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


def _plain_response(status_code: int, body: bytes, *, content_type: str) -> Response:
    headers = Headers()
    headers["Content-Type"] = content_type
    headers["Content-Length"] = str(len(body))
    reason = "OK" if status_code == _HTTP_OK else "Error"
    return Response(status_code, reason, headers, body)


def _json_response(status_code: int, obj: dict[str, Any]) -> Response:
    return _plain_response(status_code, json.dumps(obj).encode(), content_type="application/json")


_RUN_HISTORY_PATH_PREFIX = "/run-history/"


def _process_request(
    connection: ServerConnection, request: Request, *, expected_token: str
) -> Response | None:
    """Answer plain HTTP requests directly; return `None` to let a `/ingest`
    or `/watch` request proceed to the normal WebSocket handshake."""
    _ = connection
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
        if cached is None:
            return _json_response(
                404, {"detail": f"run {run_id} was not pushed since the relay started"}
            )
        return _json_response(200, cached)
    if request.path == "/ingest":
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {expected_token}":
            return _plain_response(401, b"unauthorized", content_type="text/plain")
        return None
    if request.path == "/watch":
        return None
    return _plain_response(404, b"not found", content_type="text/plain")


async def _run(host: str, port: int, token: str) -> None:
    def process_request(connection: ServerConnection, request: Request) -> Response | None:
        return _process_request(connection, request, expected_token=token)

    async with serve(_handler, host, port, process_request=process_request):
        _log.info("relay.started", extra={"host": host, "port": port})
        await asyncio.get_running_loop().create_future()  # run forever


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")  # noqa: S104 -- operator-run relay, not a library default
    parser.add_argument("--port", type=int, default=8099)
    args = parser.parse_args()
    token = _require_token()
    asyncio.run(_run(args.host, args.port, token))


if __name__ == "__main__":
    main()
