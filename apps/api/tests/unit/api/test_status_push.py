"""Tests for the StatusPush runtime (cora.api._status_push).

Covers the pure snapshot builder, the settings validator, the disabled/
unconfigured no-ops, and a fakes-driven push against a real local
WebSocket server (proving the wire format and the connect/reconnect
behavior, not just the unit in isolation).
"""

# white-box test of the runtime internals (private functions / constants)
# pyright: reportPrivateUsage=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from websockets.asyncio.server import ServerConnection, serve

from cora.api._status_push import _render_progress, build_snapshot, status_push_lifespan
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, UUIDv7Generator
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.features.list_runs import ListRuns, RunListPage, RunSummaryItem
from cora.run.ports.capture_observer import CaptureProgressObservation, ReachTier

_NOW = datetime(2026, 6, 22, 12, 0, 0, tzinfo=UTC)


# ---------- pure: build_snapshot ----------


@pytest.mark.unit
def test_build_snapshot_shape() -> None:
    snapshot = build_snapshot(
        runs=[{"run_id": "abc", "name": "n", "status": "Running"}],
        sequence=3,
        generated_at="2026-06-22T12:00:00+00:00",
        producer_id="p1",
    )
    assert snapshot == {
        "schema_version": 1,
        "producer_id": "p1",
        "sequence": 3,
        "generated_at": "2026-06-22T12:00:00+00:00",
        "runs": [{"run_id": "abc", "name": "n", "status": "Running"}],
    }


# ---------- settings validator ----------


@pytest.mark.unit
def test_status_push_tick_seconds_rejects_sub_floor() -> None:
    with pytest.raises(ValueError, match="status_push_tick_seconds"):
        Settings(status_push_tick_seconds=0.05)  # type: ignore[call-arg]


@pytest.mark.unit
def test_status_push_settings_accept_valid() -> None:
    settings = Settings(  # type: ignore[call-arg]
        status_push_enabled=True,
        status_push_tick_seconds=1.0,
        status_push_url="ws://127.0.0.1:9/ingest",
    )
    assert settings.status_push_tick_seconds == 1.0
    assert settings.status_push_url == "ws://127.0.0.1:9/ingest"


# ---------- pure: _render_progress ----------


class _FakeWitnessRecorder:
    """Duck-types `RunWitnessRecorder`'s read-only surface for these tests."""

    def __init__(self, readings: dict[UUID, dict[str, CaptureProgressObservation]]) -> None:
        self._readings = readings

    def progress_readings(self) -> dict[UUID, dict[str, CaptureProgressObservation]]:
        return self._readings


def _obs(
    *, value: float, commanded_total: float | None, observed_at: datetime | None
) -> CaptureProgressObservation:
    return CaptureProgressObservation(
        capture_code="c1",
        role="images_saved",
        value=value,
        commanded_total=commanded_total,
        reach_tier=ReachTier.RELAYED,
        observed_at=observed_at,
        source_kind="EpicsPv",
        source_id="2bmb:TomoScan:ImagesSaved",
    )


@pytest.mark.unit
def test_render_progress_is_empty_when_recorder_is_none() -> None:
    assert _render_progress(uuid4(), None) == {}


@pytest.mark.unit
def test_render_progress_is_empty_when_run_has_no_readings() -> None:
    recorder = _FakeWitnessRecorder({})
    assert _render_progress(uuid4(), recorder) == {}  # type: ignore[arg-type]


@pytest.mark.unit
def test_render_progress_renders_each_role_json_safe() -> None:
    run_id = uuid4()
    recorder = _FakeWitnessRecorder(
        {run_id: {"images_saved": _obs(value=810.0, commanded_total=1500.0, observed_at=_NOW)}}
    )

    rendered = _render_progress(run_id, recorder)  # type: ignore[arg-type]

    assert rendered == {
        "images_saved": {
            "value": 810.0,
            "commanded_total": 1500.0,
            "observed_at": _NOW.isoformat(),
        }
    }


@pytest.mark.unit
def test_render_progress_renders_a_missing_observed_at_as_none() -> None:
    """2-BM's real case: the substrate reports no time for this reading."""
    run_id = uuid4()
    recorder = _FakeWitnessRecorder(
        {run_id: {"images_saved": _obs(value=3.0, commanded_total=None, observed_at=None)}}
    )

    rendered = _render_progress(run_id, recorder)  # type: ignore[arg-type]

    assert rendered["images_saved"]["observed_at"] is None
    assert rendered["images_saved"]["commanded_total"] is None


# ---------- lifespan no-ops ----------


def _kernel(**settings_kwargs: object) -> Kernel:
    settings = Settings(**settings_kwargs)  # type: ignore[arg-type]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(_NOW),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
    )


def _make_list_runs(items: list[RunSummaryItem]):
    async def list_runs(
        query: ListRuns,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunListPage:
        # Honor the status filter, matching the real handler: _status_push
        # drains "Running" then "Held" as two separate calls, and a fake
        # that ignored the filter would double-count every run.
        matching = [i for i in items if query.status is None or i.status == query.status]
        return RunListPage(items=matching, next_cursor=None)

    return list_runs


@pytest.mark.unit
async def test_lifespan_is_noop_when_disabled() -> None:
    kernel = _kernel(status_push_enabled=False)
    async with status_push_lifespan(kernel, list_runs=_make_list_runs([])):
        pass  # spawning no task and returning cleanly is the assertion


@pytest.mark.unit
async def test_lifespan_is_noop_when_enabled_but_no_url_configured() -> None:
    kernel = _kernel(status_push_enabled=True, status_push_url=None)
    async with status_push_lifespan(kernel, list_runs=_make_list_runs([])):
        pass


# ---------- real socket: push against a local WebSocket server ----------


@pytest.mark.unit
async def test_lifespan_pushes_a_snapshot_to_a_real_relay() -> None:
    """Boots a tiny local WebSocket server standing in for the relay's
    `/ingest` endpoint, enables StatusPush against it, and asserts the
    first pushed message decodes to the expected run row."""
    received: asyncio.Queue[str] = asyncio.Queue()

    async def handler(ws: ServerConnection) -> None:
        async for message in ws:
            await received.put(message if isinstance(message, str) else message.decode())

    async with serve(handler, "127.0.0.1", 0) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        url = f"ws://127.0.0.1:{port}/ingest"
        kernel = _kernel(
            status_push_enabled=True,
            status_push_url=url,
            status_push_tick_seconds=0.1,
        )
        run_id = uuid4()
        list_runs = _make_list_runs(
            [
                RunSummaryItem(
                    run_id=run_id,
                    name="smoke-run",
                    plan_id=uuid4(),
                    subject_id=None,
                    raid=None,
                    status="Running",
                    created_at=_NOW,
                    running_since=_NOW,
                    override_parameters_present=False,
                    campaign_id=None,
                    snr_limit=None,
                    expected_observation_interval_seconds=None,
                    conduct_mode="Witnessed",
                    capture_code=None,
                )
            ]
        )

        async with status_push_lifespan(kernel, list_runs=list_runs):
            raw = await asyncio.wait_for(received.get(), timeout=5)

        snapshot = json.loads(raw)
        assert snapshot["schema_version"] == 1
        assert snapshot["runs"] == [
            {"run_id": str(run_id), "name": "smoke-run", "status": "Running", "progress": {}}
        ]


@pytest.mark.unit
async def test_lifespan_includes_witness_recorder_progress_in_the_pushed_snapshot() -> None:
    """The end-to-end path from a `RunWitnessRecorder` reading to the wire."""
    received: asyncio.Queue[str] = asyncio.Queue()

    async def handler(ws: ServerConnection) -> None:
        async for message in ws:
            await received.put(message if isinstance(message, str) else message.decode())

    async with serve(handler, "127.0.0.1", 0) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        url = f"ws://127.0.0.1:{port}/ingest"
        kernel = _kernel(
            status_push_enabled=True,
            status_push_url=url,
            status_push_tick_seconds=0.1,
        )
        run_id = uuid4()
        list_runs = _make_list_runs(
            [
                RunSummaryItem(
                    run_id=run_id,
                    name="smoke-run",
                    plan_id=uuid4(),
                    subject_id=None,
                    raid=None,
                    status="Running",
                    created_at=_NOW,
                    running_since=_NOW,
                    override_parameters_present=False,
                    campaign_id=None,
                    snr_limit=None,
                    expected_observation_interval_seconds=None,
                    conduct_mode="Witnessed",
                    capture_code=None,
                )
            ]
        )
        witness_recorder = _FakeWitnessRecorder(
            {run_id: {"images_saved": _obs(value=42.0, commanded_total=100.0, observed_at=_NOW)}}
        )

        async with status_push_lifespan(
            kernel,
            list_runs=list_runs,
            witness_recorder=witness_recorder,  # type: ignore[arg-type]
        ):
            raw = await asyncio.wait_for(received.get(), timeout=5)

        snapshot = json.loads(raw)
        assert snapshot["runs"][0]["progress"] == {
            "images_saved": {
                "value": 42.0,
                "commanded_total": 100.0,
                "observed_at": _NOW.isoformat(),
            }
        }


@pytest.mark.unit
async def test_lifespan_reconnects_after_the_relay_drops(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kill the relay mid-stream, then bring a new one up on the same port;
    the producer must resume pushing without being restarted itself."""
    monkeypatch.setattr("cora.api._status_push._RECONNECT_INITIAL_SECONDS", 0.02, raising=False)
    received: asyncio.Queue[str] = asyncio.Queue()

    async def handler(ws: ServerConnection) -> None:
        async for message in ws:
            await received.put(message if isinstance(message, str) else message.decode())

    server = await serve(handler, "127.0.0.1", 0)
    port = next(iter(server.sockets)).getsockname()[1]
    url = f"ws://127.0.0.1:{port}/ingest"
    kernel = _kernel(
        status_push_enabled=True,
        status_push_url=url,
        status_push_tick_seconds=0.1,
    )
    list_runs = _make_list_runs([])

    async with status_push_lifespan(kernel, list_runs=list_runs):
        await asyncio.wait_for(received.get(), timeout=5)

        server.close()
        await server.wait_closed()
        # Drain the queue so the next item we see is genuinely post-restart.
        while not received.empty():
            received.get_nowait()

        server = await serve(handler, "127.0.0.1", port)
        await asyncio.wait_for(received.get(), timeout=10)

    server.close()
    await server.wait_closed()
