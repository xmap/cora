"""End-to-end replay tests: real `ControlPortCaptureObserver` classification
feeding a real `RunWitnessRecorder` (and, for the progress-role tests, a
real `CaptureProgressFeeder`), driven by the actual literal sequence
measured on arcturus (2026-08-14, 431 real captures) rather than
pre-classified phases.

Unlike `test_capture_observer.py` (adapter alone) and `test_run_witness.py`
(recorder alone, fed pre-built `CaptureLifecycleObservation`s), this file wires both
together so the deployment's real `CAPTURE_STATUS_PHASES` table and the
recorder's dedup/terminal/truncate state machine are exercised as one
pipeline, the way `run_witness_loop` actually runs them.
"""

import asyncio
import contextlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.api._capture_observer import ControlPortCaptureObserver
from cora.api._capture_progress_feeder import CaptureProgressFeeder
from cora.api._run_witness import RunWitnessRecorder, run_witness_loop
from cora.infrastructure.config import Settings
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.ports.control_port import Measurement
from cora.run.aggregates.run import InMemoryFeedHeartbeatStore
from cora.run.features.append_observations.command import AppendObservations
from cora.run.features.record_witnessed_run.command import RecordWitnessedRun
from cora.run.features.record_witnessed_run_outcome.command import RecordWitnessedRunOutcome
from cora.run.features.truncate_run.command import TruncateRun
from cora.run.ports.capture_observer import CaptureProgressObservation
from cora.shared.reach import ReachTier
from tests.unit._helpers import build_deps

_CODE = "2bmb-tomoscan"
_STATUS_PV = "2bmb:TomoScan:ScanStatus"
_ABORT_PV = "2bmb:TomoScan:AbortScan"
_SAVED_PV = "2bmb:TomoScan:ImagesSaved"
_PLAN_ID = UUID("01900000-0000-7000-8000-000000007107")
_NOW = datetime(2026, 8, 14, 22, 30, 34, tzinfo=UTC)

# arcturus's live CAPTURE_STATUS_PHASES, including the "Programming PSO"
# fix shipped alongside this effort's deploy.
_PHASES = {
    "Beginning scan": "Begun",
    "Waiting for overwrite confirmation": "Progressing",
    "Moving rotation axis to start": "Progressing",
    "Programming PSO": "Progressing",
    "Collecting dark fields": "Progressing",
    "Collecting flat fields": "Progressing",
    "Collecting projections": "Progressing",
    "fdt file transfer complete": "Progressing",
    "scp file transfer complete": "Progressing",
    "Scan complete": "Ended",
}

# One real fly-scan cycle's literal sequence, in order, per the arcturus
# log (2026-08-14T22:30:34Z onward): Beginning scan -> Programming PSO ->
# Moving rotation axis to start -> dark -> flat -> projections -> fdt
# transfer -> Scan complete.
_HAPPY_CYCLE = (
    "Beginning scan",
    "Programming PSO",
    "Moving rotation axis to start",
    "Collecting dark fields",
    "Collecting flat fields",
    "Collecting projections",
    "fdt file transfer complete",
    "Scan complete",
)


class _ScriptedPort:
    """Minimal fake `ControlPort`: replays a fixed reading list per address.

    Yields control back to the event loop between readings (real EPICS
    CA delivery is network-driven and naturally interleaves independent
    subscriptions this way); without it, one address's whole script
    would race ahead of a sibling address's pump before the loop ever
    gets a chance to schedule it, which is a fake-port artifact, not a
    real-deployment ordering guarantee this test should rely on.
    """

    def __init__(self, readings: dict[str, list[Measurement]]) -> None:
        self._readings = readings

    async def subscribe(self, address: str):
        for reading in self._readings.get(address, []):
            await asyncio.sleep(0)
            yield reading


def _reading(value: str) -> Measurement:
    return Measurement(value=value, kind="Categorical", quality="Good", produced_at=None)  # type: ignore[arg-type]


def _progress_reading(value: str) -> Measurement:
    """Unlike `_reading`, carries a real substrate time: a progress
    reading with `produced_at=None` is deliberately skipped by
    `_flush_observations`'s dual-clock guard, which is not what these
    tests are exercising."""
    return Measurement(value=value, kind="Categorical", quality="Good", produced_at=_NOW)  # type: ignore[arg-type]


class _FakeGenesis:
    """Fake `record_witnessed_run` handler: records every call, returns a
    fresh run_id each time (and remembers what it returned, so a test
    can assert a later write landed against the SAME run_id)."""

    def __init__(self) -> None:
        self.calls: list[RecordWitnessedRun] = []
        self.returned_run_ids: list[UUID] = []

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
        run_id = uuid4()
        self.returned_run_ids.append(run_id)
        return run_id


class _FakeOutcome:
    """Fake `record_witnessed_run_outcome` handler: records every call,
    against a shared `order` list when one is supplied."""

    def __init__(self, *, order: list[str] | None = None) -> None:
        self.calls: list[RecordWitnessedRunOutcome] = []
        self._order = order

    async def __call__(
        self,
        command: RecordWitnessedRunOutcome,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        if self._order is not None:
            self._order.append("outcome")
        self.calls.append(command)


class _FakeTruncate:
    """Fake `truncate_run` handler: records every call."""

    def __init__(self) -> None:
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


class _FakeAppendObservations:
    """Fake `append_observations` handler: records every call, in order,
    against a shared list so a test can assert its position relative to
    other calls (e.g. the outcome command)."""

    def __init__(self, *, order: list[str] | None = None) -> None:
        self.calls: list[AppendObservations] = []
        self._order = order

    async def __call__(
        self,
        command: AppendObservations,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int:
        if self._order is not None:
            self._order.append("append")
        self.calls.append(command)
        return len(command.entries)


def _recorder(
    *, genesis: _FakeGenesis, outcome: _FakeOutcome, truncate: _FakeTruncate
) -> RunWitnessRecorder:
    settings = Settings(  # type: ignore[call-arg]
        run_witness_recording_enabled=True,
        capture_watch_plan_id=_PLAN_ID,
    )
    return RunWitnessRecorder(
        deps=build_deps(ids=[uuid4() for _ in range(200)]),
        record_witnessed_run=genesis,
        record_witnessed_run_outcome=outcome,
        truncate_run=truncate,
        settings=settings,
    )


def _feeder(
    recorder: RunWitnessRecorder, append_observations: _FakeAppendObservations
) -> CaptureProgressFeeder:
    return CaptureProgressFeeder(
        deps=build_deps(ids=[uuid4() for _ in range(200)]),
        append_observations=append_observations,  # type: ignore[arg-type]
        feed_heartbeat_store=InMemoryFeedHeartbeatStore(),
        open_captures=recorder.open_captures,
        principal_id=uuid4(),
    )


async def _run_loop_over(
    port: _ScriptedPort,
    recorder: RunWitnessRecorder,
    *,
    feeder: CaptureProgressFeeder | None = None,
    capture_pvs: dict[str, str] | None = None,
    settle_seconds: float = 0.05,
) -> None:
    observer = ControlPortCaptureObserver(
        control_port=port,  # type: ignore[arg-type]
        capture_pvs={_CODE: capture_pvs or {"status": _STATUS_PV, "abort": _ABORT_PV}},
        status_phases=_PHASES,
    )
    task = asyncio.create_task(
        run_witness_loop(
            observer=observer,
            capture_codes=frozenset({_CODE}),
            recorder=recorder,
            feeder=feeder,
        )
    )
    await asyncio.sleep(settle_seconds)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


@pytest.mark.unit
async def test_replay_three_clean_cycles_promotes_and_completes_each_exactly_once() -> None:
    """Three back-to-back real fly-scan cycles: exactly 3 Runs promoted,
    all 3 closed as Completed via the real Ended classification, zero
    truncates (no missed terminal in a clean sequence), and the `fdt`
    transfer-start literal never terminates anything along the way."""
    literals = _HAPPY_CYCLE * 3
    port = _ScriptedPort({_STATUS_PV: [_reading(v) for v in literals]})
    genesis = _FakeGenesis()
    outcome = _FakeOutcome()
    truncate = _FakeTruncate()
    recorder = _recorder(genesis=genesis, outcome=outcome, truncate=truncate)

    await _run_loop_over(port, recorder)

    assert len(genesis.calls) == 3
    assert len(outcome.calls) == 3
    assert all(call.observed_phase.value == "Ended" for call in outcome.calls)
    assert truncate.calls == []


@pytest.mark.unit
async def test_replay_a_real_abort_edge_closes_as_aborted_not_completed() -> None:
    """A real AbortScan assertion closes the capture as Aborted before
    the trailing 'Scan complete' the exception handler's `finally`
    block still writes; that trailing literal must land as a no-op on
    the now-idle capture, not a second outcome call."""
    port = _ScriptedPort(
        {
            _STATUS_PV: [
                _reading("Beginning scan"),
                _reading("Programming PSO"),
                _reading("Collecting projections"),
                _reading("fdt file transfer complete"),
                _reading("Scan complete"),
            ],
            _ABORT_PV: [_reading("Yes")],
        }
    )
    genesis = _FakeGenesis()
    outcome = _FakeOutcome()
    truncate = _FakeTruncate()
    recorder = _recorder(genesis=genesis, outcome=outcome, truncate=truncate)

    await _run_loop_over(port, recorder)

    assert len(genesis.calls) == 1
    assert len(outcome.calls) == 1
    assert outcome.calls[0].observed_phase.value == "Aborted"


@pytest.mark.unit
async def test_replay_a_missed_terminal_is_recovered_by_the_next_begun() -> None:
    """The status pump's terminal literal is dropped (models a CA
    transition loss); the next cycle's Beginning scan truncates the
    stale Run before promoting a fresh one."""
    literals = [
        "Beginning scan",
        "Programming PSO",
        "Collecting projections",
        # 'Scan complete' dropped here.
        "Beginning scan",
        "Programming PSO",
        "Collecting projections",
        "Scan complete",
    ]
    port = _ScriptedPort({_STATUS_PV: [_reading(v) for v in literals]})
    genesis = _FakeGenesis()
    outcome = _FakeOutcome()
    truncate = _FakeTruncate()
    recorder = _recorder(genesis=genesis, outcome=outcome, truncate=truncate)

    await _run_loop_over(port, recorder)

    assert len(genesis.calls) == 2
    assert len(truncate.calls) == 1
    assert len(outcome.calls) == 1


@pytest.mark.unit
async def test_replay_progress_readings_flush_before_the_outcome_lands() -> None:
    """A real 2-BM ImagesSaved trail ("<done>/<total>" strings), buffered
    across one fly-scan cycle, is flushed and written against the
    promoted run_id BEFORE the recorder's own outcome command closes
    that Run: `run_witness_loop` flushes on the terminal observation's
    phase before dispatching it to the recorder, so the observation
    write for a cycle always precedes that cycle's outcome write."""
    order: list[str] = []
    port = _ScriptedPort(
        {
            _STATUS_PV: [_reading(v) for v in _HAPPY_CYCLE],
            _SAVED_PV: [
                _progress_reading("100/1561"),
                _progress_reading("800/1561"),
                _progress_reading("1561/1561"),
            ],
        }
    )
    genesis = _FakeGenesis()
    outcome = _FakeOutcome(order=order)
    truncate = _FakeTruncate()
    append_observations = _FakeAppendObservations(order=order)
    recorder = _recorder(genesis=genesis, outcome=outcome, truncate=truncate)
    feeder = _feeder(recorder, append_observations)

    await _run_loop_over(
        port,
        recorder,
        feeder=feeder,
        capture_pvs={"status": _STATUS_PV, "abort": _ABORT_PV, "images_saved": _SAVED_PV},
    )

    assert len(genesis.calls) == 1
    assert len(outcome.calls) == 1
    assert len(append_observations.calls) == 1
    assert append_observations.calls[0].run_id == genesis.returned_run_ids[0]
    entries = append_observations.calls[0].entries
    assert [e.channel_name for e in entries] == ["images_saved"]
    # The buffer is latest-wins: only the last reading survives to the flush.
    assert entries[0].value == 1561.0
    assert order == ["append", "outcome"]


@pytest.mark.unit
async def test_replay_a_late_progress_reading_after_close_is_dropped_not_written() -> None:
    """A progress reading whose callback lands AFTER a capture has
    already closed must not resurrect a write against a Run that is no
    longer open. Decoupled from the two pumps' relative arrival timing
    (an accepted residual documented in `_run_witness.py`, not
    something to assert on here): the closed-capture case is exercised
    directly against the real recorder + feeder pair once the cycle has
    genuinely finished, not raced against the status pump."""
    port = _ScriptedPort({_STATUS_PV: [_reading(v) for v in _HAPPY_CYCLE]})
    genesis = _FakeGenesis()
    outcome = _FakeOutcome()
    truncate = _FakeTruncate()
    append_observations = _FakeAppendObservations()
    recorder = _recorder(genesis=genesis, outcome=outcome, truncate=truncate)
    feeder = _feeder(recorder, append_observations)

    await _run_loop_over(port, recorder, feeder=feeder)
    assert len(outcome.calls) == 1  # the cycle has genuinely closed

    feeder.offer(
        CaptureProgressObservation(
            capture_code=_CODE,
            role="images_saved",
            value=1561.0,
            reach_tier=ReachTier.RELAYED,
            observed_at=None,
            source_kind="EpicsPv",
            source_id=_SAVED_PV,
        )
    )
    await feeder.flush_capture(_CODE)

    assert append_observations.calls == []
