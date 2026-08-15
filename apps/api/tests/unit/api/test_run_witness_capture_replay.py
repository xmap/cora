"""End-to-end replay tests: real `ControlPortCaptureObserver` classification
feeding a real `RunWitnessRecorder`, driven by the actual literal sequence
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
from uuid import UUID, uuid4

import pytest

from cora.api._capture_observer import ControlPortCaptureObserver
from cora.api._run_witness import RunWitnessRecorder, run_witness_loop
from cora.infrastructure.config import Settings
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.ports.control_port import Measurement
from cora.run.features.record_witnessed_run.command import RecordWitnessedRun
from cora.run.features.record_witnessed_run_outcome.command import RecordWitnessedRunOutcome
from cora.run.features.truncate_run.command import TruncateRun
from tests.unit._helpers import build_deps

_CODE = "2bmb-tomoscan"
_STATUS_PV = "2bmb:TomoScan:ScanStatus"
_ABORT_PV = "2bmb:TomoScan:AbortScan"
_PLAN_ID = UUID("01900000-0000-7000-8000-000000007107")

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


class _FakeGenesis:
    """Fake `record_witnessed_run` handler: records every call, returns a
    fresh run_id each time."""

    def __init__(self) -> None:
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
        return uuid4()


class _FakeOutcome:
    """Fake `record_witnessed_run_outcome` handler: records every call."""

    def __init__(self) -> None:
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


async def _run_loop_over(
    port: _ScriptedPort, recorder: RunWitnessRecorder, *, settle_seconds: float = 0.05
) -> None:
    observer = ControlPortCaptureObserver(
        control_port=port,  # type: ignore[arg-type]
        capture_pvs={_CODE: {"status": _STATUS_PV, "abort": _ABORT_PV}},
        status_phases=_PHASES,
    )
    task = asyncio.create_task(
        run_witness_loop(observer=observer, capture_codes=frozenset({_CODE}), recorder=recorder)
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
