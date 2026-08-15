"""Tests for the RunWitness shadow runtime (cora.api._run_witness).

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
import dataclasses
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
import structlog.testing

from cora.api._run_witness import (
    RUN_WITNESS_MONITOR_SOURCE_ID,
    RunWitnessRecorder,
    observe_capture,
    rebuild_open_captures,
    run_witness_lifespan,
    run_witness_loop,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import (
    ConductMode,
    InMemoryFeedHeartbeatStore,
    RunStarted,
    event_type_name,
    to_payload,
)
from cora.run.errors import UnauthorizedError
from cora.run.features.append_observations.command import AppendObservations
from cora.run.features.list_runs import RunListPage, RunSummaryItem
from cora.run.features.record_witnessed_run.command import RecordWitnessedRun
from cora.run.features.record_witnessed_run_outcome.command import RecordWitnessedRunOutcome
from cora.run.features.truncate_run.command import TruncateRun
from cora.run.ports.capture_observer import (
    AnyCaptureObservation,
    CaptureLifecycleObservation,
    CaptureObserverScope,
    CapturePhase,
    CaptureProgressObservation,
)
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
) -> CaptureLifecycleObservation:
    return CaptureLifecycleObservation(
        capture_code=capture_code,
        reported_status=reported_status,
        phase=phase,
        reach_tier=reach_tier,
        observed_at=observed_at,
        source_kind="EpicsPv",
        source_id="2bmb:TomoScan:ScanStatus",
    )


def _progress_obs(
    *,
    role: str = "images_saved",
    value: float = 1.0,
    commanded_total: float | None = None,
    capture_code: str = _CODE,
    observed_at: datetime | None = _NOW,
) -> CaptureProgressObservation:
    return CaptureProgressObservation(
        capture_code=capture_code,
        role=role,
        value=value,
        commanded_total=commanded_total,
        reach_tier=ReachTier.RELAYED,
        observed_at=observed_at,
        source_kind="EpicsPv",
        source_id=f"2bmb:TomoScan:{role}",
    )


class _FakeObserver:
    """Yields a fixed observation sequence once, then ends the stream."""

    def __init__(self, observations: list[AnyCaptureObservation]) -> None:
        self._observations = observations

    def observe(self, scope: CaptureObserverScope) -> AsyncGenerator[AnyCaptureObservation]:
        return self._drain()

    async def _drain(self) -> AsyncGenerator[AnyCaptureObservation]:
        for observation in self._observations:
            yield observation


class _FakeCaptureProgressFeeder:
    """Records every `offer()` / `flush_capture()` call, in order, so a
    test can assert both that they happened and their relative sequence
    against the recorder's own dispatch."""

    def __init__(self, *, raises_on_flush: Exception | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self._raises_on_flush = raises_on_flush

    def offer(self, observation: CaptureProgressObservation) -> None:
        self.calls.append(("offer", observation.capture_code))

    async def flush_capture(self, capture_code: str) -> None:
        self.calls.append(("flush", capture_code))
        if self._raises_on_flush is not None:
            raise self._raises_on_flush


class _BoomObserver:
    """Raises mid-iteration so the loop's outer resilience branch fires."""

    def observe(self, scope: CaptureObserverScope) -> AsyncGenerator[CaptureLifecycleObservation]:
        return self._drain()

    async def _drain(self) -> AsyncGenerator[CaptureLifecycleObservation]:
        raise RuntimeError("observer boom")
        yield  # pragma: no cover - unreachable, marks this body an async generator


@pytest.mark.unit
@pytest.mark.parametrize(
    ("phase", "expected_event"),
    [
        (CapturePhase.BEGUN, "run_witness.capture_begun"),
        (CapturePhase.PROGRESSING, "run_witness.capture_progressing"),
        (CapturePhase.ENDED, "run_witness.capture_ended"),
        (CapturePhase.ABORTED, "run_witness.capture_aborted"),
        (CapturePhase.UNRECOGNIZED, "run_witness.capture_unrecognized"),
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
    assert [entry["event"] for entry in logs] == ["run_witness.capture_unreached"]


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
async def test_run_witness_loop_is_a_no_op_for_empty_capture_codes() -> None:
    observer = _FakeObserver([_obs(reported_status="Scan complete", phase=CapturePhase.ENDED)])
    await run_witness_loop(observer=observer, capture_codes=frozenset())
    # No assertion needed beyond "returns": an observer never drained
    # would hang forever if the empty-scope short-circuit were missing.


@pytest.mark.unit
async def test_run_witness_loop_logs_every_observation_in_sequence() -> None:
    observer = _FakeObserver(
        [
            _obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN),
            _obs(reported_status="Collecting projections", phase=CapturePhase.PROGRESSING),
            _obs(reported_status="Scan complete", phase=CapturePhase.ENDED),
        ]
    )
    task = asyncio.create_task(
        run_witness_loop(observer=observer, capture_codes=frozenset({_CODE}))
    )
    with structlog.testing.capture_logs() as logs:
        await asyncio.sleep(0.05)  # one full drain of the fixed sequence
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    events = [entry["event"] for entry in logs]
    assert events == [
        "run_witness.capture_begun",
        "run_witness.capture_progressing",
        "run_witness.capture_ended",
    ]


@pytest.mark.unit
async def test_run_witness_loop_survives_an_observer_that_raises() -> None:
    """The outer resilience branch logs and reconnects rather than the
    loop propagating the exception and dying silently."""
    task = asyncio.create_task(
        run_witness_loop(
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
    assert "run_witness.iteration_failed" in events


@pytest.mark.unit
async def test_run_witness_loop_offers_a_progress_observation_to_the_feeder() -> None:
    """A `CaptureProgressObservation` reaches `feeder.offer()`; with no
    `recorder` supplied (as here), it reaches nothing else."""
    feeder = _FakeCaptureProgressFeeder()
    observer = _FakeObserver([_progress_obs(role="images_saved", value=3.0)])
    task = asyncio.create_task(
        run_witness_loop(
            observer=observer,
            capture_codes=frozenset({_CODE}),
            feeder=feeder,  # type: ignore[arg-type]
        )
    )
    await asyncio.sleep(0.02)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert feeder.calls == [("offer", _CODE)]


@pytest.mark.unit
async def test_run_witness_loop_a_progress_observation_with_no_feeder_is_a_noop() -> None:
    """`feeder=None` (recording off) makes a progress observation a
    silent no-op, same posture as `recorder=None` for a lifecycle one."""
    observer = _FakeObserver([_progress_obs()])
    task = asyncio.create_task(
        run_witness_loop(observer=observer, capture_codes=frozenset({_CODE}))
    )
    await asyncio.sleep(0.02)  # would hang or crash if this branch mishandled feeder=None
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


@pytest.mark.unit
async def test_run_witness_loop_flushes_progress_before_the_recorder_acts_on_a_terminal() -> None:
    """A BEGUN/ENDED/ABORTED observation must flush the capture's
    buffered progress trail BEFORE the recorder's own dispatch, so the
    trail is attributed to the Run before it can close or be replaced."""
    order: list[str] = []

    class _OrderingFeeder(_FakeCaptureProgressFeeder):
        async def flush_capture(self, capture_code: str) -> None:
            order.append("flush")

    class _OrderingRecorder:
        async def observe_capture(self, observation: CaptureLifecycleObservation) -> None:
            order.append("observe")

    observer = _FakeObserver([_obs(reported_status="Scan complete", phase=CapturePhase.ENDED)])
    task = asyncio.create_task(
        run_witness_loop(
            observer=observer,
            capture_codes=frozenset({_CODE}),
            recorder=_OrderingRecorder(),  # type: ignore[arg-type]
            feeder=_OrderingFeeder(),  # type: ignore[arg-type]
        )
    )
    await asyncio.sleep(0.02)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert order == ["flush", "observe"]


@pytest.mark.unit
async def test_run_witness_loop_does_not_flush_on_a_non_flush_trigger_phase() -> None:
    """PROGRESSING is not in `_FLUSH_TRIGGER_PHASES`: the recorder's own
    dedup state is untouched by it, so there is nothing to flush ahead
    of."""
    feeder = _FakeCaptureProgressFeeder()
    observer = _FakeObserver(
        [_obs(reported_status="Collecting projections", phase=CapturePhase.PROGRESSING)]
    )
    task = asyncio.create_task(
        run_witness_loop(
            observer=observer,
            capture_codes=frozenset({_CODE}),
            feeder=feeder,  # type: ignore[arg-type]
        )
    )
    await asyncio.sleep(0.02)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert feeder.calls == []


@pytest.mark.unit
async def test_run_witness_loop_survives_a_flush_failure_and_still_dispatches_to_recorder() -> None:
    """A flush failure is logged and swallowed; the recorder still gets
    the observation, matching the loop's own record_failed posture."""
    feeder = _FakeCaptureProgressFeeder(raises_on_flush=RuntimeError("flush boom"))
    recorded: list[str] = []

    class _RecordingRecorder:
        async def observe_capture(self, observation: CaptureLifecycleObservation) -> None:
            recorded.append(observation.capture_code)

    observer = _FakeObserver([_obs(reported_status="Scan complete", phase=CapturePhase.ENDED)])
    task = asyncio.create_task(
        run_witness_loop(
            observer=observer,
            capture_codes=frozenset({_CODE}),
            recorder=_RecordingRecorder(),  # type: ignore[arg-type]
            feeder=feeder,  # type: ignore[arg-type]
        )
    )
    with structlog.testing.capture_logs() as logs:
        await asyncio.sleep(0.02)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    events = [entry["event"] for entry in logs]
    assert "run_witness.progress_flush_failed" in events
    assert recorded == [_CODE]


@pytest.mark.unit
async def test_lifespan_is_a_no_op_when_no_capture_codes_configured() -> None:
    entered = False
    async with run_witness_lifespan(observer=_FakeObserver([]), capture_codes=frozenset()):
        entered = True
    assert entered


@pytest.mark.unit
async def test_lifespan_spawns_and_cleanly_cancels_the_background_task() -> None:
    observer = _FakeObserver([_obs(reported_status="Scan complete", phase=CapturePhase.ENDED)])
    with structlog.testing.capture_logs() as logs:
        async with run_witness_lifespan(observer=observer, capture_codes=frozenset({_CODE})):
            await asyncio.sleep(0.02)
    events = [entry["event"] for entry in logs]
    assert "run_witness.capture_ended" in events


class _FakeRecordWitnessedRun:
    """Fake `record_witnessed_run` handler: records every call, returns a
    fixed run_id, or raises a configured exception instead."""

    def __init__(self, *, run_id: UUID | None = None, raises: Exception | None = None) -> None:
        self.run_id = run_id if run_id is not None else uuid4()
        self.raises = raises
        self.calls: list[RecordWitnessedRun] = []

    async def __call__(
        self,
        command: RecordWitnessedRun,
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


class _FakeRecordWitnessedRunOutcome:
    """Fake `record_witnessed_run_outcome` handler: records every call,
    returns None, or raises a configured exception instead."""

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.raises = raises
        self.calls: list[RecordWitnessedRunOutcome] = []

    async def __call__(
        self,
        command: RecordWitnessedRunOutcome,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        self.calls.append(command)
        if self.raises is not None:
            raise self.raises


class _FakeTruncateRun:
    """Fake `truncate_run` handler: records every call, returns None, or
    raises a configured exception instead."""

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.raises = raises
        self.calls: list[TruncateRun] = []

    async def __call__(
        self,
        command: TruncateRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        self.calls.append(command)
        if self.raises is not None:
            raise self.raises


class _FakeAppendObservations:
    """Fake `append_observations` handler: records every call."""

    def __init__(self) -> None:
        self.calls: list[AppendObservations] = []

    async def __call__(
        self,
        command: AppendObservations,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int:
        self.calls.append(command)
        return len(command.entries)


def _recorder(
    *,
    record_witnessed_run: _FakeRecordWitnessedRun,
    record_witnessed_run_outcome: _FakeRecordWitnessedRunOutcome | None = None,
    truncate_run: _FakeTruncateRun | None = None,
    run_witness_recording_enabled: bool = True,
    capture_watch_plan_id: UUID | None = _PLAN_ID,
    open_captures: dict[str, UUID] | None = None,
) -> RunWitnessRecorder:
    settings = Settings(  # type: ignore[call-arg]
        run_witness_recording_enabled=run_witness_recording_enabled,
        capture_watch_plan_id=capture_watch_plan_id,
    )
    outcome = record_witnessed_run_outcome or _FakeRecordWitnessedRunOutcome()
    truncate = truncate_run or _FakeTruncateRun()
    return RunWitnessRecorder(
        deps=build_deps(ids=[uuid4() for _ in range(10)]),
        record_witnessed_run=record_witnessed_run,
        record_witnessed_run_outcome=outcome,
        truncate_run=truncate,
        settings=settings,
        open_captures=open_captures,
    )


@pytest.mark.unit
async def test_run_witness_recorder_promotes_a_begun_capture_while_idle() -> None:
    fake = _FakeRecordWitnessedRun()
    recorder = _recorder(record_witnessed_run=fake)

    await recorder.observe_capture(_obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN))

    assert len(fake.calls) == 1
    command = fake.calls[0]
    assert command.capture_code == _CODE
    assert command.plan_id == _PLAN_ID
    assert command.trigger == "Monitor"
    assert command.monitor_source_id == RUN_WITNESS_MONITOR_SOURCE_ID


@pytest.mark.unit
async def test_run_witness_recorder_truncates_stale_run_and_repromotes_on_a_second_begun() -> None:
    """A second BEGUN for a code that is already open means the previous
    terminal was missed: truncate the stale Run (interrupted_at=None,
    the moment it actually ended is unknown), then promote a new one."""
    stale_run_id = uuid4()
    fresh_run_id = uuid4()
    genesis = _FakeRecordWitnessedRun(run_id=stale_run_id)
    truncate = _FakeTruncateRun()
    recorder = _recorder(record_witnessed_run=genesis, truncate_run=truncate)

    begun = _obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN)
    await recorder.observe_capture(begun)

    genesis.run_id = fresh_run_id
    await recorder.observe_capture(begun)

    assert len(genesis.calls) == 2
    assert len(truncate.calls) == 1
    truncate_command = truncate.calls[0]
    assert truncate_command.run_id == stale_run_id
    assert truncate_command.interrupted_at is None


@pytest.mark.unit
async def test_run_witness_recorder_promotes_even_when_the_stale_truncate_fails() -> None:
    """The new capture is a real fact regardless of whether the stale Run
    could be closed: a truncate failure must not block the promotion."""
    genesis = _FakeRecordWitnessedRun()
    truncate = _FakeTruncateRun(raises=RuntimeError("Run already terminal"))
    recorder = _recorder(record_witnessed_run=genesis, truncate_run=truncate)

    begun = _obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN)
    await recorder.observe_capture(begun)
    await recorder.observe_capture(begun)

    assert len(genesis.calls) == 2
    assert len(truncate.calls) == 1


@pytest.mark.unit
async def test_run_witness_recorder_stays_idle_after_a_promotion_failure() -> None:
    fake = _FakeRecordWitnessedRun(raises=RuntimeError("clearance refused"))
    recorder = _recorder(record_witnessed_run=fake)

    begun = _obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN)
    await recorder.observe_capture(begun)
    assert len(fake.calls) == 1

    fake.raises = None
    await recorder.observe_capture(begun)
    assert len(fake.calls) == 2


@pytest.mark.unit
async def test_run_witness_recorder_logs_a_distinct_event_on_unauthorized() -> None:
    fake = _FakeRecordWitnessedRun(raises=UnauthorizedError("not granted"))
    recorder = _recorder(record_witnessed_run=fake)

    begun = _obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN)
    with structlog.testing.capture_logs() as logs:
        await recorder.observe_capture(begun)

    events = [entry["event"] for entry in logs]
    assert "run_witness.promotion_unauthorized" in events


@pytest.mark.unit
async def test_run_witness_recorder_records_ended_outcome_while_open() -> None:
    run_id = uuid4()
    genesis = _FakeRecordWitnessedRun(run_id=run_id)
    outcome = _FakeRecordWitnessedRunOutcome()
    recorder = _recorder(
        record_witnessed_run=genesis,
        record_witnessed_run_outcome=outcome,
        open_captures={_CODE: run_id},
    )

    await recorder.observe_capture(_obs(reported_status="Scan complete", phase=CapturePhase.ENDED))

    assert len(outcome.calls) == 1
    command = outcome.calls[0]
    assert command.run_id == run_id
    assert command.capture_code == _CODE
    assert command.observed_phase is CapturePhase.ENDED
    assert command.observed_at == _NOW
    assert command.trigger == "Monitor"
    assert command.monitor_source_id == RUN_WITNESS_MONITOR_SOURCE_ID

    # Reopening after the close promotes again: proves the entry was
    # actually cleared, not merely left stale.
    await recorder.observe_capture(_obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN))
    assert len(genesis.calls) == 1


@pytest.mark.unit
async def test_run_witness_recorder_records_aborted_outcome_while_open() -> None:
    run_id = uuid4()
    genesis = _FakeRecordWitnessedRun(run_id=run_id)
    outcome = _FakeRecordWitnessedRunOutcome()
    recorder = _recorder(
        record_witnessed_run=genesis,
        record_witnessed_run_outcome=outcome,
        open_captures={_CODE: run_id},
    )

    await recorder.observe_capture(_obs(reported_status="Scan aborted", phase=CapturePhase.ABORTED))
    assert outcome.calls[0].observed_phase is CapturePhase.ABORTED

    await recorder.observe_capture(_obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN))
    assert len(genesis.calls) == 1


@pytest.mark.unit
async def test_run_witness_recorder_leaves_entry_open_after_a_failed_outcome() -> None:
    """A failed outcome write leaves the entry open; the next BEGUN
    truncates it (recovering via the same path as a missed terminal)
    rather than the failure being silently swallowed."""
    run_id = uuid4()
    genesis = _FakeRecordWitnessedRun()
    outcome = _FakeRecordWitnessedRunOutcome(raises=RuntimeError("append failed"))
    truncate = _FakeTruncateRun()
    recorder = _recorder(
        record_witnessed_run=genesis,
        record_witnessed_run_outcome=outcome,
        truncate_run=truncate,
        open_captures={_CODE: run_id},
    )

    await recorder.observe_capture(_obs(reported_status="Scan complete", phase=CapturePhase.ENDED))
    await recorder.observe_capture(_obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN))

    assert len(truncate.calls) == 1
    assert truncate.calls[0].run_id == run_id
    assert len(genesis.calls) == 1


@pytest.mark.unit
async def test_run_witness_recorder_logs_a_distinct_event_on_outcome_unauthorized() -> None:
    run_id = uuid4()
    outcome = _FakeRecordWitnessedRunOutcome(raises=UnauthorizedError("not granted"))
    recorder = _recorder(
        record_witnessed_run=_FakeRecordWitnessedRun(),
        record_witnessed_run_outcome=outcome,
        open_captures={_CODE: run_id},
    )

    with structlog.testing.capture_logs() as logs:
        await recorder.observe_capture(
            _obs(reported_status="Scan complete", phase=CapturePhase.ENDED)
        )

    events = [entry["event"] for entry in logs]
    assert "run_witness.outcome_unauthorized" in events


# ---------- observe_progress / capture_progress_snapshot retention ----------


@pytest.mark.unit
async def test_observe_progress_then_ended_carries_a_snapshot_on_the_outcome() -> None:
    run_id = uuid4()
    outcome = _FakeRecordWitnessedRunOutcome()
    recorder = _recorder(
        record_witnessed_run=_FakeRecordWitnessedRun(),
        record_witnessed_run_outcome=outcome,
        open_captures={_CODE: run_id},
    )

    recorder.observe_progress(
        _progress_obs(role="images_collected", value=2987.0, commanded_total=3000.0)
    )
    recorder.observe_progress(
        _progress_obs(role="images_saved", value=2987.0, commanded_total=3000.0)
    )
    await recorder.observe_capture(_obs(reported_status="Scan complete", phase=CapturePhase.ENDED))

    assert len(outcome.calls) == 1
    snapshot = outcome.calls[0].capture_progress_snapshot
    assert snapshot is not None
    assert snapshot.collected_count == 2987.0
    assert snapshot.collected_total == 3000.0
    assert snapshot.saved_count == 2987.0
    assert snapshot.saved_total == 3000.0


@pytest.mark.unit
async def test_observe_progress_one_role_only_still_builds_a_snapshot() -> None:
    """Both roles compose into one snapshot; a role that never reported
    stays `None` inside it rather than blocking the other."""
    run_id = uuid4()
    outcome = _FakeRecordWitnessedRunOutcome()
    recorder = _recorder(
        record_witnessed_run=_FakeRecordWitnessedRun(),
        record_witnessed_run_outcome=outcome,
        open_captures={_CODE: run_id},
    )

    recorder.observe_progress(_progress_obs(role="images_collected", value=42.0))
    await recorder.observe_capture(_obs(reported_status="Scan complete", phase=CapturePhase.ENDED))

    snapshot = outcome.calls[0].capture_progress_snapshot
    assert snapshot is not None
    assert snapshot.collected_count == 42.0
    assert snapshot.saved_count is None


@pytest.mark.unit
async def test_ended_with_nothing_retained_carries_no_snapshot() -> None:
    """Absence must read as 'no reading reached CORA', never as an
    all-None snapshot: the whole object is None."""
    run_id = uuid4()
    outcome = _FakeRecordWitnessedRunOutcome()
    recorder = _recorder(
        record_witnessed_run=_FakeRecordWitnessedRun(),
        record_witnessed_run_outcome=outcome,
        open_captures={_CODE: run_id},
    )

    await recorder.observe_capture(_obs(reported_status="Scan complete", phase=CapturePhase.ENDED))

    assert outcome.calls[0].capture_progress_snapshot is None


@pytest.mark.unit
async def test_observe_progress_is_a_noop_when_recording_disabled() -> None:
    run_id = uuid4()
    outcome = _FakeRecordWitnessedRunOutcome()
    recorder = _recorder(
        record_witnessed_run=_FakeRecordWitnessedRun(),
        record_witnessed_run_outcome=outcome,
        open_captures={_CODE: run_id},
        run_witness_recording_enabled=False,
    )

    recorder.observe_progress(_progress_obs(role="images_collected", value=2987.0))
    await recorder.observe_capture(_obs(reported_status="Scan complete", phase=CapturePhase.ENDED))

    # Shadow mode: observe_capture itself no-ops before building any
    # command, so there is nothing to assert on outcome.calls directly;
    # the point is that retaining progress in shadow mode does not crash
    # and leaves no state to leak into a later recording-enabled run.
    assert outcome.calls == []


@pytest.mark.unit
async def test_promote_clears_progress_retained_for_a_different_prior_capture() -> None:
    """A stale capture's retained progress must not ride onto the NEW
    capture `_promote` is about to open for the same code."""
    stale_run_id = uuid4()
    fresh_run_id = uuid4()
    genesis = _FakeRecordWitnessedRun(run_id=fresh_run_id)
    outcome = _FakeRecordWitnessedRunOutcome()
    recorder = _recorder(
        record_witnessed_run=genesis,
        record_witnessed_run_outcome=outcome,
        truncate_run=_FakeTruncateRun(),
        open_captures={_CODE: stale_run_id},
    )

    recorder.observe_progress(_progress_obs(role="images_collected", value=999.0))
    await recorder.observe_capture(_obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN))
    await recorder.observe_capture(_obs(reported_status="Scan complete", phase=CapturePhase.ENDED))

    assert outcome.calls[0].run_id == fresh_run_id
    assert outcome.calls[0].capture_progress_snapshot is None


@pytest.mark.unit
async def test_truncate_then_promote_never_leaks_the_stale_captures_progress() -> None:
    """Black-box companion to `test_promote_clears_progress_retained_for_a_different_prior_capture`:
    the truncate-then-promote pair (both real state-mutation sites) must
    together prevent a stale capture's progress from ever reaching the
    NEW capture's own eventual terminal, regardless of which of the two
    sites is doing the clearing."""
    stale_run_id = uuid4()
    fresh_run_id = uuid4()
    outcome = _FakeRecordWitnessedRunOutcome()
    recorder = _recorder(
        record_witnessed_run=_FakeRecordWitnessedRun(run_id=fresh_run_id),
        record_witnessed_run_outcome=outcome,
        truncate_run=_FakeTruncateRun(),
        open_captures={_CODE: stale_run_id},
    )

    recorder.observe_progress(_progress_obs(role="images_collected", value=999.0))
    await recorder.observe_capture(_obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN))
    recorder.observe_progress(_progress_obs(role="images_collected", value=17.0))
    await recorder.observe_capture(_obs(reported_status="Scan complete", phase=CapturePhase.ENDED))

    assert outcome.calls[0].run_id == fresh_run_id
    snapshot = outcome.calls[0].capture_progress_snapshot
    assert snapshot is not None
    assert snapshot.collected_count == 17.0


@pytest.mark.unit
async def test_record_outcome_retains_progress_across_a_failed_attempt_for_a_retry() -> None:
    """A failed outcome write leaves `_open_captures` populated so the
    next attempt for the same code can retry; retained progress must
    survive that failure too, since it describes the same still-open
    capture, not the failed write."""
    run_id = uuid4()

    class _FailOnceThenSucceed:
        def __init__(self) -> None:
            self.calls: list[RecordWitnessedRunOutcome] = []
            self._remaining_failures = 1

        async def __call__(
            self,
            command: RecordWitnessedRunOutcome,
            *,
            principal_id: UUID,
            correlation_id: UUID,
            causation_id: UUID | None = None,
            surface_id: UUID = NIL_SENTINEL_ID,
        ) -> None:
            self.calls.append(command)
            if self._remaining_failures > 0:
                self._remaining_failures -= 1
                raise RuntimeError("append failed")

    outcome = _FailOnceThenSucceed()
    recorder = _recorder(
        record_witnessed_run=_FakeRecordWitnessedRun(),
        record_witnessed_run_outcome=outcome,  # type: ignore[arg-type]
        open_captures={_CODE: run_id},
    )

    recorder.observe_progress(_progress_obs(role="images_collected", value=2987.0))
    ended = _obs(reported_status="Scan complete", phase=CapturePhase.ENDED)
    await recorder.observe_capture(ended)  # fails; entry stays open
    await recorder.observe_capture(ended)  # retried, same observation

    assert len(outcome.calls) == 2
    snapshot = outcome.calls[1].capture_progress_snapshot
    assert snapshot is not None
    assert snapshot.collected_count == 2987.0


@pytest.mark.unit
async def test_run_witness_recorder_noop_on_ended_while_idle() -> None:
    genesis = _FakeRecordWitnessedRun()
    outcome = _FakeRecordWitnessedRunOutcome()
    recorder = _recorder(record_witnessed_run=genesis, record_witnessed_run_outcome=outcome)

    await recorder.observe_capture(_obs(reported_status="Scan complete", phase=CapturePhase.ENDED))

    assert genesis.calls == []
    assert outcome.calls == []


@pytest.mark.unit
async def test_run_witness_recorder_noop_on_aborted_while_idle() -> None:
    genesis = _FakeRecordWitnessedRun()
    outcome = _FakeRecordWitnessedRunOutcome()
    recorder = _recorder(record_witnessed_run=genesis, record_witnessed_run_outcome=outcome)

    await recorder.observe_capture(_obs(reported_status="Scan aborted", phase=CapturePhase.ABORTED))

    assert genesis.calls == []
    assert outcome.calls == []


@pytest.mark.unit
@pytest.mark.parametrize("preopened", [False, True])
async def test_run_witness_recorder_noop_on_progressing_regardless_of_state(
    preopened: bool,
) -> None:
    fake = _FakeRecordWitnessedRun()
    open_captures = {_CODE: uuid4()} if preopened else None
    recorder = _recorder(record_witnessed_run=fake, open_captures=open_captures)

    await recorder.observe_capture(
        _obs(reported_status="Collecting projections", phase=CapturePhase.PROGRESSING)
    )

    assert fake.calls == []


@pytest.mark.unit
@pytest.mark.parametrize("preopened", [False, True])
async def test_run_witness_recorder_noop_on_unrecognized_regardless_of_state(
    preopened: bool,
) -> None:
    fake = _FakeRecordWitnessedRun()
    open_captures = {_CODE: uuid4()} if preopened else None
    recorder = _recorder(record_witnessed_run=fake, open_captures=open_captures)

    await recorder.observe_capture(_obs(reported_status="???", phase=CapturePhase.UNRECOGNIZED))

    assert fake.calls == []


@pytest.mark.unit
@pytest.mark.parametrize("preopened", [False, True])
async def test_run_witness_recorder_noop_on_none_phase_regardless_of_state(
    preopened: bool,
) -> None:
    """The roadmap's explicit rule: a `phase is None` observation must
    neither promote nor clear the dedup state."""
    fake = _FakeRecordWitnessedRun()
    open_captures = {_CODE: uuid4()} if preopened else None
    recorder = _recorder(record_witnessed_run=fake, open_captures=open_captures)

    await recorder.observe_capture(_obs(reported_status=None, phase=None))

    assert fake.calls == []


@pytest.mark.unit
async def test_open_captures_reflects_the_seeded_map() -> None:
    run_id = uuid4()
    recorder = _recorder(
        record_witnessed_run=_FakeRecordWitnessedRun(), open_captures={_CODE: run_id}
    )

    assert recorder.open_captures() == {_CODE: run_id}


@pytest.mark.unit
async def test_open_captures_is_empty_when_nothing_is_open() -> None:
    recorder = _recorder(record_witnessed_run=_FakeRecordWitnessedRun())

    assert recorder.open_captures() == {}


@pytest.mark.unit
async def test_open_captures_reflects_a_promotion() -> None:
    run_id = uuid4()
    fake = _FakeRecordWitnessedRun(run_id=run_id)
    recorder = _recorder(record_witnessed_run=fake)

    await recorder.observe_capture(_obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN))

    assert recorder.open_captures() == {_CODE: run_id}


@pytest.mark.unit
async def test_open_captures_returns_a_copy_not_a_live_reference() -> None:
    """The caller must not be able to mutate this recorder's own dedup
    state through the returned mapping."""
    recorder = _recorder(
        record_witnessed_run=_FakeRecordWitnessedRun(), open_captures={_CODE: uuid4()}
    )

    snapshot = recorder.open_captures()
    snapshot["injected"] = uuid4()

    assert "injected" not in recorder.open_captures()


@pytest.mark.unit
async def test_run_witness_recorder_is_a_pass_through_when_recording_disabled() -> None:
    """The hard no-regression requirement: with recording off, the fake
    handler is never called and the log output matches bare
    `observe_capture` exactly."""
    fake = _FakeRecordWitnessedRun()
    recorder = _recorder(record_witnessed_run=fake, run_witness_recording_enabled=False)
    observation = _obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN)

    with structlog.testing.capture_logs() as recorder_logs:
        await recorder.observe_capture(observation)
    with structlog.testing.capture_logs() as bare_logs:
        observe_capture(observation)

    assert fake.calls == []
    assert recorder_logs == bare_logs


@pytest.mark.unit
async def test_run_witness_lifespan_seeds_open_captures_from_the_supplied_map() -> None:
    """A code seeded as open at construction reads OPEN: a BEGUN for it
    goes through the truncate-then-promote recovery path rather than a
    blind idle-promote, proving the supplied map was actually consulted."""
    run_id = uuid4()
    genesis = _FakeRecordWitnessedRun()
    truncate = _FakeTruncateRun()
    observer = _FakeObserver([_obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN)])
    deps = dataclasses.replace(
        build_deps(ids=[uuid4() for _ in range(10)]),
        settings=Settings(  # type: ignore[call-arg]
            run_witness_recording_enabled=True,
            capture_watch_plan_id=_PLAN_ID,
        ),
    )

    async with run_witness_lifespan(
        observer=observer,
        capture_codes=frozenset({_CODE}),
        deps=deps,
        record_witnessed_run=genesis,
        record_witnessed_run_outcome=_FakeRecordWitnessedRunOutcome(),
        truncate_run=truncate,
        open_captures={_CODE: run_id},
    ):
        await asyncio.sleep(0.02)

    assert len(truncate.calls) == 1
    assert truncate.calls[0].run_id == run_id
    assert len(genesis.calls) == 1


@pytest.mark.unit
async def test_run_witness_lifespan_rejects_a_handler_without_deps() -> None:
    with pytest.raises(ValueError, match="requires deps"):
        async with run_witness_lifespan(
            observer=_FakeObserver([]),
            capture_codes=frozenset({_CODE}),
            record_witnessed_run=_FakeRecordWitnessedRun(),
        ):
            pass


@pytest.mark.unit
async def test_run_witness_lifespan_rejects_progress_recording_without_witness_handler() -> None:
    with pytest.raises(ValueError, match="capture_progress_recording_enabled requires"):
        async with run_witness_lifespan(
            observer=_FakeObserver([]),
            capture_codes=frozenset({_CODE}),
            capture_progress_recording_enabled=True,
        ):
            pass


@pytest.mark.unit
async def test_run_witness_lifespan_rejects_progress_recording_without_append_obs() -> None:
    deps = dataclasses.replace(
        build_deps(ids=[uuid4() for _ in range(5)]),
        settings=Settings(  # type: ignore[call-arg]
            run_witness_recording_enabled=True,
            capture_watch_plan_id=_PLAN_ID,
        ),
    )
    with pytest.raises(ValueError, match="append_observations"):
        async with run_witness_lifespan(
            observer=_FakeObserver([]),
            capture_codes=frozenset({_CODE}),
            deps=deps,
            record_witnessed_run=_FakeRecordWitnessedRun(),
            record_witnessed_run_outcome=_FakeRecordWitnessedRunOutcome(),
            truncate_run=_FakeTruncateRun(),
            capture_progress_recording_enabled=True,
        ):
            pass


@pytest.mark.unit
async def test_run_witness_lifespan_with_progress_recording_writes_observations() -> None:
    """End-to-end wiring check: a BEGUN promotes, a buffered progress
    reading survives to the periodic flush tick, and the flush writes
    through the real `AppendObservations` fake against the promoted
    run_id -- proving the feeder is actually constructed and started,
    not just accepted as a parameter."""
    run_id = uuid4()
    genesis = _FakeRecordWitnessedRun(run_id=run_id)
    append_observations = _FakeAppendObservations()
    heartbeats = InMemoryFeedHeartbeatStore()
    observer = _FakeObserver(
        [
            _obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN),
            _progress_obs(role="images_saved", value=5.0),
        ]
    )
    deps = dataclasses.replace(
        build_deps(ids=[uuid4() for _ in range(20)]),
        settings=Settings(  # type: ignore[call-arg]
            run_witness_recording_enabled=True,
            capture_watch_plan_id=_PLAN_ID,
        ),
    )

    async with run_witness_lifespan(
        observer=observer,
        capture_codes=frozenset({_CODE}),
        deps=deps,
        record_witnessed_run=genesis,
        record_witnessed_run_outcome=_FakeRecordWitnessedRunOutcome(),
        truncate_run=_FakeTruncateRun(),
        append_observations=append_observations,
        feed_heartbeat_store=heartbeats,
        capture_progress_recording_enabled=True,
        capture_progress_flush_tick_seconds=0.01,
    ):
        await asyncio.sleep(0.05)  # promote, buffer, then at least one flush tick

    assert len(genesis.calls) == 1
    assert len(append_observations.calls) == 1
    assert append_observations.calls[0].run_id == run_id
    assert append_observations.calls[0].entries[0].channel_name == "images_saved"
    assert len(heartbeats.all()) >= 1


@pytest.mark.unit
async def test_run_witness_lifespan_refuses_progress_recording_in_shadow_mode() -> None:
    """Defensive, mirrors `_promote`'s own capture_watch_plan_id check:
    the boot-time gate already refuses to start the app in this state,
    but a direct in-process caller that sets `run_witness_recording_enabled
    =False` on `deps.settings` while still passing
    `capture_progress_recording_enabled=True` must not get a feeder
    that writes real rows while the recorder stays shadow-only."""
    deps = dataclasses.replace(
        build_deps(ids=[uuid4() for _ in range(10)]),
        settings=Settings(  # type: ignore[call-arg]
            run_witness_recording_enabled=False,
            capture_watch_plan_id=_PLAN_ID,
        ),
    )
    with pytest.raises(ValueError, match="run_witness_recording_enabled=True"):
        async with run_witness_lifespan(
            observer=_FakeObserver([]),
            capture_codes=frozenset({_CODE}),
            deps=deps,
            record_witnessed_run=_FakeRecordWitnessedRun(),
            record_witnessed_run_outcome=_FakeRecordWitnessedRunOutcome(),
            truncate_run=_FakeTruncateRun(),
            append_observations=_FakeAppendObservations(),
            feed_heartbeat_store=InMemoryFeedHeartbeatStore(),
            capture_progress_recording_enabled=True,
        ):
            pass


@pytest.mark.unit
async def test_run_witness_lifespan_flushes_buffered_progress_on_shutdown() -> None:
    """A reading buffered right before teardown must not be silently
    lost: the lifespan's `finally` does one best-effort final flush
    after cancelling both background tasks."""
    run_id = uuid4()
    genesis = _FakeRecordWitnessedRun(run_id=run_id)
    append_observations = _FakeAppendObservations()
    observer = _FakeObserver(
        [
            _obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN),
            _progress_obs(role="images_saved", value=9.0),
        ]
    )
    deps = dataclasses.replace(
        build_deps(ids=[uuid4() for _ in range(20)]),
        settings=Settings(  # type: ignore[call-arg]
            run_witness_recording_enabled=True,
            capture_watch_plan_id=_PLAN_ID,
        ),
    )

    async with run_witness_lifespan(
        observer=observer,
        capture_codes=frozenset({_CODE}),
        deps=deps,
        record_witnessed_run=genesis,
        record_witnessed_run_outcome=_FakeRecordWitnessedRunOutcome(),
        truncate_run=_FakeTruncateRun(),
        append_observations=append_observations,
        feed_heartbeat_store=InMemoryFeedHeartbeatStore(),
        capture_progress_recording_enabled=True,
        # Long enough that the periodic loop never ticks on its own;
        # only the shutdown-time final flush can be responsible for
        # any write this test observes.
        capture_progress_flush_tick_seconds=60.0,
    ):
        await asyncio.sleep(0.02)  # promote + buffer, no time for a periodic tick

    assert len(append_observations.calls) == 1
    assert append_observations.calls[0].run_id == run_id
    assert append_observations.calls[0].entries[0].channel_name == "images_saved"


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


def _summary_item(*, run_id: UUID, conduct_mode: str = "Witnessed") -> RunSummaryItem:
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


async def _append_witnessed_run_started(deps: Any, *, run_id: UUID, capture_code: str) -> None:
    """Directly append a RunStarted(conduct_mode=WITNESSED) event carrying
    the given capture_code as an external_ref, mirroring the shipped
    `test_initiator_tick_counts_a_witnessed_run_toward_max_in_flight`
    seeding pattern (record_witnessed_run's own decider is exercised
    elsewhere; this test only needs the resulting stream shape)."""
    event = RunStarted(
        run_id=run_id,
        name="watched capture",
        plan_id=_PLAN_ID,
        subject_id=None,
        occurred_at=_NOW,
        conduct_mode=ConductMode.WITNESSED,
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
    await _append_witnessed_run_started(deps, run_id=run_id, capture_code=_CODE)
    list_runs = _FakeListRuns([RunListPage(items=[_summary_item(run_id=run_id)], next_cursor=None)])

    result = await rebuild_open_captures(deps, list_runs=list_runs)

    assert result == {_CODE: run_id}


@pytest.mark.unit
async def test_rebuild_open_captures_pages_through_multiple_pages() -> None:
    deps = build_deps(ids=[uuid4() for _ in range(10)])
    run_id_a = uuid4()
    run_id_b = uuid4()
    await _append_witnessed_run_started(deps, run_id=run_id_a, capture_code="code-a")
    await _append_witnessed_run_started(deps, run_id=run_id_b, capture_code="code-b")
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
        conduct_mode=ConductMode.WITNESSED,
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
