"""Behavioural tests for `Conductor.conduct_until_converged` (slice 6c, I3).

Coverage for the AUTO-align convergence loop over the existing
ProcedureIteration aggregate, using fake lifecycle handlers (start /
complete / abort / start_iteration / end_iteration) that record the FSM
transitions + iteration boundaries, an InMemoryControlPort for the
correction setpoint, and an InMemoryComputePort seeded with an offset
SEQUENCE that shrinks into tolerance by pass N.

Asserted properties (mapped to the design memo's blockers):
  - converged path: criterion matches the deposited value -> complete; the
    sequence converges by pass N; iteration_count == N; every iteration is
    opened then closed (current_iteration_index None at terminal, B3)
  - not-converged pass leaves the loop RUNNING and iterates (NOT Held, B4)
  - cap-abort (never converges): the cap pre-check stops BEFORE the (C+1)-th
    start_iteration and aborts (B2); converged=False on each ended iteration
  - HALT-on-real-fault: a failing setpoint in the pass aborts after closing
    the open iteration (converged=None), surfacing the step failure verbatim
  - end_iteration ALWAYS precedes the FSM transition (B3 ordering)
  - loud-fail if the convergence name is absent after a successful pass
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
    WithinToleranceCriterion,
)
from cora.operation.features.abort_procedure.command import AbortProcedure
from cora.operation.features.append_activities.command import AppendProcedureActivities
from cora.operation.features.complete_procedure.command import CompleteProcedure
from cora.operation.features.end_iteration.command import EndProcedureIteration
from cora.operation.features.start_iteration.command import StartProcedureIteration
from cora.operation.features.start_procedure.command import StartProcedure
from cora.operation.ports.measurement import Measurement
from cora.recipe.aggregates.recipe.body import CaptureRef

_FIXED_NOW = datetime(2026, 6, 24, 9, 0, 0, tzinfo=UTC)
_ROT_CENTER_ADDR = "2bma:rot:center"
_CONVERGENCE_NAME = "rotation_center_offset"


@dataclass
class _FakeAppendStep:
    calls: list[AppendProcedureActivities] = field(default_factory=list[AppendProcedureActivities])

    async def __call__(
        self,
        command: AppendProcedureActivities,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int:
        self.calls.append(command)
        return len(command.entries)


@dataclass
class _Transcript:
    """Records the FSM + iteration boundary calls in order for assertions."""

    events: list[str] = field(default_factory=list[str])
    start_iteration_indices: list[int] = field(default_factory=list[int])
    end_iteration_verdicts: list[bool | None] = field(default_factory=list[bool | None])


def _make_handlers(transcript: _Transcript) -> dict[str, object]:
    async def start_procedure(command: StartProcedure, **_: object) -> None:
        transcript.events.append("start_procedure")

    async def complete_procedure(command: CompleteProcedure, **_: object) -> None:
        transcript.events.append("complete_procedure")

    async def abort_procedure(command: AbortProcedure, **_: object) -> None:
        transcript.events.append("abort_procedure")

    async def start_iteration(command: StartProcedureIteration, **_: object) -> None:
        transcript.events.append(f"start_iteration[{command.iteration_index}]")
        transcript.start_iteration_indices.append(command.iteration_index)

    async def end_iteration(command: EndProcedureIteration, **_: object) -> None:
        transcript.events.append(f"end_iteration[{command.iteration_index}={command.converged}]")
        transcript.end_iteration_verdicts.append(command.converged)

    return {
        "start_procedure": start_procedure,
        "complete_procedure": complete_procedure,
        "abort_procedure": abort_procedure,
        "start_iteration": start_iteration,
        "end_iteration": end_iteration,
    }


def _conductor(
    transcript: _Transcript,
    *,
    compute_port: InMemoryComputePort,
    control_port: InMemoryControlPort,
) -> Conductor:
    handlers = _make_handlers(transcript)
    return Conductor(
        control_port=control_port,
        append_step=_FakeAppendStep(),
        clock=FakeClock(_FIXED_NOW),
        id_generator=_FakeIdGen(),
        compute_port=compute_port,
        start_procedure=handlers["start_procedure"],  # type: ignore[arg-type]
        complete_procedure=handlers["complete_procedure"],  # type: ignore[arg-type]
        abort_procedure=handlers["abort_procedure"],  # type: ignore[arg-type]
        start_iteration=handlers["start_iteration"],  # type: ignore[arg-type]
        end_iteration=handlers["end_iteration"],  # type: ignore[arg-type]
    )


@dataclass
class _FakeIdGen:
    def new_id(self) -> UUID:
        return uuid4()


def _offset_measurement(value: float) -> Measurement:
    return Measurement(
        value=value,
        kind="Scalar",
        quality="Good",
        produced_at=_FIXED_NOW,
        name=_CONVERGENCE_NAME,
        units="pixel",
    )


def _pass_block() -> tuple[object, ...]:
    """One pass: compute the offset (deposit) then correct via CaptureRef setpoint."""
    return (
        ComputeStep(
            command=("tomopy", "find_center"),
            input_uris=("file:///a.h5",),
            output_uri=None,
            parameters={},
            capture_name=_CONVERGENCE_NAME,
        ),
        SetpointStep(
            address=_ROT_CENTER_ADDR,
            value=CaptureRef(capture_name=_CONVERGENCE_NAME),
        ),
    )


@pytest.mark.unit
async def test_converges_by_pass_n_completes_and_closes_every_iteration() -> None:
    """An offset sequence shrinking into tolerance completes; iteration_count == N (B3)."""
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_ROT_CENTER_ADDR)
    compute = InMemoryComputePort()
    # Three passes: 2.0, 1.0, then 0.3 (within tol 0.5 -> converges on pass 3).
    compute.set_measurement_sequence(
        (
            (_offset_measurement(2.0),),
            (_offset_measurement(1.0),),
            (_offset_measurement(0.3),),
        )
    )
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await conductor.conduct_until_converged(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=_pass_block(),  # type: ignore[arg-type]
        convergence_capture_name=_CONVERGENCE_NAME,
        criterion=WithinToleranceCriterion(expected=0.0, tolerance=0.5),
    )

    assert result.succeeded is True
    assert "complete_procedure" in transcript.events
    assert "abort_procedure" not in transcript.events
    # Three iterations opened, three closed; the last verdict converged.
    assert transcript.start_iteration_indices == [1, 2, 3]
    assert transcript.end_iteration_verdicts == [False, False, True]
    # Every start_iteration is followed by its end_iteration before complete (B3).
    assert transcript.events[-1] == "complete_procedure"
    assert transcript.events[-2] == "end_iteration[3=True]"
    # The final pass surfaced the converged offset for a Calibration write.
    assert [m.name for m in result.measurements] == [_CONVERGENCE_NAME]
    assert result.measurements[0].value == pytest.approx(0.3)


@pytest.mark.unit
async def test_converges_first_pass_single_iteration() -> None:
    """A first-pass-in-tolerance offset completes after exactly one iteration."""
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_ROT_CENTER_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(((_offset_measurement(0.1),),))
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await conductor.conduct_until_converged(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=_pass_block(),  # type: ignore[arg-type]
        convergence_capture_name=_CONVERGENCE_NAME,
        criterion=WithinToleranceCriterion(expected=0.0, tolerance=0.5),
    )

    assert result.succeeded is True
    assert transcript.start_iteration_indices == [1]
    assert transcript.end_iteration_verdicts == [True]


@pytest.mark.unit
async def test_never_converges_cap_trips_aborts_without_extra_start() -> None:
    """A never-shrinking offset trips the cap; abort fires WITHOUT a (C+1)-th start (B2)."""
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_ROT_CENTER_ADDR)
    compute = InMemoryComputePort()
    # Cap = 2: permit exactly 2 unconverged passes, then abort. Seed 2 passes
    # that never converge (5.0 each).
    compute.set_measurement_sequence(
        (
            (_offset_measurement(5.0),),
            (_offset_measurement(5.0),),
        )
    )
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await conductor.conduct_until_converged(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=_pass_block(),  # type: ignore[arg-type]
        convergence_capture_name=_CONVERGENCE_NAME,
        criterion=WithinToleranceCriterion(expected=0.0, tolerance=0.5),
        max_consecutive_unconverged_iterations=2,
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "ConvergenceIterationCapReached"
    # Exactly 2 iterations opened (the cap), 2 closed unconverged, then abort.
    assert transcript.start_iteration_indices == [1, 2]
    assert transcript.end_iteration_verdicts == [False, False]
    # Cap pre-check stops BEFORE the 3rd start_iteration: no start[3].
    assert "start_iteration[3]" not in transcript.events
    assert transcript.events[-1] == "abort_procedure"
    # The open iteration is always closed before the abort (B3): last end before abort.
    assert transcript.events[-2] == "end_iteration[2=False]"


@pytest.mark.unit
async def test_not_converged_pass_iterates_not_held() -> None:
    """A not-converged pass leaves the loop RUNNING and iterates; never holds (B4)."""
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_ROT_CENTER_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(
        (
            (_offset_measurement(3.0),),
            (_offset_measurement(0.2),),
        )
    )
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await conductor.conduct_until_converged(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=_pass_block(),  # type: ignore[arg-type]
        convergence_capture_name=_CONVERGENCE_NAME,
        criterion=WithinToleranceCriterion(expected=0.0, tolerance=0.5),
    )

    assert result.succeeded is True
    assert result.held is False
    # The non-converged pass 1 did NOT hold: it iterated to pass 2.
    assert transcript.start_iteration_indices == [1, 2]
    assert "hold" not in " ".join(transcript.events)


@pytest.mark.unit
async def test_real_fault_in_pass_closes_iteration_then_aborts() -> None:
    """A failing setpoint aborts after closing the open iteration (converged=None)."""
    transcript = _Transcript()
    control = InMemoryControlPort()
    # The correction address is NOT connected -> the setpoint write raises.
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(((_offset_measurement(3.0),),))
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await conductor.conduct_until_converged(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=_pass_block(),  # type: ignore[arg-type]
        convergence_capture_name=_CONVERGENCE_NAME,
        criterion=WithinToleranceCriterion(expected=0.0, tolerance=0.5),
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.source_kind == "setpoint"
    # The open iteration is closed with no verdict, THEN abort (B3).
    assert transcript.start_iteration_indices == [1]
    assert transcript.end_iteration_verdicts == [None]
    assert transcript.events[-2] == "end_iteration[1=None]"
    assert transcript.events[-1] == "abort_procedure"


@pytest.mark.unit
async def test_absent_convergence_name_after_successful_pass_loud_fails() -> None:
    """A successful pass that deposits no convergence value loud-fails (authoring error)."""
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_ROT_CENTER_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(((_offset_measurement(0.1),),))
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    # The pass block has NO deposit-ComputeStep into the convergence name (the
    # compute step carries no capture_name), so the successful pass leaves the
    # convergence slot empty.
    pass_block: tuple[object, ...] = (
        ComputeStep(
            command=("tomopy", "find_center"),
            input_uris=("file:///a.h5",),
            output_uri=None,
            parameters={},
            capture_name=None,
        ),
    )
    result = await conductor.conduct_until_converged(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=pass_block,  # type: ignore[arg-type]
        convergence_capture_name=_CONVERGENCE_NAME,
        criterion=WithinToleranceCriterion(expected=0.0, tolerance=0.5),
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "ComputeMeasurementNotFound"
    # The iteration is closed (converged=None) before the abort.
    assert transcript.end_iteration_verdicts == [None]
    assert transcript.events[-1] == "abort_procedure"


class _AlwaysOutOfToleranceComputePort(InMemoryComputePort):
    """ComputePort fake that deposits the SAME out-of-tolerance value forever.

    Unlike the FIFO-seeded `InMemoryComputePort` (which exhausts its sequence and
    then yields a measurement-less job), this always surfaces one out-of-tolerance
    `Measurement` named `_CONVERGENCE_NAME`, so an uncapped never-converging loop
    keeps iterating until the absolute ceiling backstop bites (it never aborts on
    a missing-measurement or a missing-deposit early)."""

    def __init__(self, value: float) -> None:
        super().__init__()
        self._fixed_value = value

    async def fetch_measurements(self, job_id: object) -> tuple[Measurement, ...]:  # type: ignore[override]
        return (_offset_measurement(self._fixed_value),)


@pytest.mark.unit
async def test_uncapped_never_converging_aborts_at_absolute_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """cap=None + a never-matching criterion is bounded by the absolute ceiling.

    With no patience cap the loop has no operator-set stop, so a never-converging
    sequence would actuate hardware without bound. The absolute ceiling
    (`_ABSOLUTE_MAX_ITERATIONS`, defense-in-depth) aborts the Procedure with the
    distinct `AbsoluteIterationCeilingReached` error. Monkeypatched to a small
    value so the test runs in single-digit passes rather than 10_000."""
    from cora.operation import conductor as conductor_module

    monkeypatch.setattr(conductor_module, "_ABSOLUTE_MAX_ITERATIONS", 3)
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_ROT_CENTER_ADDR)
    # Always 5.0 (well outside tol 0.5): the criterion never matches, so the loop
    # would run forever were it not for the ceiling.
    compute = _AlwaysOutOfToleranceComputePort(5.0)
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await conductor.conduct_until_converged(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=_pass_block(),  # type: ignore[arg-type]
        convergence_capture_name=_CONVERGENCE_NAME,
        criterion=WithinToleranceCriterion(expected=0.0, tolerance=0.5),
        max_consecutive_unconverged_iterations=None,
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "AbsoluteIterationCeilingReached"
    # Exactly the ceiling number of iterations ran (each opened then closed
    # unconverged), then the loop-top ceiling check aborted before the next start.
    assert transcript.start_iteration_indices == [1, 2, 3]
    assert transcript.end_iteration_verdicts == [False, False, False]
    assert "start_iteration[4]" not in transcript.events
    assert transcript.events[-1] == "abort_procedure"
    # No iteration is open at the loop top, so the abort is the only transition;
    # the last recorded boundary is an end_iteration (no dangling open start),
    # i.e. the aggregate's current_iteration_index is None at the terminal.
    assert transcript.events[-2] == "end_iteration[3=False]"


@pytest.mark.unit
async def test_missing_iteration_handlers_raises_runtime_error() -> None:
    """conduct_until_converged without the iteration handlers raises a wiring RuntimeError."""
    conductor = Conductor(
        control_port=InMemoryControlPort(),
        append_step=_FakeAppendStep(),
        clock=FakeClock(_FIXED_NOW),
        id_generator=_FakeIdGen(),
        compute_port=InMemoryComputePort(),
    )

    with pytest.raises(RuntimeError, match="conduct_until_converged"):
        await conductor.conduct_until_converged(
            procedure_id=uuid4(),
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=_pass_block(),  # type: ignore[arg-type]
            convergence_capture_name=_CONVERGENCE_NAME,
            criterion=WithinToleranceCriterion(expected=0.0, tolerance=0.5),
        )
