"""Behavioural tests for the Conductor's `ComputeStep` arm (slice 6a).

Coverage for `_run_compute` (the value-arm compute step):

  Happy path:
  - submit -> await -> fetch_measurements -> provide_result records a
    pre-effect in-flight marker + an `ok` outcome carrying job_id + status
    + each Measurement flattened (name + value + kind + units preserved)
  - the produced Measurements surface on `ConductorResult.measurements`
  - the in-memory fake's Simulated kind folds onto the result actuation_kind

  Failure families (each -> recorded `failed` outcome + ConductorFailure halt):
  - submit rejects (ComputeSubmitRejectedError)
  - await raises (ComputeJobFailedError)
  - a non-Succeeded terminal (Failed) without an exception
  - fetch_measurements raises MeasurementNotFoundError (unseeded value)

  Wiring:
  - dispatching a ComputeStep with compute_port=None raises RuntimeError

  Resume:
  - execute_from halts-for-operator on a ComputeStep (like an acquisition)

The unit tier uses `InMemoryComputePort` (the only value-producing
substrate) seeded via `set_next_measurements` / `set_next_result`, plus
the same fake append-step handler the rest of the conductor tests use.
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
from cora.operation.ports.control_port import ActuationKind
from cora.operation.ports.measurement import Measurement

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
    """Fake `Handler` for the append_activities slice; records every call."""

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
) -> Conductor:
    return Conductor(
        control_port=InMemoryControlPort(),
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_SequenceIdGenerator([]),
        compute_port=compute_port,
    )


def _pixel_size_measurement(value: float) -> Measurement:
    return Measurement(
        value=value,
        kind="Scalar",
        quality="Good",
        produced_at=_FIXED_NOW,
        name="pixel_size",
        units="um",
    )


_COMPUTE_STEP = ComputeStep(
    command=("tomopy", "find_center"),
    input_uris=("file:///flat0.h5", "file:///flat1.h5"),
    output_uri=None,
    parameters={"algorithm": "vo"},
)


@pytest.mark.unit
async def test_compute_happy_path_records_marker_then_outcome_with_measurement() -> None:
    """Submit -> await -> fetch -> provide records marker + ok outcome carrying the Measurement."""
    appender = _FakeAppendStep()
    port = InMemoryComputePort()
    port.set_next_measurements((_pixel_size_measurement(3.45),))
    conductor = _conductor(appender, compute_port=port)

    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(_COMPUTE_STEP,),
    )

    assert result.succeeded is True
    assert result.completed_count == 1
    # Side-effecting step: a pre-effect in_flight marker + the ok outcome.
    assert len(appender.calls) == 2
    marker = appender.calls[0].command.entries[0]
    assert marker.step_kind == "compute"
    assert marker.payload["result"] == "in_flight"
    assert marker.payload["command"] == ["tomopy", "find_center"]
    outcome = appender.calls[1].command.entries[0]
    assert outcome.step_kind == "compute"
    assert outcome.payload["result"] == "ok"
    assert outcome.payload["status"] == ComputeStatus.SUCCEEDED.value
    assert outcome.payload["job_id"] == "inmem-job-1"
    # The compute-Measurement flattener keeps name + units (unlike the
    # control flattener pinned by projection-metadata frozenset tests).
    assert outcome.payload["measurements"] == [
        {
            "name": "pixel_size",
            "value": 3.45,
            "kind": "Scalar",
            "units": "um",
            "quality": "Good",
        }
    ]


@pytest.mark.unit
async def test_compute_happy_path_surfaces_measurement_on_result() -> None:
    """The produced Measurement surfaces on ConductorResult.measurements."""
    appender = _FakeAppendStep()
    port = InMemoryComputePort()
    port.set_next_measurements((_pixel_size_measurement(3.45),))
    conductor = _conductor(appender, compute_port=port)

    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(_COMPUTE_STEP,),
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].name == "pixel_size"
    assert result.measurements[0].value == 3.45
    assert result.measurements[0].units == "um"


@pytest.mark.unit
async def test_compute_folds_simulated_actuation_kind_onto_result() -> None:
    """The in-memory fake's Simulated kind folds onto the conduct's actuation_kind.

    Even though no ControlPort step ran (so _ActuationObserver saw
    nothing), the ComputeStep's substrate kind is merged in, so a
    simulated solver taints the conduct.
    """
    appender = _FakeAppendStep()
    port = InMemoryComputePort()
    port.set_next_measurements((_pixel_size_measurement(3.45),))
    conductor = _conductor(appender, compute_port=port)

    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(_COMPUTE_STEP,),
    )

    assert result.actuation_kind == ActuationKind.SIMULATED


@pytest.mark.unit
async def test_compute_submit_rejection_records_failure_and_halts() -> None:
    """A submit rejection records a failed outcome + ConductorFailure halt."""
    appender = _FakeAppendStep()

    class _RejectingSubmit(InMemoryComputePort):
        async def submit(self, job_spec: object) -> object:  # type: ignore[override]
            from cora.operation.ports.compute_port import ComputeSubmitRejectedError

            raise ComputeSubmitRejectedError("quota exceeded")

    conductor = _conductor(appender, compute_port=_RejectingSubmit())

    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(_COMPUTE_STEP,),
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.source_kind == "compute"
    assert result.failure.error_class == "ComputeSubmitRejectedError"
    assert result.failure.step_index == 0
    # marker + failed outcome both recorded.
    assert len(appender.calls) == 2
    assert appender.calls[1].command.entries[0].payload["result"] == "failed"


@pytest.mark.unit
async def test_compute_await_failure_records_failure_and_halts() -> None:
    """ComputeJobFailedError from await records a failed outcome + halt."""
    appender = _FakeAppendStep()

    class _FailingAwait(InMemoryComputePort):
        async def await_terminal_state(self, job_id: object) -> object:  # type: ignore[override]
            from cora.operation.ports.compute_port import ComputeJobFailedError, JobId

            raise ComputeJobFailedError(JobId(str(job_id)), "solver crashed")

    conductor = _conductor(appender, compute_port=_FailingAwait())

    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(_COMPUTE_STEP,),
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "ComputeJobFailedError"
    assert appender.calls[1].command.entries[0].payload["result"] == "failed"


@pytest.mark.unit
async def test_compute_non_succeeded_terminal_records_failure_and_halts() -> None:
    """A Failed terminal (no exception) records a failed outcome + halt."""
    appender = _FakeAppendStep()
    port = InMemoryComputePort()
    port.set_next_result(ComputeStatus.FAILED)
    conductor = _conductor(appender, compute_port=port)

    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(_COMPUTE_STEP,),
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "ComputeJobFailedError"
    failed = appender.calls[1].command.entries[0].payload
    assert failed["result"] == "failed"
    assert failed["status"] == ComputeStatus.FAILED.value


@pytest.mark.unit
async def test_compute_measurement_not_found_records_failure_and_halts() -> None:
    """An unseeded value arm (MeasurementNotFoundError) halts with a recorded failure."""
    appender = _FakeAppendStep()
    port = InMemoryComputePort()
    # Succeeded but NO measurements seeded -> fetch_measurements raises.
    port.set_next_result(ComputeStatus.SUCCEEDED)
    conductor = _conductor(appender, compute_port=port)

    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(_COMPUTE_STEP,),
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "MeasurementNotFoundError"
    assert result.measurements == ()
    assert appender.calls[1].command.entries[0].payload["result"] == "failed"


@pytest.mark.unit
async def test_compute_step_without_compute_port_raises_runtime_error() -> None:
    """Dispatching a ComputeStep with no compute_port wired raises RuntimeError (loud)."""
    appender = _FakeAppendStep()
    conductor = _conductor(appender, compute_port=None)

    with pytest.raises(RuntimeError, match="requires a compute_port"):
        await conductor.execute(
            procedure_id=uuid4(),
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=(_COMPUTE_STEP,),
        )


@pytest.mark.unit
async def test_execute_from_halts_for_operator_on_compute_step() -> None:
    """A ComputeStep reached during resume halts-for-operator (non-idempotent submit)."""
    appender = _FakeAppendStep()
    port = InMemoryComputePort()
    port.set_next_measurements((_pixel_size_measurement(3.45),))
    conductor = _conductor(appender, compute_port=port)

    steps: tuple[object, ...] = (
        SetpointStep(address="2bma:rot:val", value=0.0),
        _COMPUTE_STEP,
    )
    result = await conductor.execute_from(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=steps,  # type: ignore[arg-type]
        boundary=1,
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.source_kind == "compute"
    assert result.failure.error_class == "AcquisitionResumeRequiresOperator"
    # The compute step was NOT executed: no submit, nothing recorded.
    assert appender.calls == []


@pytest.mark.unit
async def test_compute_step_amid_setpoints_accumulates_only_compute_measurements() -> None:
    """A ComputeStep among setpoints surfaces only its produced Measurements."""
    appender = _FakeAppendStep()
    control = InMemoryControlPort()
    control.simulate_connect("2bma:rot:val")
    port = InMemoryComputePort()
    port.set_next_measurements((_pixel_size_measurement(3.45),))
    conductor = Conductor(
        control_port=control,
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_SequenceIdGenerator([]),
        compute_port=port,
    )

    steps: tuple[object, ...] = (
        SetpointStep(address="2bma:rot:val", value=0.0),
        _COMPUTE_STEP,
    )
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=steps,  # type: ignore[arg-type]
    )

    assert result.succeeded is True
    assert result.completed_count == 2
    assert [m.name for m in result.measurements] == ["pixel_size"]
