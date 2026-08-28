"""Tests for the StatusPush runtime (cora.api._status_push).

Covers the pure snapshot builder, the settings validator, the disabled/
unconfigured no-ops, per-domain drain filtering (open vs terminal status),
the Decision tail-follow, and fakes-driven pushes against a real local
WebSocket server (proving the wire format and the connect/reconnect
behavior, not just the unit in isolation).
"""

# white-box test of the runtime internals (private functions / constants)
# pyright: reportPrivateUsage=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from websockets.asyncio.server import ServerConnection, serve

from cora.api._status_push import (
    _DecisionTail,
    _render_progress,
    _render_progress_trail,
    _RunHistoryTail,
    build_run_history_message,
    build_snapshot,
    status_push_lifespan,
)
from cora.campaign.features.list_campaigns import (
    CampaignListPage,
    CampaignSummaryItem,
    ListCampaigns,
)
from cora.data.features.list_datasets import DatasetListPage, DatasetSummaryItem, ListDatasets
from cora.decision.features.list_decisions import (
    DecisionListPage,
    DecisionSummaryItem,
    ListDecisions,
)
from cora.enclosure.features.list_enclosures import (
    EnclosureListPage,
    EnclosureSummaryItem,
    ListEnclosures,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, UUIDv7Generator
from cora.infrastructure.projection import decode_cursor, encode_cursor
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.features.get_run_history import GetRunHistory
from cora.run.features.get_run_history.handler import RunHistoryEvent, RunHistoryView
from cora.run.features.list_runs import ListRuns, RunListPage, RunSummaryItem
from cora.run.features.list_runs.query import RunStatusFilter
from cora.run.ports.capture_observer import CaptureProgressObservation, ReachTier
from cora.safety.features.list_clearances import (
    ClearanceListPage,
    ClearanceSummaryItem,
    ListClearances,
)
from cora.subject.features.list_subjects import ListSubjects, SubjectListPage, SubjectSummaryItem

_NOW = datetime(2026, 6, 22, 12, 0, 0, tzinfo=UTC)


# ---------- pure: build_snapshot ----------


@pytest.mark.unit
def test_build_snapshot_shape() -> None:
    snapshot = build_snapshot(
        runs=[{"run_id": "abc", "name": "n", "status": "Running"}],
        subjects=[],
        campaigns=[],
        datasets=[],
        clearances=[],
        enclosures=[],
        decisions=[],
        sequence=3,
        generated_at="2026-06-22T12:00:00+00:00",
        producer_id="p1",
    )
    assert snapshot == {
        "kind": "snapshot",
        "schema_version": 1,
        "producer_id": "p1",
        "sequence": 3,
        "generated_at": "2026-06-22T12:00:00+00:00",
        "runs": [{"run_id": "abc", "name": "n", "status": "Running"}],
        "subjects": [],
        "campaigns": [],
        "datasets": [],
        "clearances": [],
        "enclosures": [],
        "decisions": [],
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

    def __init__(
        self,
        readings: dict[UUID, dict[str, CaptureProgressObservation]],
        trails: dict[UUID, dict[str, list[CaptureProgressObservation]]] | None = None,
    ) -> None:
        self._readings = readings
        self._trails = trails or {}

    def progress_readings(self) -> dict[UUID, dict[str, CaptureProgressObservation]]:
        return self._readings

    def progress_trails(self) -> dict[UUID, dict[str, list[CaptureProgressObservation]]]:
        return self._trails


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


# ---------- pure: _render_progress_trail ----------


@pytest.mark.unit
def test_render_progress_trail_is_empty_when_recorder_is_none() -> None:
    assert _render_progress_trail(uuid4(), None) == {}


@pytest.mark.unit
def test_render_progress_trail_is_empty_when_run_has_no_trail() -> None:
    recorder = _FakeWitnessRecorder({}, {})
    assert _render_progress_trail(uuid4(), recorder) == {}  # type: ignore[arg-type]


@pytest.mark.unit
def test_render_progress_trail_renders_each_role_json_safe_oldest_first() -> None:
    run_id = uuid4()
    first = _obs(value=1.0, commanded_total=100.0, observed_at=_NOW)
    second = _obs(value=2.0, commanded_total=100.0, observed_at=_NOW + timedelta(seconds=1))
    recorder = _FakeWitnessRecorder({}, {run_id: {"images_saved": [first, second]}})

    rendered = _render_progress_trail(run_id, recorder)  # type: ignore[arg-type]

    assert rendered == {
        "images_saved": [
            {"value": 1.0, "commanded_total": 100.0, "observed_at": _NOW.isoformat()},
            {
                "value": 2.0,
                "commanded_total": 100.0,
                "observed_at": (_NOW + timedelta(seconds=1)).isoformat(),
            },
        ]
    }


@pytest.mark.unit
def test_render_progress_trail_tail_slices_independent_of_recorder_retention() -> None:
    run_id = uuid4()
    long_trail = [_obs(value=float(i), commanded_total=None, observed_at=_NOW) for i in range(40)]
    recorder = _FakeWitnessRecorder({}, {run_id: {"images_saved": long_trail}})

    rendered = _render_progress_trail(run_id, recorder)  # type: ignore[arg-type]

    assert len(rendered["images_saved"]) == 30
    assert rendered["images_saved"][0]["value"] == 10.0
    assert rendered["images_saved"][-1]["value"] == 39.0


# ---------- fakes: one empty-by-default handler per domain ----------


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


def _make_list_subjects(items: list[SubjectSummaryItem]):
    async def list_subjects(
        query: ListSubjects,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> SubjectListPage:
        matching = [i for i in items if query.status is None or i.status == query.status]
        return SubjectListPage(items=matching, next_cursor=None)

    return list_subjects


def _make_list_campaigns(items: list[CampaignSummaryItem]):
    async def list_campaigns(
        query: ListCampaigns,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> CampaignListPage:
        matching = [i for i in items if not query.statuses or i.status in query.statuses]
        return CampaignListPage(items=matching, next_cursor=None)

    return list_campaigns


def _make_list_datasets(items: list[DatasetSummaryItem]):
    async def list_datasets(
        query: ListDatasets,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> DatasetListPage:
        matching = [
            i
            for i in items
            if query.producing_run_id is None or i.producing_run_id == query.producing_run_id
        ]
        return DatasetListPage(items=matching, next_cursor=None)

    return list_datasets


def _make_list_clearances(items: list[ClearanceSummaryItem]):
    async def list_clearances(
        query: ListClearances,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ClearanceListPage:
        matching = [i for i in items if query.status is None or i.status == query.status]
        return ClearanceListPage(items=matching, next_cursor=None)

    return list_clearances


def _make_list_enclosures(items: list[EnclosureSummaryItem]):
    async def list_enclosures(
        query: ListEnclosures,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> EnclosureListPage:
        matching = [i for i in items if query.lifecycle is None or i.lifecycle == query.lifecycle]
        return EnclosureListPage(items=matching, next_cursor=None)

    return list_enclosures


def _make_list_decisions(items: list[DecisionSummaryItem]):
    async def list_decisions(
        query: ListDecisions,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> DecisionListPage:
        # Honor the keyset cursor for real: _DecisionTail's "starts empty"
        # guarantee depends on items at-or-before the starting cursor being
        # excluded, and a fake that ignored the cursor could not catch a
        # regression there.
        if query.cursor is None:
            matching = list(items)
        else:
            cursor_at, cursor_id = decode_cursor(query.cursor)
            matching = [i for i in items if (i.created_at, i.decision_id) > (cursor_at, cursor_id)]
        return DecisionListPage(items=matching, next_cursor=None)

    return list_decisions


def _make_get_run_history(views: dict[UUID, RunHistoryView] | None = None):
    views = views or {}

    async def get_run_history(
        query: GetRunHistory,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunHistoryView | None:
        return views.get(query.run_id)

    return get_run_history


def _default_handlers(**overrides: Any) -> dict[str, Any]:
    """Empty-by-default fakes for every domain `status_push_lifespan` needs,
    so a test overriding one domain doesn't have to spell out the other six.
    `get_run_history` defaults to always returning `None`, so the default
    fixture never emits a run-history message -- tests exercising REWIND
    mode pass an explicit `views` mapping via `_make_get_run_history`."""
    defaults: dict[str, Any] = {
        "list_runs": _make_list_runs([]),
        "list_subjects": _make_list_subjects([]),
        "list_campaigns": _make_list_campaigns([]),
        "list_datasets": _make_list_datasets([]),
        "list_clearances": _make_list_clearances([]),
        "list_enclosures": _make_list_enclosures([]),
        "list_decisions": _make_list_decisions([]),
        "get_run_history": _make_get_run_history(),
    }
    defaults.update(overrides)
    return defaults


# ---------- lifespan no-ops ----------


@pytest.mark.unit
async def test_lifespan_is_noop_when_disabled() -> None:
    kernel = _kernel(status_push_enabled=False)
    async with status_push_lifespan(kernel, **_default_handlers()):
        pass  # spawning no task and returning cleanly is the assertion


@pytest.mark.unit
async def test_lifespan_is_noop_when_enabled_but_no_url_configured() -> None:
    kernel = _kernel(status_push_enabled=True, status_push_url=None)
    async with status_push_lifespan(kernel, **_default_handlers()):
        pass


# ---------- Decision tail-follow ----------


@pytest.mark.unit
async def test_decision_tail_starts_empty_even_with_existing_decisions() -> None:
    """The ring starts at "now", not at the beginning of history: an
    existing Decision predating construction must never appear."""
    existing = DecisionSummaryItem(
        decision_id=uuid4(),
        decided_by=uuid4(),
        rule="agent:RunDebriefer:v1",
        parent_id=None,
        confidence=None,
        confidence_band=None,
        choice="NominalCompletion",
        created_at=_NOW - timedelta(minutes=1),
    )
    list_decisions = _make_list_decisions([existing])
    kernel = _kernel()
    tail = _DecisionTail(started_at_cursor=encode_cursor(created_at=_NOW, item_id=UUID(int=0)))

    result = await tail.poll(list_decisions, kernel)

    assert result == []


@pytest.mark.unit
async def test_decision_tail_returns_a_freshly_published_row() -> None:
    """A fresh fake returning items regardless of cursor stands in for
    "a new Decision landed since last poll"; the tail must surface it."""
    fresh = DecisionSummaryItem(
        decision_id=uuid4(),
        decided_by=uuid4(),
        rule="agent:RunDebriefer:v1",
        parent_id=None,
        confidence=0.9,
        confidence_band="High",
        choice="NominalCompletion",
        created_at=_NOW,
    )
    list_decisions = _make_list_decisions([fresh])
    kernel = _kernel()
    tail = _DecisionTail(started_at_cursor=encode_cursor(created_at=_NOW, item_id=UUID(int=0)))

    result = await tail.poll(list_decisions, kernel)

    assert len(result) == 1
    assert result[0]["decision_id"] == str(fresh.decision_id)
    assert result[0]["choice"] == "NominalCompletion"
    assert result[0]["confidence_band"] == "High"


@pytest.mark.unit
async def test_decision_tail_caps_at_the_ring_size() -> None:
    items = [
        DecisionSummaryItem(
            decision_id=uuid4(),
            decided_by=uuid4(),
            rule=None,
            parent_id=None,
            confidence=None,
            confidence_band=None,
            choice="NominalCompletion",
            created_at=_NOW,
        )
        for _ in range(25)
    ]
    list_decisions = _make_list_decisions(items)
    kernel = _kernel()
    tail = _DecisionTail(started_at_cursor=encode_cursor(created_at=_NOW, item_id=UUID(int=0)))

    result = await tail.poll(list_decisions, kernel)

    assert len(result) == 20


# ---------- pure: build_run_history_message ----------


def _history_view(run_id: UUID, *, event_count: int = 1) -> RunHistoryView:
    return RunHistoryView(
        run_id=run_id,
        name="32-ID FlyScan",
        status="Running",
        events=[
            RunHistoryEvent(
                event_id=uuid4(),
                event_type="RunStarted",
                version=i + 1,
                occurred_at=_NOW + timedelta(seconds=i),
                recorded_at=_NOW + timedelta(seconds=i),
                payload={},
            )
            for i in range(event_count)
        ],
        observations=[],
        observations_truncated=False,
    )


@pytest.mark.unit
def test_build_run_history_message_shape() -> None:
    run_id = uuid4()
    view = _history_view(run_id)

    message = build_run_history_message(
        view=view,
        terminal=True,
        generated_at="2026-06-22T12:00:00+00:00",
        producer_id="p1",
    )

    assert message == {
        "kind": "run_history",
        "schema_version": 1,
        "producer_id": "p1",
        "generated_at": "2026-06-22T12:00:00+00:00",
        "run_id": str(run_id),
        "name": "32-ID FlyScan",
        "status": "Running",
        "terminal": True,
        "events": [
            {
                "event_type": "RunStarted",
                "occurred_at": _NOW.isoformat(),
                "recorded_at": _NOW.isoformat(),
                "payload": {},
            }
        ],
        "observations": [],
        "observations_truncated": False,
    }


# ---------- _RunHistoryTail ----------


@pytest.mark.unit
async def test_run_history_tail_emits_on_first_sight_of_an_open_run() -> None:
    run_id = uuid4()
    get_run_history = _make_get_run_history({run_id: _history_view(run_id)})
    tail = _RunHistoryTail()
    kernel = _kernel()

    messages = await tail.poll(
        get_run_history,
        kernel,
        open_run_ids=[run_id],
        generated_at="t0",
        producer_id="p1",
    )

    assert len(messages) == 1
    assert messages[0]["run_id"] == str(run_id)
    assert messages[0]["terminal"] is False


@pytest.mark.unit
async def test_run_history_tail_emits_nothing_between_refreshes() -> None:
    run_id = uuid4()
    get_run_history = _make_get_run_history({run_id: _history_view(run_id)})
    tail = _RunHistoryTail()
    kernel = _kernel()

    await tail.poll(
        get_run_history, kernel, open_run_ids=[run_id], generated_at="t0", producer_id="p1"
    )
    second = await tail.poll(
        get_run_history, kernel, open_run_ids=[run_id], generated_at="t1", producer_id="p1"
    )

    assert second == []


@pytest.mark.unit
async def test_run_history_tail_emits_terminal_true_when_a_run_leaves_the_open_set() -> None:
    run_id = uuid4()
    get_run_history = _make_get_run_history({run_id: _history_view(run_id)})
    tail = _RunHistoryTail()
    kernel = _kernel()

    await tail.poll(
        get_run_history, kernel, open_run_ids=[run_id], generated_at="t0", producer_id="p1"
    )
    closed = await tail.poll(
        get_run_history, kernel, open_run_ids=[], generated_at="t1", producer_id="p1"
    )

    assert len(closed) == 1
    assert closed[0]["run_id"] == str(run_id)
    assert closed[0]["terminal"] is True


@pytest.mark.unit
async def test_run_history_tail_ring_evicts_past_the_cap() -> None:
    run_ids = [uuid4() for _ in range(25)]
    views = {run_id: _history_view(run_id) for run_id in run_ids}
    get_run_history = _make_get_run_history(views)
    tail = _RunHistoryTail()
    kernel = _kernel()

    for run_id in run_ids:
        await tail.poll(
            get_run_history, kernel, open_run_ids=[run_id], generated_at="t", producer_id="p1"
        )

    assert len(tail._ring) == 20


@pytest.mark.unit
async def test_run_history_tail_on_reconnect_repushes_a_still_open_run_promptly() -> None:
    run_id = uuid4()
    get_run_history = _make_get_run_history({run_id: _history_view(run_id)})
    tail = _RunHistoryTail()
    kernel = _kernel()

    await tail.poll(
        get_run_history, kernel, open_run_ids=[run_id], generated_at="t0", producer_id="p1"
    )
    tail.on_reconnect()
    after_reconnect = await tail.poll(
        get_run_history, kernel, open_run_ids=[run_id], generated_at="t1", producer_id="p1"
    )

    assert len(after_reconnect) == 1


# ---------- real socket: push against a local WebSocket server ----------


def _run_item(
    run_id: UUID, *, name: str = "smoke-run", status: RunStatusFilter = "Running"
) -> RunSummaryItem:
    return RunSummaryItem(
        run_id=run_id,
        name=name,
        plan_id=uuid4(),
        subject_id=None,
        raid=None,
        status=status,
        created_at=_NOW,
        running_since=_NOW,
        override_parameters_present=False,
        campaign_id=None,
        snr_limit=None,
        expected_observation_interval_seconds=None,
        conduct_mode="Witnessed",
        capture_code=None,
    )


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

        async with status_push_lifespan(
            kernel, **_default_handlers(list_runs=_make_list_runs([_run_item(run_id)]))
        ):
            raw = await asyncio.wait_for(received.get(), timeout=5)

        snapshot = json.loads(raw)
        assert snapshot["schema_version"] == 1
        assert snapshot["runs"] == [
            {
                "run_id": str(run_id),
                "name": "smoke-run",
                "status": "Running",
                "progress": {},
                "progress_trail": {},
            }
        ]
        assert snapshot["subjects"] == []
        assert snapshot["decisions"] == []


@pytest.mark.unit
async def test_lifespan_pushes_both_a_snapshot_and_a_run_history_message() -> None:
    """REWIND mode's end-to-end path: an open run's full history arrives
    on the same socket as the live snapshot, as its own message kind."""
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

        async with status_push_lifespan(
            kernel,
            **_default_handlers(
                list_runs=_make_list_runs([_run_item(run_id)]),
                get_run_history=_make_get_run_history({run_id: _history_view(run_id)}),
            ),
        ):
            first = json.loads(await asyncio.wait_for(received.get(), timeout=5))
            second = json.loads(await asyncio.wait_for(received.get(), timeout=5))

        kinds = {first["kind"], second["kind"]}
        assert kinds == {"run_history", "snapshot"}
        history = first if first["kind"] == "run_history" else second
        assert history["run_id"] == str(run_id)
        assert history["terminal"] is False
        assert history["events"][0]["event_type"] == "RunStarted"


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
        witness_recorder = _FakeWitnessRecorder(
            {run_id: {"images_saved": _obs(value=42.0, commanded_total=100.0, observed_at=_NOW)}}
        )

        async with status_push_lifespan(
            kernel,
            **_default_handlers(list_runs=_make_list_runs([_run_item(run_id)])),
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
async def test_lifespan_pushes_open_subjects_and_drops_terminal_ones() -> None:
    received: asyncio.Queue[str] = asyncio.Queue()

    async def handler(ws: ServerConnection) -> None:
        async for message in ws:
            await received.put(message if isinstance(message, str) else message.decode())

    async with serve(handler, "127.0.0.1", 0) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        url = f"ws://127.0.0.1:{port}/ingest"
        kernel = _kernel(
            status_push_enabled=True, status_push_url=url, status_push_tick_seconds=0.1
        )
        open_subject = SubjectSummaryItem(
            subject_id=uuid4(), name="sandstone-core", status="Mounted", created_at=_NOW
        )
        terminal_subject = SubjectSummaryItem(
            subject_id=uuid4(), name="already-returned", status="Returned", created_at=_NOW
        )

        async with status_push_lifespan(
            kernel,
            **_default_handlers(
                list_subjects=_make_list_subjects([open_subject, terminal_subject])
            ),
        ):
            raw = await asyncio.wait_for(received.get(), timeout=5)

        snapshot = json.loads(raw)
        assert len(snapshot["subjects"]) == 1
        assert snapshot["subjects"][0]["name"] == "sandstone-core"


@pytest.mark.unit
async def test_lifespan_pushes_datasets_only_for_onscreen_runs() -> None:
    received: asyncio.Queue[str] = asyncio.Queue()

    async def handler(ws: ServerConnection) -> None:
        async for message in ws:
            await received.put(message if isinstance(message, str) else message.decode())

    async with serve(handler, "127.0.0.1", 0) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        url = f"ws://127.0.0.1:{port}/ingest"
        kernel = _kernel(
            status_push_enabled=True, status_push_url=url, status_push_tick_seconds=0.1
        )
        onscreen_run_id = uuid4()
        offscreen_run_id = uuid4()
        onscreen_dataset = DatasetSummaryItem(
            dataset_id=uuid4(),
            name="onscreen-ds",
            uri="s3://bucket/onscreen",
            producing_run_id=onscreen_run_id,
            subject_id=None,
            status="Registered",
            created_at=_NOW,
        )
        offscreen_dataset = DatasetSummaryItem(
            dataset_id=uuid4(),
            name="offscreen-ds",
            uri="s3://bucket/offscreen",
            producing_run_id=offscreen_run_id,
            subject_id=None,
            status="Registered",
            created_at=_NOW,
        )

        async with status_push_lifespan(
            kernel,
            **_default_handlers(
                list_runs=_make_list_runs([_run_item(onscreen_run_id)]),
                list_datasets=_make_list_datasets([onscreen_dataset, offscreen_dataset]),
            ),
        ):
            raw = await asyncio.wait_for(received.get(), timeout=5)

        snapshot = json.loads(raw)
        assert [d["name"] for d in snapshot["datasets"]] == ["onscreen-ds"]


@pytest.mark.unit
async def test_lifespan_pushes_active_clearances_only() -> None:
    received: asyncio.Queue[str] = asyncio.Queue()

    async def handler(ws: ServerConnection) -> None:
        async for message in ws:
            await received.put(message if isinstance(message, str) else message.decode())

    async with serve(handler, "127.0.0.1", 0) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        url = f"ws://127.0.0.1:{port}/ingest"
        kernel = _kernel(
            status_push_enabled=True, status_push_url=url, status_push_tick_seconds=0.1
        )
        active = ClearanceSummaryItem(
            clearance_id=uuid4(),
            template_id=uuid4(),
            template_code="ESAF",
            facility_code="cora",
            title="Active ESAF",
            external_id=None,
            status="Active",
            risk_band="Yellow",
            subject_binding_ids=[],
            asset_binding_ids=[],
            run_binding_ids=[],
            procedure_binding_ids=[],
            parent_id=None,
            registered_at=_NOW,
            last_status_changed_at=None,
            last_status_reason=None,
            last_reviewed_by=None,
            valid_from=None,
            valid_until=None,
            next_review_due_at=None,
        )
        expired = ClearanceSummaryItem(
            clearance_id=uuid4(),
            template_id=uuid4(),
            template_code="ESAF",
            facility_code="cora",
            title="Expired ESAF",
            external_id=None,
            status="Expired",
            risk_band="Yellow",
            subject_binding_ids=[],
            asset_binding_ids=[],
            run_binding_ids=[],
            procedure_binding_ids=[],
            parent_id=None,
            registered_at=_NOW,
            last_status_changed_at=None,
            last_status_reason=None,
            last_reviewed_by=None,
            valid_from=None,
            valid_until=None,
            next_review_due_at=None,
        )

        async with status_push_lifespan(
            kernel, **_default_handlers(list_clearances=_make_list_clearances([active, expired]))
        ):
            raw = await asyncio.wait_for(received.get(), timeout=5)

        snapshot = json.loads(raw)
        assert len(snapshot["clearances"]) == 1
        assert snapshot["clearances"][0]["template_code"] == "ESAF"


@pytest.mark.unit
async def test_lifespan_pushes_active_enclosures_only() -> None:
    received: asyncio.Queue[str] = asyncio.Queue()

    async def handler(ws: ServerConnection) -> None:
        async for message in ws:
            await received.put(message if isinstance(message, str) else message.decode())

    async with serve(handler, "127.0.0.1", 0) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        url = f"ws://127.0.0.1:{port}/ingest"
        kernel = _kernel(
            status_push_enabled=True, status_push_url=url, status_push_tick_seconds=0.1
        )
        active = EnclosureSummaryItem(
            enclosure_id=uuid4(),
            name="2-BM-B",
            facility_code="cora",
            lifecycle="Active",
            permit_status="Permitted",
            registered_at=_NOW,
            registered_by=uuid4(),
            last_permit_status_changed_at=None,
            last_permit_status_reason=None,
            last_trigger=None,
            last_source_kind=None,
            last_source_id=None,
            last_source_observed_at=None,
            decommissioned_at=None,
            decommissioned_by=None,
        )
        decommissioned = EnclosureSummaryItem(
            enclosure_id=uuid4(),
            name="old-hutch",
            facility_code="cora",
            lifecycle="Decommissioned",
            permit_status="Unknown",
            registered_at=_NOW,
            registered_by=uuid4(),
            last_permit_status_changed_at=None,
            last_permit_status_reason=None,
            last_trigger=None,
            last_source_kind=None,
            last_source_id=None,
            last_source_observed_at=None,
            decommissioned_at=_NOW,
            decommissioned_by=uuid4(),
        )

        async with status_push_lifespan(
            kernel,
            **_default_handlers(list_enclosures=_make_list_enclosures([active, decommissioned])),
        ):
            raw = await asyncio.wait_for(received.get(), timeout=5)

        snapshot = json.loads(raw)
        assert len(snapshot["enclosures"]) == 1
        assert snapshot["enclosures"][0]["name"] == "2-BM-B"


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

    async with status_push_lifespan(kernel, **_default_handlers()):
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
