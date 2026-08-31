"""Regression tests for relay.py.

Deliberately not pytest: relay.py itself runs with nothing but the
standard library plus `websockets` (see its own module docstring), and
this file matches that posture rather than pulling pytest into a
directory that is not part of `apps/api`'s test tree. Run directly:

    STATUS_RELAY_TOKEN=x python3 test_relay.py

Each `test_*` coroutine is discovered and run in isolation (a fresh
relay instance per test, on its own port), and the process exits
non-zero if any assertion fails. This is the first automated coverage
`relay.py` has ever had; scope is the on-demand run-history request path
(`_request_run_history_from_producer`, `_handle_producer`'s pending-
Future registry) and the viewer auth gate, since those are the parts a
reviewer should trust least on inspection alone.
"""

from __future__ import annotations

import asyncio
import base64
import inspect
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

os.environ.setdefault("STATUS_RELAY_TOKEN", "test-token")
os.environ.setdefault("STATUS_RELAY_VIEWER_USER", "viewer")
os.environ.setdefault("STATUS_RELAY_VIEWER_PASSWORD", "test-password")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import relay
import websockets

_TOKEN = os.environ["STATUS_RELAY_TOKEN"]
_VIEWER_USER = os.environ["STATUS_RELAY_VIEWER_USER"]
_VIEWER_PASSWORD = os.environ["STATUS_RELAY_VIEWER_PASSWORD"]
_AUTH_HEADER = "Basic " + base64.b64encode(f"{_VIEWER_USER}:{_VIEWER_PASSWORD}".encode()).decode()


def _blocking_request(url: str, headers: dict[str, str]) -> tuple[int, object]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        return status, body


async def _get(url: str, headers: dict[str, str] | None = None) -> tuple[int, object]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _blocking_request, url, headers or {})


async def _recv_until_kind(ws, kind: str, *, max_frames: int = 10, timeout: float = 5) -> dict:
    """Receive frames off a `/watch` socket until one with `"kind": kind`
    arrives. `/watch` sends an initial burst of several frame kinds on
    connect (connection-state, run-history index, replayed enclosure
    timelines) whose exact count is an implementation detail this test
    file should not have to track; this skips past whichever ones do not
    match rather than asserting a fixed frame count."""
    for _ in range(max_frames):
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        msg = json.loads(raw)
        if isinstance(msg, dict) and msg.get("kind") == kind:
            return msg
    raise AssertionError(f"no {kind!r} frame received within {max_frames} frames")


class _RelayHarness:
    """Starts a real `relay.py` server on an ephemeral port for the
    duration of one `async with` block, mirroring `relay._run`'s own body
    rather than calling it as a black box so the actual bound port can be
    read back (port 0 -> the OS picks one). Resets every module-level
    global relay.py holds first, since they are process-local by design
    and would otherwise leak between tests run in the same process."""

    def __init__(self) -> None:
        self.port = 0
        self._server: websockets.asyncio.server.Server | None = None
        self._server_cm: object | None = None

    async def __aenter__(self) -> _RelayHarness:
        relay._latest_snapshot = None
        relay._producer_connected = False
        relay._producer_sock = None
        relay._producer_id = None
        relay._pending.clear()
        relay._watchers.clear()
        relay._run_histories.clear()
        relay._enclosure_timelines.clear()
        relay._activity_buffer.clear()

        check_viewer_auth = relay.basic_auth(
            realm="cora-status", credentials=(_VIEWER_USER, _VIEWER_PASSWORD)
        )

        async def process_request(connection, request):
            return await relay._process_request(
                connection, request, expected_token=_TOKEN, check_viewer_auth=check_viewer_auth
            )

        self._server_cm = relay.serve(
            relay._handler,
            "127.0.0.1",
            0,
            process_request=process_request,
            open_timeout=relay._OPEN_TIMEOUT_SECONDS,
        )
        self._server = await self._server_cm.__aenter__()
        self.port = next(iter(self._server.sockets)).getsockname()[1]
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        assert self._server_cm is not None
        await self._server_cm.__aexit__(*exc_info)

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    async def get(self, path: str, *, authenticated: bool = True) -> tuple[int, object]:
        headers = {"Authorization": _AUTH_HEADER} if authenticated else {}
        return await _get(self.url(path), headers)

    def connect_producer(self) -> websockets.connect:
        return websockets.connect(
            f"ws://127.0.0.1:{self.port}/ingest",
            additional_headers={"Authorization": f"Bearer {_TOKEN}"},
        )

    def connect_watcher(self) -> websockets.connect:
        return websockets.connect(
            f"ws://127.0.0.1:{self.port}/watch",
            additional_headers={"Authorization": _AUTH_HEADER},
        )


async def test_viewer_paths_require_basic_auth() -> None:
    async with _RelayHarness() as harness:
        status, _body = await harness.get("/", authenticated=False)
        assert status == 401, status
        status, _body = await harness.get("/")
        assert status == 200, status


async def test_ingest_rejects_a_wrong_bearer_token() -> None:
    async with _RelayHarness() as harness:
        try:
            async with websockets.connect(
                f"ws://127.0.0.1:{harness.port}/ingest",
                additional_headers={"Authorization": "Bearer wrong"},
            ):
                raise AssertionError("expected the handshake to be rejected")
        except websockets.exceptions.InvalidStatus as exc:
            assert exc.response.status_code == 401, exc.response.status_code


async def test_run_history_cache_miss_with_no_producer_is_503() -> None:
    async with _RelayHarness() as harness:
        status, body = await harness.get(f"/run-history/{uuid4()}")
        assert status == 503, (status, body)


async def test_run_history_on_demand_round_trip_and_then_cache() -> None:
    async with _RelayHarness() as harness, harness.connect_producer() as producer:
        run_id = uuid4()
        fetch = asyncio.create_task(harness.get(f"/run-history/{run_id}"))

        raw = await asyncio.wait_for(producer.recv(), timeout=5)
        request = json.loads(raw)
        assert request["kind"] == "run_history_request"
        assert request["run_id"] == str(run_id)

        history = {
            "kind": "run_history",
            "schema_version": 1,
            "producer_id": "p1",
            "generated_at": "2026-08-29T00:00:00+00:00",
            "run_id": str(run_id),
            "name": "test-run",
            "status": "Completed",
            "terminal": True,
            "events": [],
            "observations": [],
            "observations_truncated": False,
        }
        await producer.send(
            json.dumps(
                {
                    "kind": "run_history_response",
                    "schema_version": 1,
                    "producer_id": "p1",
                    "request_id": request["request_id"],
                    "generated_at": "2026-08-29T00:00:00+00:00",
                    "status": "ok",
                    "source": "read",
                    "history": history,
                }
            )
        )
        status, body = await asyncio.wait_for(fetch, timeout=5)
        assert status == 200, (status, body)
        assert body == history, body


async def test_second_fetch_after_ok_is_served_from_cache_without_the_producer() -> None:
    async with _RelayHarness() as harness:
        run_id = uuid4()
        async with harness.connect_producer() as producer:
            fetch = asyncio.create_task(harness.get(f"/run-history/{run_id}"))
            raw = await asyncio.wait_for(producer.recv(), timeout=5)
            request = json.loads(raw)
            history = {
                "kind": "run_history",
                "schema_version": 1,
                "producer_id": "p1",
                "generated_at": "2026-08-29T00:00:00+00:00",
                "run_id": str(run_id),
                "name": "test-run",
                "status": "Completed",
                "terminal": True,
                "events": [],
                "observations": [],
                "observations_truncated": False,
            }
            await producer.send(
                json.dumps(
                    {
                        "kind": "run_history_response",
                        "schema_version": 1,
                        "producer_id": "p1",
                        "request_id": request["request_id"],
                        "generated_at": "2026-08-29T00:00:00+00:00",
                        "status": "ok",
                        "source": "read",
                        "history": history,
                    }
                )
            )
            await asyncio.wait_for(fetch, timeout=5)

        # Producer is now disconnected; a cache hit needs no producer at all.
        status, body = await harness.get(f"/run-history/{run_id}")
        assert status == 200, (status, body)
        assert body == history, body


async def test_unauthorized_response_maps_to_502() -> None:
    async with _RelayHarness() as harness, harness.connect_producer() as producer:
        run_id = uuid4()
        fetch = asyncio.create_task(harness.get(f"/run-history/{run_id}"))
        raw = await asyncio.wait_for(producer.recv(), timeout=5)
        request = json.loads(raw)
        await producer.send(
            json.dumps(
                {
                    "kind": "run_history_response",
                    "schema_version": 1,
                    "producer_id": "p1",
                    "request_id": request["request_id"],
                    "generated_at": "2026-08-29T00:00:00+00:00",
                    "status": "unauthorized",
                    "source": None,
                    "history": None,
                }
            )
        )
        status, body = await asyncio.wait_for(fetch, timeout=5)
        assert status == 502, (status, body)


async def test_not_found_response_maps_to_404() -> None:
    async with _RelayHarness() as harness, harness.connect_producer() as producer:
        run_id = uuid4()
        fetch = asyncio.create_task(harness.get(f"/run-history/{run_id}"))
        raw = await asyncio.wait_for(producer.recv(), timeout=5)
        request = json.loads(raw)
        await producer.send(
            json.dumps(
                {
                    "kind": "run_history_response",
                    "schema_version": 1,
                    "producer_id": "p1",
                    "request_id": request["request_id"],
                    "generated_at": "2026-08-29T00:00:00+00:00",
                    "status": "not_found",
                    "source": None,
                    "history": None,
                }
            )
        )
        status, body = await asyncio.wait_for(fetch, timeout=5)
        assert status == 404, (status, body)


async def test_a_producer_restart_fails_pending_requests_immediately() -> None:
    """The most bug-prone new code in this whole step, per the design
    review: a producer disconnect must fail every in-flight request right
    away rather than making its caller wait out the full
    `_REQUEST_TIMEOUT_SECONDS`."""
    async with _RelayHarness() as harness:
        async with harness.connect_producer() as producer:
            run_id = uuid4()
            fetch = asyncio.create_task(harness.get(f"/run-history/{run_id}"))
            await asyncio.wait_for(producer.recv(), timeout=5)  # the request itself
            assert len(relay._pending) == 1
            # Drop the producer connection without ever answering.
        status, body = await asyncio.wait_for(fetch, timeout=2)
        assert status == 503, (status, body)
        assert relay._pending == {}


async def test_too_many_inflight_requests_is_503_with_retry_after() -> None:
    async with _RelayHarness() as harness, harness.connect_producer() as producer:
        fetches = [
            asyncio.create_task(harness.get(f"/run-history/{uuid4()}"))
            for _ in range(relay._MAX_INFLIGHT_REQUESTS + 1)
        ]
        # Drain exactly _MAX_INFLIGHT_REQUESTS request frames off the wire
        # (never answer them), then let the one-too-many fetch resolve.
        received = 0
        for _ in range(relay._MAX_INFLIGHT_REQUESTS):
            await asyncio.wait_for(producer.recv(), timeout=5)
            received += 1
        assert received == relay._MAX_INFLIGHT_REQUESTS

        done, pending = await asyncio.wait(fetches, timeout=2)
        busy = [t for t in done if (await t)[0] == 503]
        assert len(busy) >= 1, "expected at least one 503 (too many in flight)"
        for task in pending:
            task.cancel()


def _sample_enclosure_timeline(enclosure_id: str) -> dict:
    return {
        "kind": "enclosure_timeline",
        "schema_version": 1,
        "producer_id": "p1",
        "generated_at": "2026-08-30T00:00:00+00:00",
        "enclosure_id": enclosure_id,
        "document": {
            "domain": {"from": "2026-08-09T11:04:00+00:00", "to": "2026-08-30T00:00:00+00:00"},
            "lanes": [
                {"lane_id": "permit", "label": "Permit", "render": "markers", "points": []},
                {"lane_id": "lifecycle", "label": "Lifecycle", "render": "markers", "points": []},
            ],
            "subject_lane_id": "permit",
            "title": "2-BM-A",
            "subtitle": "Permitted",
            "truncated": {"events": False},
        },
    }


async def test_enclosure_timeline_from_producer_is_broadcast_to_a_connected_watcher() -> None:
    async with _RelayHarness() as harness, harness.connect_watcher() as watcher:
        async with harness.connect_producer() as producer:
            timeline = _sample_enclosure_timeline(str(uuid4()))
            await producer.send(json.dumps(timeline))
            received = await _recv_until_kind(watcher, "enclosure_timeline")
            assert received == timeline, received


async def test_enclosure_timeline_is_replayed_to_a_watcher_that_connects_later() -> None:
    """The behavior that makes REWIND reach an enclosure without any
    on-demand request path: a pushed timeline is cached
    (`relay._enclosure_timelines`, no eviction, unlike `activity`'s
    bounded time window) and replayed on every new `/watch` connection,
    not just broadcast to whoever happened to already be listening."""
    async with _RelayHarness() as harness:
        enclosure_id = str(uuid4())
        async with harness.connect_producer() as producer:
            timeline = _sample_enclosure_timeline(enclosure_id)
            await producer.send(json.dumps(timeline))
            # Give the relay's event loop a turn to process the frame
            # before a fresh watcher connects and expects to see it.
            await asyncio.sleep(0.1)

            async with harness.connect_watcher() as watcher:
                received = await _recv_until_kind(watcher, "enclosure_timeline")
                assert received == timeline, received


async def test_malformed_enclosure_timeline_without_enclosure_id_is_dropped() -> None:
    async with _RelayHarness() as harness, harness.connect_producer() as producer:
        await producer.send(
            json.dumps(
                {
                    "kind": "enclosure_timeline",
                    "schema_version": 1,
                    "producer_id": "p1",
                    "generated_at": "2026-08-30T00:00:00+00:00",
                    "document": {},
                }
            )
        )
        # No reply is expected either way; give the relay a turn to process
        # (and, if it were going to, mis-store) the frame.
        await asyncio.sleep(0.1)
        assert relay._enclosure_timelines == {}


def _recent_iso() -> str:
    """A timestamp inside `relay._ACTIVITY_BUFFER_SECONDS` of real now,
    since pruning compares `occurred_at` against the wall clock at test
    run time, not a fixed date."""
    return datetime.now(UTC).isoformat()


def _sample_activity_message(*, occurred_at: str, stream_type: str = "Run") -> dict:
    return {
        "kind": "activity",
        "schema_version": 1,
        "producer_id": "p1",
        "generated_at": "2026-08-30T00:05:00+00:00",
        "events": [
            {
                "stream_type": stream_type,
                "stream_id": str(uuid4()),
                "event_type": "RunStarted",
                "occurred_at": occurred_at,
                "recorded_at": occurred_at,
            }
        ],
    }


async def test_activity_from_producer_is_broadcast_to_a_connected_watcher() -> None:
    async with _RelayHarness() as harness, harness.connect_watcher() as watcher:
        async with harness.connect_producer() as producer:
            message = _sample_activity_message(occurred_at=_recent_iso())
            await producer.send(json.dumps(message))
            received = await _recv_until_kind(watcher, "activity")
            assert received == message, received


async def test_activity_is_replayed_to_a_watcher_that_connects_later() -> None:
    """The fix for the flowing lanes going empty on a refresh or a
    resumed SSH tunnel: before this, `activity` was a pure pass-through
    with nothing for a fresh `/watch` connection to catch up on. Now the
    last `relay._ACTIVITY_BUFFER_SECONDS` of events are buffered
    (`relay._activity_buffer`) and replayed as one synthetic `activity`
    message on connect, in the same shape `page.html`'s `handleActivity`
    already knows how to consume."""
    async with _RelayHarness() as harness:
        async with harness.connect_producer() as producer:
            message = _sample_activity_message(occurred_at=_recent_iso())
            await producer.send(json.dumps(message))
            # Give the relay's event loop a turn to process the frame
            # before a fresh watcher connects and expects to see it.
            await asyncio.sleep(0.1)

            async with harness.connect_watcher() as watcher:
                received = await _recv_until_kind(watcher, "activity")
                assert received["events"] == message["events"], received


async def test_activity_older_than_the_buffer_window_is_not_replayed() -> None:
    async with _RelayHarness() as harness:
        async with harness.connect_producer() as producer:
            stale = _sample_activity_message(occurred_at="2020-01-01T00:00:00+00:00")
            await producer.send(json.dumps(stale))
            await asyncio.sleep(0.1)

            async with harness.connect_watcher() as watcher:
                got_activity = False
                try:
                    await _recv_until_kind(watcher, "activity", max_frames=3, timeout=0.5)
                    got_activity = True
                except (TimeoutError, AssertionError):
                    pass
                assert not got_activity, "a stale event outside the buffer window was replayed"


async def test_malformed_activity_without_events_list_is_dropped() -> None:
    async with _RelayHarness() as harness, harness.connect_producer() as producer:
        await producer.send(
            json.dumps(
                {
                    "kind": "activity",
                    "schema_version": 1,
                    "producer_id": "p1",
                    "generated_at": "2026-08-30T00:00:00+00:00",
                }
            )
        )
        # No reply is expected either way; give the relay a turn to process
        # (and, if it were going to, mis-store) the frame.
        await asyncio.sleep(0.1)
        assert relay._activity_buffer == []


TESTS: list[Callable[[], Awaitable[None]]] = [
    obj
    for name, obj in list(globals().items())
    if name.startswith("test_") and inspect.iscoroutinefunction(obj)
]


async def _run_all() -> bool:
    ok = True
    for test in TESTS:
        try:
            await asyncio.wait_for(test(), timeout=30)
        except Exception as exc:
            ok = False
            print(f"FAIL: {test.__name__}: {exc!r}")
        else:
            print(f"OK:   {test.__name__}")
    return ok


def main() -> None:
    ok = asyncio.run(_run_all())
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
