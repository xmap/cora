"""Tests for the RunWatcher shadow runtime (cora.api._run_watcher).

Covers the no-op-when-unconfigured lifespan shape, that every observed
phase (and the two no-phase cases, unreached and probe-only) logs the
right event with the right fields, that a bad observation is logged
and skipped rather than killing the loop, and that a stream ending
triggers reconnect rather than the loop exiting silently.

Every assertion is against `structlog.testing.capture_logs()`. There is
nothing else to assert: shadow mode has no event store, no entries
table, and no Run command, so "it wrote nothing" is a structural fact
about the module's imports, not a per-test behavior to pin.
"""

# white-box test of the runtime internals (private constants)
# pyright: reportPrivateUsage=false

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
import structlog.testing

from cora.api._run_watcher import (
    RUN_WATCHER_MONITOR_SOURCE_ID,
    RunWatcherRecorder,
    observe_capture,
    rebuild_open_captures,
    run_run_watcher,
    run_watcher_lifespan,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import ConductMode, RunStarted, event_type_name, to_payload
from cora.run.errors import UnauthorizedError
from cora.run.features.list_runs import RunListPage, RunSummaryItem
from cora.run.features.record_watched_run.command import RecordWatchedRun
from cora.run.ports.capture_observer import CaptureObservation, CaptureObserverScope, CapturePhase
from cora.shared.reach import ReachTier
from tests.unit._helpers import build_deps

_CODE = "2bmb-tomoscan"
_NOW = datetime(2026, 8, 13, 12, 0, 0, tzinfo=UTC)
_PLAN_ID = UUID("01900000-0000-7000-8000-000000007107")


def _obs(
    *,
    reported_status: str | None,
    phase: CapturePhase | None,
    reach_tier: ReachTier = ReachTier.RELAYED,
    observed_at: datetime | None = _NOW,
    capture_code: str = _CODE,
) -> CaptureObservation:
    return CaptureObservation(
        capture_code=capture_code,
        reported_status=reported_status,
        phase=phase,
        reach_tier=reach_tier,
        observed_at=observed_at,
        source_kind="EpicsPv",
        source_id="2bmb:TomoScan:ScanStatus",
    )


class _FakeObserver:
    """Yields a fixed observation sequence once, then ends the stream."""

    def __init__(self, observations: list[CaptureObservation]) -> None:
        self._observations = observations

    def observe(self, scope: CaptureObserverScope) -> AsyncGenerator[CaptureObservation]:
        return self._drain()

    async def _drain(self) -> AsyncGenerator[CaptureObservation]:
        for observation in self._observations:
            yield observation


class _BoomObserver:
    """Raises mid-iteration so the loop's outer resilience branch fires."""

    def observe(self, scope: CaptureObserverScope) -> AsyncGenerator[CaptureObservation]:
        return self._drain()

    async def _drain(self) -> AsyncGenerator[CaptureObservation]:
        raise RuntimeError("observer boom")
        yield  # pragma: no cover - unreachable, marks this body an async generator


@pytest.mark.unit
@pytest.mark.parametrize(
    ("phase", "expected_event"),
    [
        (CapturePhase.BEGUN, "run_watcher.capture_begun"),
        (CapturePhase.PROGRESSING, "run_watcher.capture_progressing"),
        (CapturePhase.ENDED, "run_watcher.capture_ended"),
        (CapturePhase.ABORTED, "run_watcher.capture_aborted"),
        (CapturePhase.UNRECOGNIZED, "run_watcher.capture_unrecognized"),
    ],
)
def test_observe_capture_logs_the_matching_event_per_phase(
    phase: CapturePhase, expected_event: str
) -> None:
    with structlog.testing.capture_logs() as logs:
        observe_capture(_obs(reported_status="whatever", phase=phase))
    assert [entry["event"] for entry in logs] == [expected_event]


@pytest.mark.unit
def test_observe_capture_logs_unreached_for_a_probe_only_observation() -> None:
    """A `None` phase (no status claim at all) logs as unreached rather
    than being silently dropped."""
    with structlog.testing.capture_logs() as logs:
        observe_capture(_obs(reported_status=None, phase=None))
    assert [entry["event"] for entry in logs] == ["run_watcher.capture_unreached"]


@pytest.mark.unit
def test_observe_capture_carries_the_full_attribution() -> None:
    with structlog.testing.capture_logs() as logs:
        observe_capture(_obs(reported_status="Scan complete", phase=CapturePhase.ENDED))
    entry = logs[0]
    assert entry["capture_code"] == _CODE
    assert entry["reported_status"] == "Scan complete"
    assert entry["source_kind"] == "EpicsPv"
    assert entry["source_id"] == "2bmb:TomoScan:ScanStatus"
    assert entry["observed_at"] == _NOW.isoformat()


@pytest.mark.unit
def test_observe_capture_reports_no_substrate_time_as_none_not_a_string() -> None:
    """An adapter with no substrate time reports `None`; the log line
    must carry that faithfully rather than stringifying a sentinel."""
    with structlog.testing.capture_logs() as logs:
        observe_capture(
            _obs(reported_status="Scan complete", phase=CapturePhase.ENDED, observed_at=None)
        )
    assert logs[0]["observed_at"] is None


@pytest.mark.unit
async def test_run_run_watcher_is_a_no_op_for_empty_capture_codes() -> None:
    observer = _FakeObserver([_obs(reported_status="Scan complete", phase=CapturePhase.ENDED)])
    await run_run_watcher(observer=observer, capture_codes=frozenset())
    # No assertion needed beyond "returns": an observer never drained
    # would hang forever if the empty-scope short-circuit were missing.


@pytest.mark.unit
async def test_run_run_watcher_logs_every_observation_in_sequence() -> None:
    observer = _FakeObserver(
        [
            _obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN),
            _obs(reported_status="Collecting projections", phase=CapturePhase.PROGRESSING),
            _obs(reported_status="Scan complete", phase=CapturePhase.ENDED),
        ]
    )
    task = asyncio.create_task(run_run_watcher(observer=observer, capture_codes=frozenset({_CODE})))
    with structlog.testing.capture_logs() as logs:
        await asyncio.sleep(0.05)  # one full drain of the fixed sequence
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    events = [entry["event"] for entry in logs]
    assert events == [
        "run_watcher.capture_begun",
        "run_watcher.capture_progressing",
        "run_watcher.capture_ended",
    ]


@pytest.mark.unit
async def test_run_run_watcher_survives_an_observer_that_raises() -> None:
    """The outer resilience branch logs and reconnects rather than the
    loop propagating the exception and dying silently."""
    task = asyncio.create_task(
        run_run_watcher(
            observer=_BoomObserver(),
            capture_codes=frozenset({_CODE}),
            reconnect_delay_seconds=0.01,
        )
    )
    with structlog.testing.capture_logs() as logs:
        await asyncio.sleep(0.05)  # several reconnect passes at this cadence
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    events = [entry["event"] for entry in logs]
    assert "run_watcher.iteration_failed" in events


@pytest.mark.unit
async def test_lifespan_is_a_no_op_when_no_capture_codes_configured() -> None:
    entered = False
    async with run_watcher_lifespan(observer=_FakeObserver([]), capture_codes=frozenset()):
        entered = True
    assert entered


@pytest.mark.unit
async def test_lifespan_spawns_and_cleanly_cancels_the_background_task() -> None:
    observer = _FakeObserver([_obs(reported_status="Scan complete", phase=CapturePhase.ENDED)])
    with structlog.testing.capture_logs() as logs:
        async with run_watcher_lifespan(observer=observer, capture_codes=frozenset({_CODE})):
            await asyncio.sleep(0.02)
    events = [entry["event"] for entry in logs]
    assert "run_watcher.capture_ended" in events


class _FakeRecordWatchedRun:
    """Fake `record_watched_run` handler: records every call, returns a
    fixed run_id, or raises a configured exception instead."""

    def __init__(self, *, run_id: UUID | None = None, raises: Exception | None = None) -> None:
        self.run_id = run_id if run_id is not None else uuid4()
        self.raises = raises
        self.calls: list[RecordWatchedRun] = []

    async def __call__(
        self,
        command: RecordWatchedRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        self.calls.append(command)
        if self.raises is not None:
            raise self.raises
        return self.run_id


def _recorder(
    *,
    record_watched_run: _FakeRecordWatchedRun,
    run_watcher_recording_enabled: bool = True,
    capture_watch_plan_id: UUID | None = _PLAN_ID,
    open_captures: dict[str, UUID] | None = None,
) -> RunWatcherRecorder:
    settings = Settings(  # type: ignore[call-arg]
        run_watcher_recording_enabled=run_watcher_recording_enabled,
        capture_watch_plan_id=capture_watch_plan_id,
    )
    return RunWatcherRecorder(
        deps=build_deps(ids=[uuid4() for _ in range(10)]),
        record_watched_run=record_watched_run,
        settings=settings,
        open_captures=open_captures,
    )


@pytest.mark.unit
async def test_run_watcher_recorder_promotes_a_begun_capture_while_idle() -> None:
    fake = _FakeRecordWatchedRun()
    recorder = _recorder(record_watched_run=fake)

    await recorder.observe_capture(_obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN))

    assert len(fake.calls) == 1
    command = fake.calls[0]
    assert command.capture_code == _CODE
    assert command.plan_id == _PLAN_ID
    assert command.trigger == "Monitor"
    assert command.monitor_source_id == RUN_WATCHER_MONITOR_SOURCE_ID


@pytest.mark.unit
async def test_run_watcher_recorder_does_not_repromote_a_begun_capture_while_open() -> None:
    fake = _FakeRecordWatchedRun()
    recorder = _recorder(record_watched_run=fake)

    begun = _obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN)
    await recorder.observe_capture(begun)
    await recorder.observe_capture(begun)

    assert len(fake.calls) == 1


@pytest.mark.unit
async def test_run_watcher_recorder_stays_idle_after_a_promotion_failure() -> None:
    fake = _FakeRecordWatchedRun(raises=RuntimeError("clearance refused"))
    recorder = _recorder(record_watched_run=fake)

    begun = _obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN)
    await recorder.observe_capture(begun)
    assert len(fake.calls) == 1

    fake.raises = None
    await recorder.observe_capture(begun)
    assert len(fake.calls) == 2


@pytest.mark.unit
async def test_run_watcher_recorder_logs_a_distinct_event_on_unauthorized() -> None:
    fake = _FakeRecordWatchedRun(raises=UnauthorizedError("not granted"))
    recorder = _recorder(record_watched_run=fake)

    begun = _obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN)
    with structlog.testing.capture_logs() as logs:
        await recorder.observe_capture(begun)

    events = [entry["event"] for entry in logs]
    assert "run_watcher.promotion_unauthorized" in events


@pytest.mark.unit
async def test_run_watcher_recorder_clears_on_ended_while_open() -> None:
    run_id = uuid4()
    fake = _FakeRecordWatchedRun(run_id=run_id)
    recorder = _recorder(record_watched_run=fake, open_captures={_CODE: run_id})

    await recorder.observe_capture(_obs(reported_status="Scan complete", phase=CapturePhase.ENDED))

    # Reopening after the close promotes again: proves the entry was
    # actually cleared, not merely left stale.
    await recorder.observe_capture(_obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN))
    assert len(fake.calls) == 1


@pytest.mark.unit
async def test_run_watcher_recorder_clears_on_aborted_while_open() -> None:
    run_id = uuid4()
    fake = _FakeRecordWatchedRun(run_id=run_id)
    recorder = _recorder(record_watched_run=fake, open_captures={_CODE: run_id})

    await recorder.observe_capture(_obs(reported_status="Scan aborted", phase=CapturePhase.ABORTED))
    await recorder.observe_capture(_obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN))

    assert len(fake.calls) == 1


@pytest.mark.unit
async def test_run_watcher_recorder_noop_on_ended_while_idle() -> None:
    fake = _FakeRecordWatchedRun()
    recorder = _recorder(record_watched_run=fake)

    await recorder.observe_capture(_obs(reported_status="Scan complete", phase=CapturePhase.ENDED))

    assert fake.calls == []


@pytest.mark.unit
async def test_run_watcher_recorder_noop_on_aborted_while_idle() -> None:
    fake = _FakeRecordWatchedRun()
    recorder = _recorder(record_watched_run=fake)

    await recorder.observe_capture(_obs(reported_status="Scan aborted", phase=CapturePhase.ABORTED))

    assert fake.calls == []


@pytest.mark.unit
@pytest.mark.parametrize("preopened", [False, True])
async def test_run_watcher_recorder_noop_on_progressing_regardless_of_state(
    preopened: bool,
) -> None:
    fake = _FakeRecordWatchedRun()
    open_captures = {_CODE: uuid4()} if preopened else None
    recorder = _recorder(record_watched_run=fake, open_captures=open_captures)

    await recorder.observe_capture(
        _obs(reported_status="Collecting projections", phase=CapturePhase.PROGRESSING)
    )

    assert fake.calls == []


@pytest.mark.unit
@pytest.mark.parametrize("preopened", [False, True])
async def test_run_watcher_recorder_noop_on_unrecognized_regardless_of_state(
    preopened: bool,
) -> None:
    fake = _FakeRecordWatchedRun()
    open_captures = {_CODE: uuid4()} if preopened else None
    recorder = _recorder(record_watched_run=fake, open_captures=open_captures)

    await recorder.observe_capture(_obs(reported_status="???", phase=CapturePhase.UNRECOGNIZED))

    assert fake.calls == []


@pytest.mark.unit
@pytest.mark.parametrize("preopened", [False, True])
async def test_run_watcher_recorder_noop_on_none_phase_regardless_of_state(
    preopened: bool,
) -> None:
    """The roadmap's explicit rule: a `phase is None` observation must
    neither promote nor clear the dedup state."""
    fake = _FakeRecordWatchedRun()
    open_captures = {_CODE: uuid4()} if preopened else None
    recorder = _recorder(record_watched_run=fake, open_captures=open_captures)

    await recorder.observe_capture(_obs(reported_status=None, phase=None))

    assert fake.calls == []


@pytest.mark.unit
async def test_run_watcher_recorder_is_a_pass_through_when_recording_disabled() -> None:
    """The hard no-regression requirement: with recording off, the fake
    handler is never called and the log output matches bare
    `observe_capture` exactly."""
    fake = _FakeRecordWatchedRun()
    recorder = _recorder(record_watched_run=fake, run_watcher_recording_enabled=False)
    observation = _obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN)

    with structlog.testing.capture_logs() as recorder_logs:
        await recorder.observe_capture(observation)
    with structlog.testing.capture_logs() as bare_logs:
        observe_capture(observation)

    assert fake.calls == []
    assert recorder_logs == bare_logs


@pytest.mark.unit
async def test_run_watcher_lifespan_seeds_open_captures_from_the_supplied_map() -> None:
    run_id = uuid4()
    fake = _FakeRecordWatchedRun()
    observer = _FakeObserver([_obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN)])
    deps = build_deps()

    async with run_watcher_lifespan(
        observer=observer,
        capture_codes=frozenset({_CODE}),
        deps=deps,
        record_watched_run=fake,
        open_captures={_CODE: run_id},
    ):
        await asyncio.sleep(0.02)

    assert fake.calls == []


@pytest.mark.unit
async def test_run_watcher_lifespan_rejects_a_handler_without_deps() -> None:
    with pytest.raises(ValueError, match="requires deps"):
        async with run_watcher_lifespan(
            observer=_FakeObserver([]),
            capture_codes=frozenset({_CODE}),
            record_watched_run=_FakeRecordWatchedRun(),
        ):
            pass


class _FakeListRuns:
    """Fake `list_runs` handler: returns one canned page per call, in order."""

    def __init__(self, pages: list[Any]) -> None:
        self._pages = pages
        self.queries: list[Any] = []

    async def __call__(
        self,
        query: Any,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Any:
        self.queries.append(query)
        return self._pages[len(self.queries) - 1]


def _summary_item(*, run_id: UUID, conduct_mode: str = "Recorded") -> RunSummaryItem:
    return RunSummaryItem(
        run_id=run_id,
        name="watched capture",
        plan_id=_PLAN_ID,
        subject_id=None,
        raid=None,
        status="Running",
        created_at=_NOW,
        running_since=_NOW,
        override_parameters_present=False,
        campaign_id=None,
        snr_limit=None,
        expected_observation_interval_seconds=None,
        conduct_mode=conduct_mode,
    )


async def _append_watched_run_started(deps: Any, *, run_id: UUID, capture_code: str) -> None:
    """Directly append a RunStarted(conduct_mode=RECORDED) event carrying
    the given capture_code as an external_ref, mirroring the shipped
    `test_initiator_tick_counts_a_watched_recorded_run_toward_max_in_flight`
    seeding pattern (record_watched_run's own decider is exercised
    elsewhere; this test only needs the resulting stream shape)."""
    event = RunStarted(
        run_id=run_id,
        name="watched capture",
        plan_id=_PLAN_ID,
        subject_id=None,
        occurred_at=_NOW,
        conduct_mode=ConductMode.RECORDED,
        external_refs=({"scheme": "capture-code", "value": capture_code},),
    )
    await deps.event_store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=uuid4(),
                command_name="seed",
                correlation_id=uuid4(),
                causation_id=None,
                principal_id=uuid4(),
            )
        ],
    )


@pytest.mark.unit
async def test_rebuild_open_captures_extracts_capture_code_from_external_refs() -> None:
    deps = build_deps(ids=[uuid4() for _ in range(10)])
    run_id = uuid4()
    await _append_watched_run_started(deps, run_id=run_id, capture_code=_CODE)
    list_runs = _FakeListRuns([RunListPage(items=[_summary_item(run_id=run_id)], next_cursor=None)])

    result = await rebuild_open_captures(deps, list_runs=list_runs)

    assert result == {_CODE: run_id}


@pytest.mark.unit
async def test_rebuild_open_captures_pages_through_multiple_pages() -> None:
    deps = build_deps(ids=[uuid4() for _ in range(10)])
    run_id_a = uuid4()
    run_id_b = uuid4()
    await _append_watched_run_started(deps, run_id=run_id_a, capture_code="code-a")
    await _append_watched_run_started(deps, run_id=run_id_b, capture_code="code-b")
    list_runs = _FakeListRuns(
        [
            RunListPage(items=[_summary_item(run_id=run_id_a)], next_cursor="more"),
            RunListPage(items=[_summary_item(run_id=run_id_b)], next_cursor=None),
        ]
    )

    result = await rebuild_open_captures(deps, list_runs=list_runs)

    assert result == {"code-a": run_id_a, "code-b": run_id_b}
    assert [q.cursor for q in list_runs.queries] == [None, "more"]


@pytest.mark.unit
async def test_rebuild_open_captures_skips_a_run_with_no_capture_code_ref() -> None:
    deps = build_deps(ids=[uuid4() for _ in range(10)])
    run_id = uuid4()
    event = RunStarted(
        run_id=run_id,
        name="watched capture, no ref",
        plan_id=_PLAN_ID,
        subject_id=None,
        occurred_at=_NOW,
        conduct_mode=ConductMode.RECORDED,
    )
    await deps.event_store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=uuid4(),
                command_name="seed",
                correlation_id=uuid4(),
                causation_id=None,
                principal_id=uuid4(),
            )
        ],
    )
    list_runs = _FakeListRuns([RunListPage(items=[_summary_item(run_id=run_id)], next_cursor=None)])

    result = await rebuild_open_captures(deps, list_runs=list_runs)

    assert result == {}
