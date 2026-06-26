"""Unit tests for the `stream` action body and its `StreamParams` schema.

`stream` records a DAQ-owned high-rate frame stream against the
areaDetector file-writer PV convention, terminal on a frame count
(`events` -> "count") or a wall-clock cap (`duration` -> "duration").
It runs its own terminal loop (NOT a `collect`-style `Acquire_RBV`
done-poll) and STOPs the DAQ in a `finally` so an aborted stream never
leaves it free-running.

  StreamParams validation:
  - events-only accepted; duration-only accepted
  - both events and duration rejected (one terminal only)
  - neither events nor duration rejected (a terminal is required)
  - events >= 1 enforced; duration > 0 enforced

  Body behaviour (stream called directly with ActionContext):
  - count terminal: writes AcquireTime/NumCapture/Capture=1, polls
    NumCaptured_RBV, stops (Capture=0), reads FullFileName_RBV, evidence
    carries uri + frames_captured + terminal == "count"
  - duration terminal: stops when the clock passes started_at + duration,
    terminal == "duration"
  - the DAQ is STOPPED (Capture=0) on task cancellation (finally)
  - unconnected detector propagates ControlNotConnectedError

  End-to-end via Conductor:
  - InMemoryActionRegistry({"stream": stream}) + ActionStep produces
    ConductorResult.succeeded=True with the expected result_data
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from cora.infrastructure.ports.clock import FakeClock
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.acquisitions import StreamParams, stream
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.conductor import (
    ActionContext,
    ActionStep,
    Conductor,
    InMemoryActionRegistry,
)
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    Measurement,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

    from cora.operation.features.append_activities.command import (
        AppendProcedureActivities,
    )

_FIXED_NOW = datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)
_DETECTOR = "8idRigaku3m:HDF1"
_URI = "/data/xpcs/8id/run0042/stream.h5"


def _seed_daq(port: InMemoryControlPort, *, captured: int) -> None:
    port.simulate_connect(f"{_DETECTOR}:AcquireTime")
    port.simulate_connect(f"{_DETECTOR}:NumCapture")
    port.simulate_connect(f"{_DETECTOR}:Capture")
    port.set_reading(
        f"{_DETECTOR}:NumCaptured_RBV",
        Measurement(value=captured, kind="Scalar", quality="Good", produced_at=_FIXED_NOW),
    )
    port.set_reading(
        f"{_DETECTOR}:FullFileName_RBV",
        Measurement(value=_URI, kind="Categorical", quality="Good", produced_at=_FIXED_NOW),
    )


def _ctx(port: Any, params: Mapping[str, Any], clock: Any = None) -> ActionContext:
    return ActionContext(
        control_port=port,
        clock=clock if clock is not None else FakeClock(_FIXED_NOW),
        params=params,
    )


@dataclass
class _RecordingPort:
    delegate: InMemoryControlPort
    writes: list[tuple[str, Any, bool]] = field(default_factory=list[tuple[str, Any, bool]])

    async def write(
        self,
        address: str,
        value: Any,
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        self.writes.append((address, value, wait))
        await self.delegate.write(address, value, wait=wait, timeout_s=timeout_s)

    async def read(self, address: str) -> Measurement:
        return await self.delegate.read(address)

    def subscribe(self, address: str) -> AsyncIterator[Measurement]:
        return self.delegate.subscribe(address)


@dataclass
class _StepClock:
    """Returns each seeded time in turn, clamping at the last (for duration tests)."""

    times: list[datetime]
    _index: int = 0

    def now(self) -> datetime:
        at = self.times[min(self._index, len(self.times) - 1)]
        self._index += 1
        return at


# --- StreamParams validation -------------------------------------------


@pytest.mark.unit
def test_daq_run_params_events_only_accepted() -> None:
    params = StreamParams.model_validate({"detector": _DETECTOR, "events": 100000, "dwell": 0.001})
    assert params.events == 100000
    assert params.duration is None


@pytest.mark.unit
def test_daq_run_params_duration_only_accepted() -> None:
    params = StreamParams.model_validate({"detector": _DETECTOR, "duration": 30.0, "dwell": 0.001})
    assert params.duration == 30.0
    assert params.events is None


@pytest.mark.unit
def test_daq_run_params_both_terminals_rejected() -> None:
    with pytest.raises(ValidationError, match="exactly one of events or duration"):
        StreamParams.model_validate(
            {"detector": _DETECTOR, "events": 1000, "duration": 30.0, "dwell": 0.001}
        )


@pytest.mark.unit
def test_daq_run_params_no_terminal_rejected() -> None:
    with pytest.raises(ValidationError, match="exactly one of events or duration"):
        StreamParams.model_validate({"detector": _DETECTOR, "dwell": 0.001})


@pytest.mark.unit
@pytest.mark.parametrize("bad_events", [0, -5])
def test_daq_run_params_non_positive_events_rejected(bad_events: int) -> None:
    with pytest.raises(ValidationError):
        StreamParams.model_validate({"detector": _DETECTOR, "events": bad_events, "dwell": 0.001})


@pytest.mark.unit
@pytest.mark.parametrize("bad_duration", [0.0, -1.0])
def test_daq_run_params_non_positive_duration_rejected(bad_duration: float) -> None:
    with pytest.raises(ValidationError):
        StreamParams.model_validate(
            {"detector": _DETECTOR, "duration": bad_duration, "dwell": 0.001}
        )


# --- stream body behaviour ---------------------------------------------


@pytest.mark.unit
async def test_stream_count_terminal_writes_capture_cycle_and_returns_evidence() -> None:
    inner = InMemoryControlPort()
    _seed_daq(inner, captured=100)
    port = _RecordingPort(delegate=inner)
    result = await stream(_ctx(port, {"detector": _DETECTOR, "events": 100, "dwell": 0.001}))
    # Config -> start; then the finally STOP after the count terminal.
    assert port.writes == [
        (f"{_DETECTOR}:AcquireTime", 0.001, True),
        (f"{_DETECTOR}:NumCapture", 100, True),
        (f"{_DETECTOR}:Capture", 1, True),
        (f"{_DETECTOR}:Capture", 0, True),
    ]
    assert result["terminal"] == "count"
    assert result["uri"] == _URI
    assert result["frames_captured"] == 100
    assert result["events_requested"] == 100
    assert result["duration_requested"] is None
    assert result["dwell"] == 0.001


@pytest.mark.unit
async def test_stream_duration_terminal_stops_when_clock_passes_cap() -> None:
    inner = InMemoryControlPort()
    _seed_daq(inner, captured=58000)
    port = _RecordingPort(delegate=inner)
    clock = _StepClock([_FIXED_NOW, _FIXED_NOW + timedelta(seconds=10)])
    result = await stream(
        _ctx(port, {"detector": _DETECTOR, "duration": 5.0, "dwell": 0.001}, clock=clock)
    )
    assert result["terminal"] == "duration"
    assert result["duration_requested"] == 5.0
    assert result["events_requested"] is None
    assert result["frames_captured"] == 58000
    # NumCapture = 0 (unlimited) in the duration cap; Capture started and stopped.
    assert (f"{_DETECTOR}:NumCapture", 0, True) in port.writes
    assert (f"{_DETECTOR}:Capture", 1, True) in port.writes
    assert (f"{_DETECTOR}:Capture", 0, True) in port.writes


@pytest.mark.unit
async def test_stream_stops_daq_on_cancellation() -> None:
    """An aborted stream (task cancel) must still write Capture=0 (finally)."""
    inner = InMemoryControlPort()
    _seed_daq(inner, captured=0)  # never reaches events -> loop parks in sleep
    port = _RecordingPort(delegate=inner)
    task = asyncio.create_task(
        stream(_ctx(port, {"detector": _DETECTOR, "events": 1_000_000, "dwell": 0.001}))
    )
    await asyncio.sleep(0)  # let the body arm and enter the poll loop
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (f"{_DETECTOR}:Capture", 1, True) in port.writes
    assert (f"{_DETECTOR}:Capture", 0, True) in port.writes


@pytest.mark.unit
async def test_stream_unconnected_detector_propagates_not_connected_error() -> None:
    port = InMemoryControlPort()
    _seed_daq(port, captured=100)
    port.simulate_disconnect(f"{_DETECTOR}:AcquireTime")
    with pytest.raises(ControlNotConnectedError):
        await stream(_ctx(port, {"detector": _DETECTOR, "events": 100, "dwell": 0.001}))


# --- end-to-end via Conductor ------------------------------------------


@dataclass
class _AppendCall:
    command: AppendProcedureActivities
    principal_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    surface_id: UUID


@dataclass
class _FakeAppendStep:
    calls: list[_AppendCall] = field(default_factory=list[_AppendCall])

    async def __call__(
        self,
        command: AppendProcedureActivities,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int:
        self.calls.append(
            _AppendCall(
                command=command,
                principal_id=principal_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                surface_id=surface_id,
            )
        )
        return len(command.entries)


@dataclass
class _SequenceIdGenerator:
    ids: list[UUID]
    _index: int = 0

    def new_id(self) -> UUID:
        if self._index >= len(self.ids):
            raise RuntimeError("FixedIdGenerator exhausted")
        out = self.ids[self._index]
        self._index += 1
        return out


@pytest.mark.unit
async def test_conductor_executes_stream_action_and_records_step_entry() -> None:
    port = InMemoryControlPort()
    _seed_daq(port, captured=100)
    appender = _FakeAppendStep()
    registry = InMemoryActionRegistry({"stream": stream})
    conductor = Conductor(
        control_port=port,
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_SequenceIdGenerator([uuid4(), uuid4()]),
        action_registry=registry,
    )
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            ActionStep(
                name="stream",
                params={"detector": _DETECTOR, "events": 100, "dwell": 0.001},
            ),
        ),
    )
    assert result.succeeded is True
    assert result.completed_count == 1
    entry = appender.calls[1].command.entries[0]
    assert entry.step_kind == "action"
    assert entry.payload["name"] == "stream"
    assert entry.payload["result"] == "ok"
    result_data = entry.payload["result_data"]
    assert result_data["terminal"] == "count"
    assert result_data["uri"] == _URI
    assert result_data["frames_captured"] == 100
