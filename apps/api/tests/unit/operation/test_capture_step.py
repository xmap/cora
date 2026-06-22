"""Unit tests for the Conductor's CaptureStep + CaptureRef runtime value capture.

A `CaptureStep` reads an address at execute time and stores the OBSERVED
value into the per-conduct `captures` dict; a later `SetpointStep` whose
value is a `CaptureRef` resolves against that dict before writing. These
tests drive `Conductor.execute` directly (no FSM) with an in-memory port.

  - capture stores the observed value; a CaptureRef setpoint restores it
    (even across an intervening literal move)
  - a capture records a single outcome entry, no in_flight marker (a read
    is not side-effecting, unlike a setpoint/action)
  - an unseeded CaptureRef setpoint loud-fails (recorded, nothing written)
  - a re-capture into a filled name is rejected
  - a non-numeric / non-finite captured value is a recorded failure
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.clock import FakeClock
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.conductor import (
    ActionStep,
    CaptureStep,
    Conductor,
    InMemoryActionRegistry,
    SetpointStep,
)
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    ControlValueCoercionError,
    Reading,
)
from cora.recipe.aggregates.recipe.body import CaptureRef

if TYPE_CHECKING:
    from uuid import UUID as _UUID

    from cora.operation.features.append_activities.command import (
        AppendProcedureActivities,
    )

_FIXED_NOW = datetime(2026, 6, 22, 12, 0, 0, tzinfo=UTC)
_AXIS = "2bma:sample:x"


@dataclass
class _AppendCall:
    command: AppendProcedureActivities
    principal_id: _UUID
    correlation_id: _UUID
    causation_id: _UUID | None
    surface_id: _UUID


@dataclass
class _FakeAppendStep:
    calls: list[_AppendCall] = field(default_factory=list[_AppendCall])

    async def __call__(
        self,
        command: AppendProcedureActivities,
        *,
        principal_id: _UUID,
        correlation_id: _UUID,
        causation_id: _UUID | None = None,
        surface_id: _UUID = NIL_SENTINEL_ID,
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
            raise RuntimeError("id generator exhausted")
        out = self.ids[self._index]
        self._index += 1
        return out


def _conductor(port: InMemoryControlPort, appender: _FakeAppendStep) -> Conductor:
    return Conductor(
        control_port=port,
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_SequenceIdGenerator([uuid4() for _ in range(40)]),
        action_registry=InMemoryActionRegistry({}),
    )


def _seed_axis(port: InMemoryControlPort, value: object) -> None:
    port.simulate_connect(_AXIS)
    port.set_reading(
        _AXIS,
        Reading(value=value, kind="Scalar", quality="Good", sampled_at=_FIXED_NOW),
    )


async def _execute(conductor: Conductor, steps: tuple[object, ...]):
    return await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=steps,  # type: ignore[arg-type]
    )


@pytest.mark.unit
async def test_capture_then_captureref_setpoint_restores_observed_value() -> None:
    """Capture the observed axis, move away, then a CaptureRef setpoint restores it."""
    port = InMemoryControlPort()
    _seed_axis(port, 12.5)
    appender = _FakeAppendStep()
    result = await _execute(
        _conductor(port, appender),
        (
            CaptureStep(address=_AXIS, capture_name="home"),
            SetpointStep(address=_AXIS, value=20.0),
            SetpointStep(address=_AXIS, value=CaptureRef(capture_name="home")),
        ),
    )
    assert result.succeeded is True
    assert result.completed_count == 3
    # Restored to the CAPTURED 12.5, not the intervening literal 20.0.
    assert (await port.read(_AXIS)).value == 12.5
    # The restore setpoint's recorded value is the resolved capture.
    outcomes = [e for c in appender.calls for e in c.command.entries if e.payload["result"] == "ok"]
    restore = next(e for e in outcomes if e.payload.get("capture_ref") == "home")
    assert restore.step_kind == "setpoint"
    assert restore.payload["value"] == 12.5
    capture = next(e for e in outcomes if e.step_kind == "capture")
    assert capture.payload["captured_value"] == 12.5
    assert capture.payload["capture_name"] == "home"


@pytest.mark.unit
async def test_capture_records_no_in_flight_marker() -> None:
    """A capture is a read: one outcome entry, no pre-effect in_flight marker."""
    port = InMemoryControlPort()
    _seed_axis(port, 3.0)
    appender = _FakeAppendStep()
    await _execute(_conductor(port, appender), (CaptureStep(address=_AXIS, capture_name="home"),))
    capture_entries = [
        e for c in appender.calls for e in c.command.entries if e.step_kind == "capture"
    ]
    assert len(capture_entries) == 1
    assert capture_entries[0].payload["result"] == "ok"
    assert all(e.payload["result"] != "in_flight" for e in capture_entries)


@pytest.mark.unit
async def test_unseeded_captureref_setpoint_loud_fails() -> None:
    """A CaptureRef whose name was never captured fails loud; nothing is written."""
    port = InMemoryControlPort()
    _seed_axis(port, 1.0)
    appender = _FakeAppendStep()
    result = await _execute(
        _conductor(port, appender),
        (SetpointStep(address=_AXIS, value=CaptureRef(capture_name="missing")),),
    )
    assert result.succeeded is False
    assert result.completed_count == 0
    assert result.failure is not None
    assert result.failure.error_class == "UnresolvedCaptureRef"
    # The axis was never written (still the seeded value).
    assert (await port.read(_AXIS)).value == 1.0


@pytest.mark.unit
async def test_recapture_into_filled_name_rejected() -> None:
    """A second CaptureStep into an already-filled name is a recorded failure."""
    port = InMemoryControlPort()
    _seed_axis(port, 7.0)
    appender = _FakeAppendStep()
    result = await _execute(
        _conductor(port, appender),
        (
            CaptureStep(address=_AXIS, capture_name="home"),
            CaptureStep(address=_AXIS, capture_name="home"),
        ),
    )
    assert result.succeeded is False
    assert result.completed_count == 1
    assert result.failure is not None
    assert result.failure.error_class == "DuplicateCapture"


@pytest.mark.unit
async def test_non_numeric_capture_value_fails() -> None:
    """A categorical / non-numeric read cannot seed a numeric restore -> recorded failure."""
    port = InMemoryControlPort()
    _seed_axis(port, "parked")
    appender = _FakeAppendStep()
    result = await _execute(
        _conductor(port, appender),
        (CaptureStep(address=_AXIS, capture_name="home"),),
    )
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == ControlValueCoercionError.__name__


@pytest.mark.unit
async def test_non_finite_capture_value_fails() -> None:
    """A NaN read is rejected before it can poison a downstream setpoint."""
    port = InMemoryControlPort()
    _seed_axis(port, float("nan"))
    appender = _FakeAppendStep()
    result = await _execute(
        _conductor(port, appender),
        (CaptureStep(address=_AXIS, capture_name="home"),),
    )
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == ControlValueCoercionError.__name__


@pytest.mark.unit
async def test_non_good_quality_capture_value_fails() -> None:
    """A non-Good reading cannot seed a safe restore target -> recorded failure."""
    port = InMemoryControlPort()
    port.simulate_connect(_AXIS)
    port.set_reading(
        _AXIS,
        Reading(value=12.5, kind="Scalar", quality="Bad", sampled_at=_FIXED_NOW),
    )
    appender = _FakeAppendStep()
    result = await _execute(
        _conductor(port, appender),
        (CaptureStep(address=_AXIS, capture_name="home"),),
    )
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "CheckFailedError"


@pytest.mark.unit
async def test_capture_read_error_fails_loud() -> None:
    """A capture against a disconnected address records the control failure."""
    port = InMemoryControlPort()  # _AXIS is never connected
    appender = _FakeAppendStep()
    result = await _execute(
        _conductor(port, appender),
        (CaptureStep(address=_AXIS, capture_name="home"),),
    )
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == ControlNotConnectedError.__name__


@pytest.mark.unit
async def test_failure_after_retract_leaves_axis_displaced_without_restore() -> None:
    """If a step fails after the retract, the CaptureRef restore never runs and
    the axis is left at the OUT position (the sample stays out of beam, not
    silently restored). The no-restore-on-failure is a structural consequence of
    step ordering, replacing the deleted flats body's try/finally guarantee."""
    port = InMemoryControlPort()
    _seed_axis(port, 12.5)
    appender = _FakeAppendStep()
    result = await _execute(
        _conductor(port, appender),
        (
            CaptureStep(address=_AXIS, capture_name="home"),
            SetpointStep(address=_AXIS, value=20.0),
            ActionStep(name="collect", params={}),
            SetpointStep(address=_AXIS, value=CaptureRef(capture_name="home")),
        ),
    )
    assert result.succeeded is False
    assert result.completed_count == 2  # capture + retract; the action halts
    assert result.failure is not None
    assert result.failure.step_index == 2
    assert result.failure.error_class == "UnknownActionError"
    assert (await port.read(_AXIS)).value == 20.0  # restore never ran
