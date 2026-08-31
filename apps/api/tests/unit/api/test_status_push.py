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
    _ActivityTail,
    _answer_request,
    _DecisionTail,
    _EnclosureTimelineTail,
    _Inbound,
    _parse_inbound,
    _render_progress,
    _render_progress_trail,
    _RunHistoryTail,
    build_activity_message,
    build_enclosure_timeline_message,
    build_run_history_message,
    build_run_history_response,
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
from cora.enclosure.features.get_enclosure_history import GetEnclosureHistory
from cora.enclosure.features.get_enclosure_history.handler import (
    EnclosureHistoryEvent,
    EnclosureHistoryView,
)
from cora.enclosure.features.list_enclosures import (
    EnclosureListPage,
    EnclosureSummaryItem,
    ListEnclosures,
)
from cora.infrastructure.adapters.in_memory_event_activity_trail import (
    InMemoryEventActivityTrail,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, UUIDv7Generator
from cora.infrastructure.ports.event_activity_trail import EventActivityRow
from cora.infrastructure.ports.event_store import NewEvent
from cora.infrastructure.projection import decode_cursor, encode_cursor
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.errors import UnauthorizedError as RunUnauthorizedError
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


@pytest.mark.unit
def test_status_push_request_max_per_tick_rejects_above_the_cap() -> None:
    with pytest.raises(ValueError, match="status_push_request_max_per_tick"):
        Settings(status_push_request_max_per_tick=9)  # type: ignore[call-arg]


@pytest.mark.unit
def test_status_push_request_max_per_tick_rejects_negative() -> None:
    with pytest.raises(ValueError, match="status_push_request_max_per_tick"):
        Settings(status_push_request_max_per_tick=-1)  # type: ignore[call-arg]


@pytest.mark.unit
def test_status_push_request_max_per_tick_accepts_the_disabling_zero() -> None:
    settings = Settings(status_push_request_max_per_tick=0)  # type: ignore[call-arg]
    assert settings.status_push_request_max_per_tick == 0


@pytest.mark.unit
def test_status_push_request_max_per_tick_accepts_the_upper_bound() -> None:
    settings = Settings(status_push_request_max_per_tick=8)  # type: ignore[call-arg]
    assert settings.status_push_request_max_per_tick == 8


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


def _kernel(*, event_store: InMemoryEventStore | None = None, **settings_kwargs: object) -> Kernel:
    settings = Settings(**settings_kwargs)  # type: ignore[arg-type]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(_NOW),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
        event_store=event_store,
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


def _make_get_enclosure_history(views: dict[UUID, EnclosureHistoryView] | None = None):
    views = views or {}

    async def get_enclosure_history(
        query: GetEnclosureHistory,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> EnclosureHistoryView | None:
        return views.get(query.enclosure_id)

    return get_enclosure_history


def _default_handlers(**overrides: Any) -> dict[str, Any]:
    """Empty-by-default fakes for every domain `status_push_lifespan` needs,
    so a test overriding one domain doesn't have to spell out the other six.
    `get_run_history` and `get_enclosure_history` both default to always
    returning `None`, so the default fixture never emits a run-history or
    enclosure-timeline message -- tests exercising REWIND mode pass an
    explicit `views` mapping via `_make_get_run_history` /
    `_make_get_enclosure_history`."""
    defaults: dict[str, Any] = {
        "list_runs": _make_list_runs([]),
        "list_subjects": _make_list_subjects([]),
        "list_campaigns": _make_list_campaigns([]),
        "list_datasets": _make_list_datasets([]),
        "list_clearances": _make_list_clearances([]),
        "list_enclosures": _make_list_enclosures([]),
        "list_decisions": _make_list_decisions([]),
        "get_run_history": _make_get_run_history(),
        "get_enclosure_history": _make_get_enclosure_history(),
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
async def test_cached_terminal_is_none_for_a_run_never_seen() -> None:
    assert _RunHistoryTail().cached_terminal(uuid4()) is None


@pytest.mark.unit
async def test_cached_terminal_is_none_while_a_run_is_still_open() -> None:
    run_id = uuid4()
    get_run_history = _make_get_run_history({run_id: _history_view(run_id)})
    tail = _RunHistoryTail()
    kernel = _kernel()

    await tail.poll(
        get_run_history, kernel, open_run_ids=[run_id], generated_at="t0", producer_id="p1"
    )

    assert tail.cached_terminal(run_id) is None


@pytest.mark.unit
async def test_cached_terminal_returns_the_message_once_a_run_closes() -> None:
    run_id = uuid4()
    get_run_history = _make_get_run_history({run_id: _history_view(run_id)})
    tail = _RunHistoryTail()
    kernel = _kernel()

    await tail.poll(
        get_run_history, kernel, open_run_ids=[run_id], generated_at="t0", producer_id="p1"
    )
    await tail.poll(get_run_history, kernel, open_run_ids=[], generated_at="t1", producer_id="p1")

    cached = tail.cached_terminal(run_id)
    assert cached is not None
    assert cached["run_id"] == str(run_id)
    assert cached["terminal"] is True


# ---------- pure: build_enclosure_timeline_message ----------


def _enclosure_history_view(
    enclosure_id: UUID,
    *,
    name: str = "2-BM-A",
    permit_status: str = "Permitted",
    lifecycle: str = "Active",
    events: list[EnclosureHistoryEvent] | None = None,
    events_truncated: bool = False,
) -> EnclosureHistoryView:
    if events is None:
        events = [
            EnclosureHistoryEvent(
                event_id=uuid4(),
                event_type="EnclosureRegistered",
                version=1,
                occurred_at=_NOW,
                recorded_at=_NOW,
                payload={"enclosure_id": str(enclosure_id), "name": name},
            )
        ]
    return EnclosureHistoryView(
        enclosure_id=enclosure_id,
        name=name,
        permit_status=permit_status,
        lifecycle=lifecycle,
        events=events,
        events_truncated=events_truncated,
    )


def _permit_observed_event(
    *, from_status: str, to_status: str, occurred_at: datetime, version: int
) -> EnclosureHistoryEvent:
    """A realistic `EnclosurePermitObserved` history row, payload included,
    with the PSS-address-carrying fields (`reason`, `monitor_ref`) a real
    stored event actually has -- so redaction tests exercise the real
    shape, not a payload that was already safe by construction."""
    return EnclosureHistoryEvent(
        event_id=uuid4(),
        event_type="EnclosurePermitObserved",
        version=version,
        occurred_at=occurred_at,
        recorded_at=occurred_at,
        payload={
            "from_status": from_status,
            "to_status": to_status,
            "reason": "PSS permit observation via S02BM-PSS:StaA:SecureM",
            "trigger": "Monitor",
            "triggered_by": str(uuid4()),
            "monitor_ref": "EpicsPv:S02BM-PSS:StaA:SecureM",
            "observed_at": None,
        },
    )


@pytest.mark.unit
def test_build_enclosure_timeline_message_shape_for_genesis_only() -> None:
    enclosure_id = uuid4()
    view = _enclosure_history_view(enclosure_id, permit_status="Unknown")

    message = build_enclosure_timeline_message(
        view=view, generated_at="2026-08-30T12:00:05+00:00", producer_id="p1"
    )

    assert message["kind"] == "enclosure_timeline"
    assert message["schema_version"] == 1
    assert message["producer_id"] == "p1"
    assert message["enclosure_id"] == str(enclosure_id)
    document = message["document"]
    assert document["domain"] == {"from": _NOW.isoformat(), "to": "2026-08-30T12:00:05+00:00"}
    assert document["subject_lane_id"] == "permit"
    assert document["title"] == "2-BM-A"
    assert document["subtitle"] == "Unknown"
    assert document["truncated"] == {"events": False}
    permit_lane = next(lane for lane in document["lanes"] if lane["lane_id"] == "permit")
    lifecycle_lane = next(lane for lane in document["lanes"] if lane["lane_id"] == "lifecycle")
    assert permit_lane["points"] == [
        {"t": _NOW.isoformat(), "label": "Unknown", "state": "Unknown", "tone": "warn"}
    ]
    assert lifecycle_lane["points"] == [
        {"t": _NOW.isoformat(), "label": "Active", "state": "Active"}
    ]


@pytest.mark.unit
def test_build_enclosure_timeline_message_folds_permit_transitions_in_order() -> None:
    enclosure_id = uuid4()
    genesis = EnclosureHistoryEvent(
        event_id=uuid4(),
        event_type="EnclosureRegistered",
        version=1,
        occurred_at=_NOW,
        recorded_at=_NOW,
        payload={},
    )
    permitted = _permit_observed_event(
        from_status="Unknown",
        to_status="Permitted",
        occurred_at=_NOW + timedelta(seconds=5),
        version=2,
    )
    not_permitted = _permit_observed_event(
        from_status="Permitted",
        to_status="NotPermitted",
        occurred_at=_NOW + timedelta(seconds=10),
        version=3,
    )
    view = _enclosure_history_view(
        enclosure_id, permit_status="NotPermitted", events=[genesis, permitted, not_permitted]
    )

    message = build_enclosure_timeline_message(
        view=view, generated_at="2026-08-30T12:00:20+00:00", producer_id="p1"
    )

    permit_lane = next(lane for lane in message["document"]["lanes"] if lane["lane_id"] == "permit")
    assert [p["label"] for p in permit_lane["points"]] == ["Unknown", "Permitted", "NotPermitted"]
    assert [p["tone"] for p in permit_lane["points"]] == ["warn", "good", "warn"]


@pytest.mark.unit
def test_build_enclosure_timeline_message_decommission_lands_on_lifecycle_lane_only() -> None:
    enclosure_id = uuid4()
    genesis = EnclosureHistoryEvent(
        event_id=uuid4(),
        event_type="EnclosureRegistered",
        version=1,
        occurred_at=_NOW,
        recorded_at=_NOW,
        payload={},
    )
    decommissioned = EnclosureHistoryEvent(
        event_id=uuid4(),
        event_type="EnclosureDecommissioned",
        version=2,
        occurred_at=_NOW + timedelta(seconds=5),
        recorded_at=_NOW + timedelta(seconds=5),
        payload={"reason": "instrument removed", "triggered_by": str(uuid4())},
    )
    view = _enclosure_history_view(
        enclosure_id, lifecycle="Decommissioned", events=[genesis, decommissioned]
    )

    message = build_enclosure_timeline_message(
        view=view, generated_at="2026-08-30T12:00:10+00:00", producer_id="p1"
    )

    permit_lane = next(lane for lane in message["document"]["lanes"] if lane["lane_id"] == "permit")
    lifecycle_lane = next(
        lane for lane in message["document"]["lanes"] if lane["lane_id"] == "lifecycle"
    )
    assert len(permit_lane["points"]) == 1  # genesis only; decommission never touches permit
    assert [p["label"] for p in lifecycle_lane["points"]] == ["Active", "Decommissioned"]


@pytest.mark.unit
def test_build_enclosure_timeline_message_truncated_key_is_events_not_observations() -> None:
    enclosure_id = uuid4()
    view = _enclosure_history_view(enclosure_id, events_truncated=True)

    message = build_enclosure_timeline_message(view=view, generated_at="t1", producer_id="p1")

    assert message["document"]["truncated"] == {"events": True}


@pytest.mark.unit
def test_build_enclosure_timeline_message_never_carries_reason_or_monitor_ref_or_source() -> None:
    """The load-bearing redaction test for this whole lens: the raw
    EnclosureHistoryEvent payloads DO carry the PSS PV address (via
    `reason` and `monitor_ref`), because `get_enclosure_history` is a
    general-purpose on-network read that legitimately ships full detail
    (see its handler's own docstring). This function is the layer where
    that must stop, because its output is what actually leaves the
    beamline network for the external relay."""
    enclosure_id = uuid4()
    genesis = EnclosureHistoryEvent(
        event_id=uuid4(),
        event_type="EnclosureRegistered",
        version=1,
        occurred_at=_NOW,
        recorded_at=_NOW,
        payload={},
    )
    observed = _permit_observed_event(
        from_status="Unknown",
        to_status="Permitted",
        occurred_at=_NOW + timedelta(seconds=5),
        version=2,
    )
    view = _enclosure_history_view(enclosure_id, events=[genesis, observed])

    message = build_enclosure_timeline_message(view=view, generated_at="t1", producer_id="p1")

    serialized = json.dumps(message)
    assert "S02BM-PSS" not in serialized
    assert "reason" not in serialized
    assert "monitor_ref" not in serialized
    assert "triggered_by" not in serialized
    assert observed.payload["triggered_by"] not in serialized


@pytest.mark.unit
def test_build_enclosure_timeline_message_skips_an_unrecognized_event_type() -> None:
    """Forward compatibility, mirroring the relay's own
    `producer.unknown_kind` posture: a future Enclosure event this
    producer predates must never break the live feed."""
    enclosure_id = uuid4()
    genesis = EnclosureHistoryEvent(
        event_id=uuid4(),
        event_type="EnclosureRegistered",
        version=1,
        occurred_at=_NOW,
        recorded_at=_NOW,
        payload={},
    )
    from_the_future = EnclosureHistoryEvent(
        event_id=uuid4(),
        event_type="EnclosureSomethingNotYetInvented",
        version=2,
        occurred_at=_NOW + timedelta(seconds=5),
        recorded_at=_NOW + timedelta(seconds=5),
        payload={},
    )
    view = _enclosure_history_view(enclosure_id, events=[genesis, from_the_future])

    message = build_enclosure_timeline_message(view=view, generated_at="t1", producer_id="p1")

    permit_lane = next(lane for lane in message["document"]["lanes"] if lane["lane_id"] == "permit")
    lifecycle_lane = next(
        lane for lane in message["document"]["lanes"] if lane["lane_id"] == "lifecycle"
    )
    assert len(permit_lane["points"]) == 1
    assert len(lifecycle_lane["points"]) == 1


# ---------- _EnclosureTimelineTail ----------


@pytest.mark.unit
async def test_enclosure_timeline_tail_emits_on_first_sight() -> None:
    enclosure_id = uuid4()
    get_enclosure_history = _make_get_enclosure_history(
        {enclosure_id: _enclosure_history_view(enclosure_id)}
    )
    tail = _EnclosureTimelineTail()
    kernel = _kernel()

    messages = await tail.poll(
        get_enclosure_history,
        kernel,
        enclosure_ids=[enclosure_id],
        generated_at="t0",
        producer_id="p1",
    )

    assert len(messages) == 1
    assert messages[0]["enclosure_id"] == str(enclosure_id)


@pytest.mark.unit
async def test_enclosure_timeline_tail_emits_nothing_when_unchanged() -> None:
    enclosure_id = uuid4()
    get_enclosure_history = _make_get_enclosure_history(
        {enclosure_id: _enclosure_history_view(enclosure_id)}
    )
    tail = _EnclosureTimelineTail()
    kernel = _kernel()

    await tail.poll(
        get_enclosure_history,
        kernel,
        enclosure_ids=[enclosure_id],
        generated_at="t0",
        producer_id="p1",
    )
    second = await tail.poll(
        get_enclosure_history,
        kernel,
        enclosure_ids=[enclosure_id],
        generated_at="t1",
        producer_id="p1",
    )

    assert second == []


@pytest.mark.unit
async def test_enclosure_timeline_tail_emits_again_once_the_document_changes() -> None:
    enclosure_id = uuid4()
    genesis = EnclosureHistoryEvent(
        event_id=uuid4(),
        event_type="EnclosureRegistered",
        version=1,
        occurred_at=_NOW,
        recorded_at=_NOW,
        payload={},
    )
    views = {enclosure_id: _enclosure_history_view(enclosure_id, events=[genesis])}
    get_enclosure_history = _make_get_enclosure_history(views)
    tail = _EnclosureTimelineTail()
    kernel = _kernel()

    await tail.poll(
        get_enclosure_history,
        kernel,
        enclosure_ids=[enclosure_id],
        generated_at="t0",
        producer_id="p1",
    )
    observed = _permit_observed_event(
        from_status="Unknown",
        to_status="Permitted",
        occurred_at=_NOW + timedelta(seconds=5),
        version=2,
    )
    views[enclosure_id] = _enclosure_history_view(enclosure_id, events=[genesis, observed])
    second = await tail.poll(
        get_enclosure_history,
        kernel,
        enclosure_ids=[enclosure_id],
        generated_at="t1",
        producer_id="p1",
    )

    assert len(second) == 1


@pytest.mark.unit
async def test_enclosure_timeline_tail_on_reconnect_repushes_an_unchanged_enclosure() -> None:
    enclosure_id = uuid4()
    get_enclosure_history = _make_get_enclosure_history(
        {enclosure_id: _enclosure_history_view(enclosure_id)}
    )
    tail = _EnclosureTimelineTail()
    kernel = _kernel()

    await tail.poll(
        get_enclosure_history,
        kernel,
        enclosure_ids=[enclosure_id],
        generated_at="t0",
        producer_id="p1",
    )
    tail.on_reconnect()
    after_reconnect = await tail.poll(
        get_enclosure_history,
        kernel,
        enclosure_ids=[enclosure_id],
        generated_at="t1",
        producer_id="p1",
    )

    assert len(after_reconnect) == 1


@pytest.mark.unit
async def test_enclosure_timeline_tail_skips_an_enclosure_the_handler_cannot_find() -> None:
    tail = _EnclosureTimelineTail()
    kernel = _kernel()
    get_enclosure_history = _make_get_enclosure_history({})

    messages = await tail.poll(
        get_enclosure_history,
        kernel,
        enclosure_ids=[uuid4()],
        generated_at="t0",
        producer_id="p1",
    )

    assert messages == []


# ---------- pure: build_run_history_response / _parse_inbound ----------


@pytest.mark.unit
def test_build_run_history_response_shape() -> None:
    response = build_run_history_response(
        request_id="r1",
        status="ok",
        generated_at="2026-06-22T12:00:00+00:00",
        producer_id="p1",
        source="read",
        history={"kind": "run_history"},
    )

    assert response == {
        "kind": "run_history_response",
        "schema_version": 1,
        "producer_id": "p1",
        "request_id": "r1",
        "generated_at": "2026-06-22T12:00:00+00:00",
        "status": "ok",
        "source": "read",
        "history": {"kind": "run_history"},
    }


@pytest.mark.unit
def test_build_run_history_response_defaults_source_and_history_to_none() -> None:
    response = build_run_history_response(
        request_id="r1", status="not_found", generated_at="t", producer_id="p1"
    )

    assert response["source"] is None
    assert response["history"] is None


@pytest.mark.unit
def test_parse_inbound_rejects_non_json() -> None:
    assert _parse_inbound("not json") is None


@pytest.mark.unit
def test_parse_inbound_drops_an_unrecognized_kind_with_no_reply() -> None:
    """Mirrors `relay.py`'s own `producer.unknown_kind` posture: forward
    compatibility means logging and dropping, never guessing a reply."""
    assert _parse_inbound(json.dumps({"kind": "something_else", "request_id": "x"})) is None


@pytest.mark.unit
def test_parse_inbound_drops_a_request_with_no_usable_request_id() -> None:
    assert _parse_inbound(json.dumps({"kind": "run_history_request"})) is None


@pytest.mark.unit
def test_parse_inbound_marks_unsupported_schema_version_but_still_replies() -> None:
    item = _parse_inbound(
        json.dumps({"kind": "run_history_request", "request_id": "r1", "schema_version": 99})
    )

    assert item == _Inbound(request_id="r1", run_id=None, status="unsupported")


@pytest.mark.unit
def test_parse_inbound_marks_a_malformed_run_id() -> None:
    item = _parse_inbound(
        json.dumps(
            {
                "kind": "run_history_request",
                "request_id": "r1",
                "schema_version": 1,
                "run_id": "not-a-uuid",
            }
        )
    )

    assert item == _Inbound(request_id="r1", run_id=None, status="malformed")


@pytest.mark.unit
def test_parse_inbound_accepts_a_well_formed_request() -> None:
    run_id = uuid4()
    item = _parse_inbound(
        json.dumps(
            {
                "kind": "run_history_request",
                "request_id": "r1",
                "schema_version": 1,
                "run_id": str(run_id),
            }
        )
    )

    assert item == _Inbound(request_id="r1", run_id=run_id, status=None)


# ---------- _answer_request ----------


@pytest.mark.unit
async def test_answer_request_echoes_a_pre_resolved_status_without_touching_deps() -> None:
    item = _Inbound(request_id="r1", run_id=None, status="malformed")

    response = await _answer_request(
        item,
        deps=_kernel(),
        get_run_history=_make_get_run_history(),
        run_history_tail=_RunHistoryTail(),
        producer_id="p1",
        generated_at="t",
    )

    assert response["status"] == "malformed"
    assert response["request_id"] == "r1"
    assert response["history"] is None


@pytest.mark.unit
async def test_answer_request_is_not_found_when_get_run_history_returns_none() -> None:
    item = _Inbound(request_id="r1", run_id=uuid4(), status=None)

    response = await _answer_request(
        item,
        deps=_kernel(),
        get_run_history=_make_get_run_history(),
        run_history_tail=_RunHistoryTail(),
        producer_id="p1",
        generated_at="t",
    )

    assert response["status"] == "not_found"


@pytest.mark.unit
async def test_answer_request_becomes_unauthorized_instead_of_raising() -> None:
    """The single highest-severity failure mode this design guards against:
    see this module's Transport section."""

    async def denying_get_run_history(
        query: GetRunHistory,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunHistoryView | None:
        raise RunUnauthorizedError("denied")

    item = _Inbound(request_id="r1", run_id=uuid4(), status=None)

    response = await _answer_request(
        item,
        deps=_kernel(),
        get_run_history=denying_get_run_history,
        run_history_tail=_RunHistoryTail(),
        producer_id="p1",
        generated_at="t",
    )

    assert response["status"] == "unauthorized"
    assert response["history"] is None


@pytest.mark.unit
async def test_answer_request_becomes_error_instead_of_raising_on_any_other_exception() -> None:
    async def broken_get_run_history(
        query: GetRunHistory,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunHistoryView | None:
        raise RuntimeError("boom")

    item = _Inbound(request_id="r1", run_id=uuid4(), status=None)

    response = await _answer_request(
        item,
        deps=_kernel(),
        get_run_history=broken_get_run_history,
        run_history_tail=_RunHistoryTail(),
        producer_id="p1",
        generated_at="t",
    )

    assert response["status"] == "error"


@pytest.mark.unit
async def test_answer_request_serves_a_cached_terminal_run_without_a_fresh_read() -> None:
    run_id = uuid4()
    calls = 0

    async def counting_get_run_history(
        query: GetRunHistory,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunHistoryView | None:
        nonlocal calls
        calls += 1
        return _history_view(run_id)

    tail = _RunHistoryTail()
    kernel = _kernel()
    await tail.poll(
        counting_get_run_history, kernel, open_run_ids=[run_id], generated_at="t0", producer_id="p1"
    )
    await tail.poll(
        counting_get_run_history, kernel, open_run_ids=[], generated_at="t1", producer_id="p1"
    )
    assert calls == 2  # one open-set fetch, one terminal checkpoint

    item = _Inbound(request_id="r1", run_id=run_id, status=None)
    response = await _answer_request(
        item,
        deps=kernel,
        get_run_history=counting_get_run_history,
        run_history_tail=tail,
        producer_id="p1",
        generated_at="t2",
    )

    assert response["status"] == "ok"
    assert response["source"] == "cache"
    assert calls == 2  # no additional read


@pytest.mark.unit
async def test_answer_request_does_not_serve_a_non_terminal_cached_run() -> None:
    run_id = uuid4()
    calls = 0

    async def counting_get_run_history(
        query: GetRunHistory,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunHistoryView | None:
        nonlocal calls
        calls += 1
        return _history_view(run_id)

    tail = _RunHistoryTail()
    kernel = _kernel()
    await tail.poll(
        counting_get_run_history, kernel, open_run_ids=[run_id], generated_at="t0", producer_id="p1"
    )
    assert calls == 1

    item = _Inbound(request_id="r1", run_id=run_id, status=None)
    response = await _answer_request(
        item,
        deps=kernel,
        get_run_history=counting_get_run_history,
        run_history_tail=tail,
        producer_id="p1",
        generated_at="t1",
    )

    assert response["status"] == "ok"
    assert response["source"] == "read"
    assert calls == 2  # fresh read, not served from the non-terminal cache


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


# ---------- build_activity_message ----------


@pytest.mark.unit
def test_build_activity_message_shape_for_an_operator_originated_event() -> None:
    stream_id = uuid4()
    correlation_id = uuid4()
    row = EventActivityRow(
        stream_type="Run",
        stream_id=stream_id,
        event_type="RunStarted",
        occurred_at=_NOW,
        recorded_at=_NOW,
        correlation_id=correlation_id,
        causation_id=None,
        cause_occurred_at=None,
    )

    message = build_activity_message(rows=[row], generated_at="t0", producer_id="p1")

    assert message == {
        "kind": "activity",
        "schema_version": 1,
        "producer_id": "p1",
        "generated_at": "t0",
        "events": [
            {
                "stream_type": "Run",
                "stream_id": str(stream_id),
                "event_type": "RunStarted",
                "occurred_at": _NOW.isoformat(),
                "recorded_at": _NOW.isoformat(),
                "correlation_id": str(correlation_id),
                "causation_id": None,
                "cause_occurred_at": None,
            }
        ],
    }


@pytest.mark.unit
def test_build_activity_message_carries_a_reacted_event_s_cause_and_its_time() -> None:
    """A subscriber reacting to an event sets `causation_id`, and the cause is
    usually older than the receiver's own window. Both the id and the cause's
    time have to ride out, or a viewer holding fifteen minutes cannot tell an
    event whose cause scrolled away from one that never had a cause at all."""
    causation_id = uuid4()
    cause_at = _NOW - timedelta(minutes=40)
    row = EventActivityRow(
        stream_type="Caution",
        stream_id=uuid4(),
        event_type="CautionRegistered",
        occurred_at=_NOW,
        recorded_at=_NOW,
        correlation_id=uuid4(),
        causation_id=causation_id,
        cause_occurred_at=cause_at,
    )

    message = build_activity_message(rows=[row], generated_at="t0", producer_id="p1")

    event = message["events"][0]
    assert event["causation_id"] == str(causation_id)
    assert event["cause_occurred_at"] == cause_at.isoformat()


# ---------- _ActivityTail ----------


async def _append_event(
    store: InMemoryEventStore,
    *,
    stream_type: str = "Run",
    stream_id: UUID | None = None,
    event_type: str = "RunStarted",
    occurred_at: datetime = _NOW,
) -> None:
    await store.append(
        stream_type,
        stream_id or uuid4(),
        0,
        [
            NewEvent(
                event_id=uuid4(),
                event_type=event_type,
                schema_version=1,
                payload={},
                occurred_at=occurred_at,
                correlation_id=uuid4(),
                principal_id=None,
            )
        ],
    )


@pytest.mark.unit
async def test_activity_tail_starts_empty_even_with_existing_events() -> None:
    """Mirrors `_DecisionTail`'s own "starts empty" guarantee: the first
    poll establishes a baseline at the CURRENT tip, never replaying
    history that predates this tail's construction."""
    store = InMemoryEventStore()
    await _append_event(store)
    trail = InMemoryEventActivityTrail(store)
    tail = _ActivityTail()

    rows = await tail.poll(trail)

    assert rows == []


@pytest.mark.unit
async def test_activity_tail_returns_a_freshly_appended_event() -> None:
    store = InMemoryEventStore()
    trail = InMemoryEventActivityTrail(store)
    tail = _ActivityTail()
    await tail.poll(trail)  # establish the baseline

    stream_id = uuid4()
    await _append_event(store, stream_id=stream_id, event_type="RunHeld")
    rows = await tail.poll(trail)

    assert len(rows) == 1
    assert rows[0].stream_type == "Run"
    assert rows[0].stream_id == stream_id
    assert rows[0].event_type == "RunHeld"


@pytest.mark.unit
async def test_activity_tail_does_not_repeat_a_row_already_returned() -> None:
    store = InMemoryEventStore()
    trail = InMemoryEventActivityTrail(store)
    tail = _ActivityTail()
    await tail.poll(trail)
    await _append_event(store)

    first = await tail.poll(trail)
    second = await tail.poll(trail)

    assert len(first) == 1
    assert second == []


@pytest.mark.unit
async def test_activity_tail_never_ships_the_event_payload() -> None:
    """The whole reason `EventActivityRow` has no `payload` field: proves
    the tail's output shape structurally cannot carry it, rather than
    trusting a serializer to drop it."""
    store = InMemoryEventStore()
    trail = InMemoryEventActivityTrail(store)
    tail = _ActivityTail()
    await tail.poll(trail)
    await _append_event(store)

    (row,) = await tail.poll(trail)

    assert not hasattr(row, "payload")


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
async def test_lifespan_pushes_an_activity_message_when_an_event_is_appended() -> None:
    """Flowing mode's end-to-end path: an event appended to the store
    after StatusPush has connected arrives on the wire as its own message
    kind, event metadata only -- no `payload` key anywhere in it."""
    received: asyncio.Queue[str] = asyncio.Queue()

    async def handler(ws: ServerConnection) -> None:
        async for message in ws:
            await received.put(message if isinstance(message, str) else message.decode())

    async with serve(handler, "127.0.0.1", 0) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        url = f"ws://127.0.0.1:{port}/ingest"
        store = InMemoryEventStore()
        kernel = _kernel(
            status_push_enabled=True,
            status_push_url=url,
            status_push_tick_seconds=0.1,
            event_store=store,
        )

        async with status_push_lifespan(kernel, **_default_handlers()):
            first = json.loads(await asyncio.wait_for(received.get(), timeout=5))
            assert first["kind"] == "snapshot"  # the activity baseline is now set

            stream_id = uuid4()
            await _append_event(store, stream_id=stream_id, event_type="RunStarted")

            activity = json.loads(await asyncio.wait_for(received.get(), timeout=5))

        assert activity["kind"] == "activity"
        assert len(activity["events"]) == 1
        event = activity["events"][0]
        assert event["stream_type"] == "Run"
        assert event["stream_id"] == str(stream_id)
        assert event["event_type"] == "RunStarted"
        assert "payload" not in event


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
async def test_lifespan_pushes_enclosure_timeline_alongside_the_snapshot() -> None:
    """End to end against a real socket: an Active enclosure with a
    wired `get_enclosure_history` produces an `enclosure_timeline`
    message on the same connection as the snapshot, and that message
    carries no PSS PV address -- the redaction that matters happens on
    the actual wire, not just inside the pure builder."""
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
        enclosure_id = uuid4()
        active = EnclosureSummaryItem(
            enclosure_id=enclosure_id,
            name="2-BM-A",
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
        genesis = EnclosureHistoryEvent(
            event_id=uuid4(),
            event_type="EnclosureRegistered",
            version=1,
            occurred_at=_NOW,
            recorded_at=_NOW,
            payload={},
        )
        observed = _permit_observed_event(
            from_status="Unknown", to_status="Permitted", occurred_at=_NOW, version=2
        )
        view = _enclosure_history_view(
            enclosure_id, name="2-BM-A", permit_status="Permitted", events=[genesis, observed]
        )

        async with status_push_lifespan(
            kernel,
            **_default_handlers(
                list_enclosures=_make_list_enclosures([active]),
                get_enclosure_history=_make_get_enclosure_history({enclosure_id: view}),
            ),
        ):
            first = json.loads(await asyncio.wait_for(received.get(), timeout=5))
            second = json.loads(await asyncio.wait_for(received.get(), timeout=5))

        by_kind = {first.get("kind"): first, second.get("kind"): second}
        assert "enclosure_timeline" in by_kind
        assert "snapshot" in by_kind
        timeline = by_kind["enclosure_timeline"]
        assert timeline["enclosure_id"] == str(enclosure_id)
        assert timeline["document"]["title"] == "2-BM-A"
        assert timeline["document"]["subject_lane_id"] == "permit"
        assert "S02BM-PSS" not in json.dumps(timeline)
        assert "reason" not in json.dumps(timeline)


# ---------- on-demand requests: first-ever inbound-frame tests ----------
#
# Every end-to-end test above uses a fake relay that only drains
# (`async for message in ws: ...`); these need one that can also send a
# frame back, since these are the first tests in this file to exercise
# the producer's `_read_requests` reader task at all.


def _bidirectional_handler(received: asyncio.Queue[str], sock_box: list[ServerConnection]) -> Any:
    """A fake relay `/ingest` handler that drains into `received`, same as
    every handler above, AND stashes the live `ServerConnection` in
    `sock_box` so the test itself can send a `run_history_request` back."""

    async def handler(ws: ServerConnection) -> None:
        sock_box.append(ws)
        async for message in ws:
            await received.put(message if isinstance(message, str) else message.decode())

    return handler


async def _wait_until_connected(sock_box: list[ServerConnection]) -> None:
    for _ in range(200):
        if sock_box:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("producer never connected to the fake relay")


@pytest.mark.unit
async def test_request_serving_resumes_snapshot_cadence_once_a_slow_read_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The load-bearing cadence test: while one on-demand request is being
    served, the tick loop's single writer/server phase is legitimately
    busy (this design has no per-item timeout, see this module's
    Transport section), but it must resume normal snapshot cadence the
    moment that read completes, with no reconnect and no runaway retry."""
    monkeypatch.setattr("cora.api._status_push._REQUEST_PHASE_BUDGET_SECONDS", 5.0, raising=False)
    received: asyncio.Queue[str] = asyncio.Queue()
    sock_box: list[ServerConnection] = []
    handler = _bidirectional_handler(received, sock_box)
    release_read = asyncio.Event()

    async def slow_get_run_history(
        query: GetRunHistory,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunHistoryView | None:
        await release_read.wait()
        return None

    async with serve(handler, "127.0.0.1", 0) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        url = f"ws://127.0.0.1:{port}/ingest"
        kernel = _kernel(
            status_push_enabled=True,
            status_push_url=url,
            status_push_tick_seconds=0.1,
            status_push_request_max_per_tick=2,
        )

        async with status_push_lifespan(
            kernel, **_default_handlers(get_run_history=slow_get_run_history)
        ):
            first = json.loads(await asyncio.wait_for(received.get(), timeout=5))
            assert first["kind"] == "snapshot"
            first_sequence = first["sequence"]
            await _wait_until_connected(sock_box)

            await sock_box[0].send(
                json.dumps(
                    {
                        "kind": "run_history_request",
                        "schema_version": 1,
                        "request_id": "hang-1",
                        "run_id": str(uuid4()),
                    }
                )
            )

            # The read is deliberately held open; no further message can
            # arrive while the tick loop's one writer is blocked inside
            # `_answer_request`.
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(received.get(), timeout=0.3)

            release_read.set()

            resumed = False
            for _ in range(20):
                msg = json.loads(await asyncio.wait_for(received.get(), timeout=2))
                if msg["kind"] == "run_history_response":
                    assert msg["status"] == "not_found"
                    assert msg["request_id"] == "hang-1"
                    continue
                assert msg["kind"] == "snapshot"
                assert msg["sequence"] > first_sequence
                resumed = True
                break
            assert resumed


@pytest.mark.unit
async def test_unauthorized_on_demand_request_does_not_disconnect_the_producer() -> None:
    """The single highest-severity failure mode named in this module's
    Transport section: an `UnauthorizedError` from a request-triggered
    read must never escape into `_push_loop`'s own reconnect handling.
    Asserted on the observable consequence -- exactly one producer
    connection is ever accepted -- rather than on internal state."""
    received: asyncio.Queue[str] = asyncio.Queue()
    sock_box: list[ServerConnection] = []
    connection_count = 0

    async def handler(ws: ServerConnection) -> None:
        nonlocal connection_count
        connection_count += 1
        sock_box.append(ws)
        async for message in ws:
            await received.put(message if isinstance(message, str) else message.decode())

    async def denying_get_run_history(
        query: GetRunHistory,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunHistoryView | None:
        raise RunUnauthorizedError("denied")

    async with serve(handler, "127.0.0.1", 0) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        url = f"ws://127.0.0.1:{port}/ingest"
        kernel = _kernel(
            status_push_enabled=True,
            status_push_url=url,
            status_push_tick_seconds=0.1,
            status_push_request_max_per_tick=2,
        )

        async with status_push_lifespan(
            kernel, **_default_handlers(get_run_history=denying_get_run_history)
        ):
            first = json.loads(await asyncio.wait_for(received.get(), timeout=5))
            assert first["kind"] == "snapshot"
            await _wait_until_connected(sock_box)

            await sock_box[0].send(
                json.dumps(
                    {
                        "kind": "run_history_request",
                        "schema_version": 1,
                        "request_id": "req-1",
                        "run_id": str(uuid4()),
                    }
                )
            )

            saw_unauthorized = False
            saw_snapshot_after = False
            for _ in range(30):
                msg = json.loads(await asyncio.wait_for(received.get(), timeout=2))
                if msg.get("kind") == "run_history_response":
                    assert msg["status"] == "unauthorized"
                    saw_unauthorized = True
                    continue
                assert msg["kind"] == "snapshot"
                if saw_unauthorized:
                    saw_snapshot_after = True
                    break

        assert saw_unauthorized
        assert saw_snapshot_after  # ticks kept arriving normally afterward
        assert connection_count == 1  # never reconnected


@pytest.mark.unit
async def test_request_max_per_tick_zero_disables_the_reader_entirely() -> None:
    received: asyncio.Queue[str] = asyncio.Queue()
    sock_box: list[ServerConnection] = []
    handler = _bidirectional_handler(received, sock_box)

    async with serve(handler, "127.0.0.1", 0) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        url = f"ws://127.0.0.1:{port}/ingest"
        kernel = _kernel(
            status_push_enabled=True,
            status_push_url=url,
            status_push_tick_seconds=0.1,
            status_push_request_max_per_tick=0,
        )

        async with status_push_lifespan(kernel, **_default_handlers()):
            first = json.loads(await asyncio.wait_for(received.get(), timeout=5))
            assert first["kind"] == "snapshot"
            await _wait_until_connected(sock_box)

            await sock_box[0].send(
                json.dumps(
                    {
                        "kind": "run_history_request",
                        "schema_version": 1,
                        "request_id": "req-1",
                        "run_id": str(uuid4()),
                    }
                )
            )

            # Only snapshots ever arrive: no reader task, no response, no
            # crash.
            for _ in range(5):
                msg = json.loads(await asyncio.wait_for(received.get(), timeout=2))
                assert msg["kind"] == "snapshot"


@pytest.mark.unit
async def test_request_is_answered_after_a_reconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fresh reader task is created per connection (see `_push_loop`'s
    own docstring); this proves it actually comes back after one."""
    monkeypatch.setattr("cora.api._status_push._RECONNECT_INITIAL_SECONDS", 0.02, raising=False)
    received: asyncio.Queue[str] = asyncio.Queue()
    sock_box: list[ServerConnection] = []
    handler = _bidirectional_handler(received, sock_box)

    server = await serve(handler, "127.0.0.1", 0)
    port = next(iter(server.sockets)).getsockname()[1]
    url = f"ws://127.0.0.1:{port}/ingest"
    kernel = _kernel(
        status_push_enabled=True,
        status_push_url=url,
        status_push_tick_seconds=0.1,
        status_push_request_max_per_tick=2,
    )

    async with status_push_lifespan(kernel, **_default_handlers()):
        await asyncio.wait_for(received.get(), timeout=5)

        server.close()
        await server.wait_closed()
        sock_box.clear()
        while not received.empty():
            received.get_nowait()

        server = await serve(handler, "127.0.0.1", port)
        await asyncio.wait_for(received.get(), timeout=10)
        await _wait_until_connected(sock_box)

        await sock_box[0].send(
            json.dumps(
                {
                    "kind": "run_history_request",
                    "schema_version": 1,
                    "request_id": "post-reconnect",
                    "run_id": str(uuid4()),
                }
            )
        )
        for _ in range(20):
            msg = json.loads(await asyncio.wait_for(received.get(), timeout=5))
            if msg.get("kind") == "run_history_response":
                assert msg["request_id"] == "post-reconnect"
                assert msg["status"] == "not_found"
                break
        else:
            raise AssertionError("never got a response after reconnecting")

    server.close()
    await server.wait_closed()


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
