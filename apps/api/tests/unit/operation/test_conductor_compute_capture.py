"""Behavioural tests for the ComputeStep `capture_name` deposit (slice 6c, C1).

Coverage for `_run_compute`'s deposit leg + the `execute()` captures param:

  Deposit success:
  - a ComputeStep with `capture_name` writes the named Measurement's value into
    the per-conduct captures, so a SAME-PASS SetpointStep CaptureRef resolves it
  - the OK compute outcome is still recorded (the deposit runs AFTER it)

  Five loud-fail deposit modes (each -> recorded `failed` entry + halt):
  - absent name (ComputeMeasurementNotFound)
  - ambiguous name (ComputeMeasurementAmbiguous, no first-wins)
  - non-Good quality (CheckFailedError, re-gated like _run_capture)
  - non-finite value (ControlValueCoercionError)
  - duplicate slot (DuplicateCapture)

  execute() captures round-trip:
  - an externally-supplied captures dict surfaces the deposit back to the caller
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.clock import FakeClock
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.conductor import (
    ComputeStep,
    Conductor,
    SetpointStep,
)
from cora.operation.features.append_activities.command import AppendProcedureActivities
from cora.operation.ports.compute_port import ComputeStatus
from cora.operation.ports.measurement import Measurement
from cora.recipe.aggregates.recipe.body import CaptureRef

_FIXED_NOW = datetime(2026, 6, 24, 9, 0, 0, tzinfo=UTC)


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
        if self._index < len(self.ids):
            out = self.ids[self._index]
            self._index += 1
            return out
        return uuid4()


def _conductor(
    appender: _FakeAppendStep,
    *,
    compute_port: InMemoryComputePort | None = None,
    control_port: InMemoryControlPort | None = None,
) -> Conductor:
    return Conductor(
        control_port=control_port or InMemoryControlPort(),
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_SequenceIdGenerator([]),
        compute_port=compute_port,
    )


def _offset_measurement(
    value: object,
    *,
    name: str = "rotation_center_offset",
    quality: str = "Good",
) -> Measurement:
    return Measurement(
        value=value,
        kind="Scalar",
        quality=quality,  # type: ignore[arg-type]
        produced_at=_FIXED_NOW,
        name=name,
        units="pixel",
    )


def _compute_step(capture_name: str | None) -> ComputeStep:
    return ComputeStep(
        command=("tomopy", "find_center"),
        input_uris=("file:///a.h5",),
        output_uri=None,
        parameters={"algorithm": "vo"},
        capture_name=capture_name,
    )


@pytest.mark.unit
async def test_compute_deposit_fills_slot_for_same_pass_setpoint_capture_ref() -> None:
    """A capture_name ComputeStep deposits its value; a later CaptureRef setpoint reads it."""
    appender = _FakeAppendStep()
    control = InMemoryControlPort()
    control.simulate_connect("2bma:rot:center")
    port = InMemoryComputePort()
    port.set_next_measurements((_offset_measurement(1023.4),))
    conductor = _conductor(appender, compute_port=port, control_port=control)

    steps: tuple[object, ...] = (
        _compute_step("rotation_center_offset"),
        SetpointStep(
            address="2bma:rot:center",
            value=CaptureRef(capture_name="rotation_center_offset"),
        ),
    )
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=steps,  # type: ignore[arg-type]
    )

    assert result.succeeded is True
    assert result.completed_count == 2
    # The setpoint drove the deposited value (resolved CaptureRef).
    reading = await control.read("2bma:rot:center")
    assert reading.value == pytest.approx(1023.4)


@pytest.mark.unit
async def test_compute_deposit_records_ok_outcome_before_depositing() -> None:
    """The compute job records its OK outcome; the deposit runs after (a successful pass)."""
    appender = _FakeAppendStep()
    port = InMemoryComputePort()
    port.set_next_measurements((_offset_measurement(0.2),))
    conductor = _conductor(appender, compute_port=port)

    captures: dict[str, object] = {}
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(_compute_step("rotation_center_offset"),),
        captures=captures,
    )

    assert result.succeeded is True
    # marker + ok outcome; the deposit adds no extra entry on success.
    assert [c.command.entries[0].payload["result"] for c in appender.calls] == [
        "in_flight",
        "ok",
    ]
    assert captures == {"rotation_center_offset": pytest.approx(0.2)}


@pytest.mark.unit
async def test_execute_external_captures_dict_round_trips_deposit_back_to_caller() -> None:
    """An externally-supplied captures dict surfaces the deposit to the caller (loop read)."""
    appender = _FakeAppendStep()
    port = InMemoryComputePort()
    port.set_next_measurements((_offset_measurement(0.42),))
    conductor = _conductor(appender, compute_port=port)

    pass_captures: dict[str, object] = {}
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(_compute_step("rotation_center_offset"),),
        captures=pass_captures,
    )

    assert result.succeeded is True
    assert pass_captures["rotation_center_offset"] == pytest.approx(0.42)


@pytest.mark.unit
async def test_compute_deposit_absent_name_records_not_found_failure_and_halts() -> None:
    """No produced Measurement carries the name -> ComputeMeasurementNotFound halt."""
    appender = _FakeAppendStep()
    port = InMemoryComputePort()
    port.set_next_measurements((_offset_measurement(0.2, name="something_else"),))
    conductor = _conductor(appender, compute_port=port)

    captures: dict[str, object] = {}
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(_compute_step("rotation_center_offset"),),
        captures=captures,
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "ComputeMeasurementNotFound"
    assert result.failure.source_kind == "compute"
    assert result.failure.target == "rotation_center_offset"
    # OK outcome recorded, then the deposit failure recorded separately.
    results = [c.command.entries[0].payload["result"] for c in appender.calls]
    assert results == ["in_flight", "ok", "failed"]
    assert "rotation_center_offset" not in captures


@pytest.mark.unit
async def test_compute_deposit_ambiguous_name_halts_no_first_wins() -> None:
    """Two Measurements with the name -> ComputeMeasurementAmbiguous halt (no first-wins)."""
    appender = _FakeAppendStep()
    port = InMemoryComputePort()
    port.set_next_measurements(
        (
            _offset_measurement(0.2),
            _offset_measurement(0.9),
        )
    )
    conductor = _conductor(appender, compute_port=port)

    captures: dict[str, object] = {}
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(_compute_step("rotation_center_offset"),),
        captures=captures,
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "ComputeMeasurementAmbiguous"
    assert "rotation_center_offset" not in captures


@pytest.mark.unit
async def test_compute_deposit_non_good_quality_halts() -> None:
    """A non-Good selected Measurement -> CheckFailedError halt (re-gated like _run_capture)."""
    appender = _FakeAppendStep()
    port = InMemoryComputePort()
    port.set_next_measurements((_offset_measurement(0.2, quality="Uncertain"),))
    conductor = _conductor(appender, compute_port=port)

    captures: dict[str, object] = {}
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(_compute_step("rotation_center_offset"),),
        captures=captures,
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "CheckFailedError"
    assert "rotation_center_offset" not in captures


@pytest.mark.unit
async def test_compute_deposit_non_finite_value_halts() -> None:
    """A non-finite value -> ControlValueCoercionError halt (poison guard)."""
    appender = _FakeAppendStep()
    port = InMemoryComputePort()
    port.set_next_measurements((_offset_measurement(float("nan")),))
    conductor = _conductor(appender, compute_port=port)

    captures: dict[str, object] = {}
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(_compute_step("rotation_center_offset"),),
        captures=captures,
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "ControlValueCoercionError"
    assert "rotation_center_offset" not in captures


@pytest.mark.unit
async def test_compute_deposit_duplicate_slot_halts() -> None:
    """Depositing into an already-filled slot -> DuplicateCapture halt."""
    appender = _FakeAppendStep()
    port = InMemoryComputePort()
    port.set_next_measurements((_offset_measurement(0.2),))
    conductor = _conductor(appender, compute_port=port)

    # Pre-fill the slot so the deposit rejects.
    captures: dict[str, object] = {"rotation_center_offset": 99.0}
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(_compute_step("rotation_center_offset"),),
        captures=captures,
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "DuplicateCapture"
    # Slot unchanged (no overwrite).
    assert captures["rotation_center_offset"] == 99.0


@pytest.mark.unit
async def test_compute_without_capture_name_fills_no_slot() -> None:
    """A capture_name=None ComputeStep records measurements but deposits nothing (6a/6b)."""
    appender = _FakeAppendStep()
    port = InMemoryComputePort()
    port.set_next_measurements((_offset_measurement(0.2),))
    conductor = _conductor(appender, compute_port=port)

    captures: dict[str, object] = {}
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(_compute_step(None),),
        captures=captures,
    )

    assert result.succeeded is True
    assert captures == {}
    assert len(result.measurements) == 1


@pytest.mark.unit
async def test_compute_succeeded_terminal_status_still_required_for_deposit() -> None:
    """A non-Succeeded terminal halts BEFORE the deposit (the deposit is success-only)."""
    appender = _FakeAppendStep()
    port = InMemoryComputePort()
    port.set_next_result(ComputeStatus.FAILED)
    conductor = _conductor(appender, compute_port=port)

    captures: dict[str, object] = {}
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(_compute_step("rotation_center_offset"),),
        captures=captures,
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "ComputeJobFailedError"
    assert captures == {}
