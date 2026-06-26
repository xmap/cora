"""Behavioural tests for `Conductor.conduct_until_advised` (the steered loop).

Coverage for the DECIDE-axis twin of `conduct_until_converged`: a
measure-then-advise loop over the existing ProcedureIteration aggregate,
using fake lifecycle handlers (start / complete / abort / start_iteration /
end_iteration) that record the FSM transitions + iteration boundaries, an
InMemoryControlPort for the seeded correction setpoint, an InMemoryComputePort
that deposits the objective metric, and an InMemoryDecidePort (or a raising
fake) for the brain.

Asserted properties:
  - every steering pass closes its iteration with converged=None ALWAYS and
    advised_stop tracking whether the brain said Stop
  - brain-Stop on the first turn completes the Procedure
  - a Measure verdict seeds the next pass's captures (the advised point
    resolves at the SetpointStep CaptureRef), then a Stop completes
  - a failed pass closes the iteration (converged=None, advised_stop=None)
    then aborts, surfacing the step failure verbatim
  - a brain that raises a Decide*Error is FOLDED: the iteration closes then
    the loop aborts with the brain's error_class, never an uncaught raise
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.clock import FakeClock
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.in_memory_decide_port import InMemoryDecidePort
from cora.operation.conductor import (
    ComputeStep,
    Conductor,
    SetpointStep,
)
from cora.operation.features.abort_procedure.command import AbortProcedure
from cora.operation.features.append_activities.command import AppendProcedureActivities
from cora.operation.features.complete_procedure.command import CompleteProcedure
from cora.operation.features.end_iteration.command import EndProcedureIteration
from cora.operation.features.start_iteration.command import StartProcedureIteration
from cora.operation.features.start_procedure.command import StartProcedure
from cora.operation.ports.decide_port import (
    DecideTimeoutError,
    SteeringAdvice,
    SteeringAxis,
    SteeringEvidence,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringPoint,
    SteeringSpace,
    SteeringVerdict,
)
from cora.operation.ports.measurement import Measurement
from cora.recipe.aggregates.recipe.body import CaptureRef
from cora.shared.decision_signals import DecisionConfidenceSource

_FIXED_NOW = datetime(2026, 6, 25, 9, 0, 0, tzinfo=UTC)
_MOTOR_ADDR = "motor"
_OBJECTIVE_NAME = "offset"


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
    end_iteration_converged: list[bool | None] = field(default_factory=list[bool | None])
    end_iteration_advised_stop: list[bool | None] = field(default_factory=list[bool | None])
    end_iteration_provenance: list[dict[str, object]] = field(
        default_factory=list[dict[str, object]]
    )


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
        transcript.events.append(
            f"end_iteration[{command.iteration_index}"
            f"=conv:{command.converged},stop:{command.advised_stop}]"
        )
        transcript.end_iteration_converged.append(command.converged)
        transcript.end_iteration_advised_stop.append(command.advised_stop)
        transcript.end_iteration_provenance.append(
            {
                "reasoning": command.reasoning,
                "confidence": command.confidence,
                "confidence_source": command.confidence_source,
                "alternatives": command.alternatives,
                "model_ref": command.model_ref,
                "reason": command.reason,
            }
        )

    return {
        "start_procedure": start_procedure,
        "complete_procedure": complete_procedure,
        "abort_procedure": abort_procedure,
        "start_iteration": start_iteration,
        "end_iteration": end_iteration,
    }


@dataclass
class _FakeIdGen:
    def new_id(self) -> UUID:
        return uuid4()


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


def _objective_measurement(value: float) -> Measurement:
    return Measurement(
        value=value,
        kind="Scalar",
        quality="Good",
        produced_at=_FIXED_NOW,
        name=_OBJECTIVE_NAME,
        units="pixel",
    )


def _pass_block() -> tuple[object, ...]:
    """One pass: deposit the objective metric then move the seeded axis.

    The ComputeStep deposits `offset` (the objective slot the brain reads); the
    SetpointStep consumes the `motor` axis via a CaptureRef so a brain-seeded
    point resolves to an actual write (and satisfies the G2 coverage guard).
    """
    return (
        ComputeStep(
            command=("solver", "metric"),
            input_uris=("file:///a.h5",),
            output_uri=None,
            parameters={},
            capture_name=_OBJECTIVE_NAME,
        ),
        SetpointStep(
            address=_MOTOR_ADDR,
            value=CaptureRef(capture_name=_MOTOR_ADDR),
        ),
    )


def _space() -> SteeringSpace:
    return SteeringSpace(axes=(SteeringAxis(name=_MOTOR_ADDR, lower=0.0, upper=10.0),))


def _objective() -> SteeringObjective:
    return SteeringObjective(
        kind=SteeringObjectiveKind.SATISFY,
        target_measurement_name=_OBJECTIVE_NAME,
        target_value=0.0,
    )


def _point_to_captures(point: SteeringPoint) -> dict[str, object]:
    return {_MOTOR_ADDR: point.coordinates[_MOTOR_ADDR]}


@pytest.mark.unit
async def test_conduct_until_advised_brain_stops_first_turn_completes_with_advised_stop_true() -> (
    None
):
    """A first-turn Stop completes the Procedure after exactly one iteration."""
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(((_objective_measurement(2.0),),))
    brain = InMemoryDecidePort()
    brain.set_advice_sequence([SteeringAdvice(verdict=SteeringVerdict.STOP)])
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await conductor.conduct_until_advised(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=_pass_block(),  # type: ignore[arg-type]
        decide_port=brain,
        objective=_objective(),
        space=_space(),
        objective_capture_name=_OBJECTIVE_NAME,
        point_to_captures=_point_to_captures,
    )

    assert result.succeeded is True
    assert transcript.events[-1] == "complete_procedure"
    assert "abort_procedure" not in transcript.events
    assert transcript.start_iteration_indices == [1]
    assert transcript.end_iteration_converged == [None]
    assert transcript.end_iteration_advised_stop == [True]


@pytest.mark.unit
async def test_conduct_until_advised_measure_then_stop_seeds_second_pass() -> None:
    """A Measure verdict seeds pass 2's captures; a following Stop completes."""
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(
        (
            (_objective_measurement(2.0),),
            (_objective_measurement(0.1),),
        )
    )
    brain = InMemoryDecidePort()
    brain.set_advice_sequence(
        [
            SteeringAdvice(
                verdict=SteeringVerdict.MEASURE,
                next_point=SteeringPoint(coordinates={_MOTOR_ADDR: 3.0}),
            ),
            SteeringAdvice(verdict=SteeringVerdict.STOP),
        ]
    )
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await conductor.conduct_until_advised(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=_pass_block(),  # type: ignore[arg-type]
        decide_port=brain,
        objective=_objective(),
        space=_space(),
        objective_capture_name=_OBJECTIVE_NAME,
        point_to_captures=_point_to_captures,
    )

    assert result.succeeded is True
    assert transcript.start_iteration_indices == [1, 2]
    assert transcript.end_iteration_converged == [None, None]
    assert transcript.end_iteration_advised_stop == [False, True]
    assert transcript.events[-1] == "complete_procedure"
    # The advised point seeded pass 2: the motor setpoint resolved + wrote 3.0.
    landed = await control.read(_MOTOR_ADDR)
    assert landed.value == pytest.approx(3.0)
    # Keystone invariant: each observation records the point it MEASURED at, so a
    # stateful brain rebuilt from the history sees real coordinates. Pass 1 is the
    # probe (axis lower bound 0.0); pass 2 is the advised point (3.0).
    assert brain.received_evidence[0].observations[0].point.coordinates[_MOTOR_ADDR] == 0.0
    assert brain.received_evidence[1].observations[1].point.coordinates[
        _MOTOR_ADDR
    ] == pytest.approx(3.0)


@pytest.mark.unit
async def test_conduct_until_advised_failed_pass_closes_iteration_then_aborts() -> None:
    """A failing setpoint aborts after closing the open iteration (converged=None)."""
    transcript = _Transcript()
    control = InMemoryControlPort()
    # The motor address is NOT connected, so pass 1's seeded setpoint write (the
    # probe-default point seeds motor on pass 1) raises a setpoint fault.
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(((_objective_measurement(2.0),),))
    brain = InMemoryDecidePort()
    brain.set_advice_sequence([SteeringAdvice(verdict=SteeringVerdict.STOP)])
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await conductor.conduct_until_advised(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=_pass_block(),  # type: ignore[arg-type]
        decide_port=brain,
        objective=_objective(),
        space=_space(),
        objective_capture_name=_OBJECTIVE_NAME,
        point_to_captures=_point_to_captures,
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.source_kind == "setpoint"
    assert transcript.start_iteration_indices == [1]
    assert transcript.end_iteration_converged == [None]
    assert transcript.end_iteration_advised_stop == [None]
    assert transcript.events[-2].startswith("end_iteration[1=")
    assert transcript.events[-1] == "abort_procedure"


class _RaisingDecidePort:
    """A brain that raises a Decide*Error on advise_next (folded, not crashed)."""

    async def advise_next(self, evidence: SteeringEvidence) -> SteeringAdvice:
        _ = evidence
        raise DecideTimeoutError(5.0)

    async def aclose(self) -> None:
        return None


@pytest.mark.unit
async def test_conduct_until_advised_decide_port_raises_folds_into_recorded_decision() -> None:
    """A Decide*Error from the brain is folded: iteration closes, loop aborts."""
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(((_objective_measurement(2.0),),))
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await conductor.conduct_until_advised(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=_pass_block(),  # type: ignore[arg-type]
        decide_port=_RaisingDecidePort(),
        objective=_objective(),
        space=_space(),
        objective_capture_name=_OBJECTIVE_NAME,
        point_to_captures=_point_to_captures,
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "DecideTimeoutError"
    assert result.failure.source_kind == "decide"
    # The pass itself succeeded; the brain consult failed: the iteration is
    # closed (converged=None, advised_stop=None) before the abort.
    assert transcript.start_iteration_indices == [1]
    assert transcript.end_iteration_converged == [None]
    assert transcript.end_iteration_advised_stop == [None]
    assert transcript.events[-1] == "abort_procedure"


@pytest.mark.unit
async def test_conduct_until_advised_missing_iteration_handlers_raises_runtime_error() -> None:
    """conduct_until_advised without the iteration handlers raises a wiring RuntimeError."""
    conductor = Conductor(
        control_port=InMemoryControlPort(),
        append_step=_FakeAppendStep(),
        clock=FakeClock(_FIXED_NOW),
        id_generator=_FakeIdGen(),
        compute_port=InMemoryComputePort(),
    )

    with pytest.raises(RuntimeError, match="conduct_until_advised"):
        await conductor.conduct_until_advised(
            procedure_id=uuid4(),
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=_pass_block(),  # type: ignore[arg-type]
            decide_port=InMemoryDecidePort(),
            objective=_objective(),
            space=_space(),
            objective_capture_name=_OBJECTIVE_NAME,
            point_to_captures=_point_to_captures,
        )


@pytest.mark.unit
async def test_conduct_until_advised_measure_with_incomplete_point_folds_not_orphans() -> None:
    """A structurally-valid Measure whose next_point omits an axis is FOLDED.

    The open iteration closes and the loop aborts (a DecideAdviceMalformedError
    folded like a brain fault), never an uncaught raise that would strand the
    Procedure Running with an open iteration. The wire guard only checks the
    pass-1 probe, so the brain-proposed point is validated here in-loop.
    """
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(((_objective_measurement(2.0),),))
    brain = InMemoryDecidePort()
    # next_point present (so __post_init__ accepts the Measure) but missing the
    # 'motor' axis: seeding it would KeyError without the in-loop coverage check.
    brain.set_advice_sequence(
        [SteeringAdvice(verdict=SteeringVerdict.MEASURE, next_point=SteeringPoint(coordinates={}))]
    )
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await conductor.conduct_until_advised(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=_pass_block(),  # type: ignore[arg-type]
        decide_port=brain,
        objective=_objective(),
        space=_space(),
        objective_capture_name=_OBJECTIVE_NAME,
        point_to_captures=_point_to_captures,
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "DecideAdviceMalformedError"
    assert result.failure.source_kind == "decide"
    assert transcript.start_iteration_indices == [1]
    assert transcript.end_iteration_converged == [None]
    assert transcript.end_iteration_advised_stop == [None]
    assert transcript.events[-1] == "abort_procedure"


@pytest.mark.unit
async def test_conduct_until_advised_missing_objective_deposit_loud_fails() -> None:
    """A pass that succeeds but never deposits the objective slot loud-fails.

    The iteration closes (converged=None) then the loop aborts with a compute
    measurement-not-found failure. This is the runtime safety net the wire guard
    cannot provide (it checks axis CaptureRef coverage, not that the objective
    slot is actually produced).
    """
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(((_objective_measurement(2.0),),))
    brain = InMemoryDecidePort()
    brain.set_advice_sequence([SteeringAdvice(verdict=SteeringVerdict.STOP)])
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await conductor.conduct_until_advised(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=_pass_block(),  # type: ignore[arg-type]
        decide_port=brain,
        objective=_objective(),
        space=_space(),
        objective_capture_name="never_deposited",  # the block deposits 'offset', not this
        point_to_captures=_point_to_captures,
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.source_kind == "compute"
    assert transcript.start_iteration_indices == [1]
    assert transcript.end_iteration_converged == [None]
    assert transcript.events[-1] == "abort_procedure"


@pytest.mark.unit
async def test_conduct_until_advised_threads_advice_provenance_onto_end_iteration() -> None:
    """The brain's advice provenance lands on the iteration ledger.

    advice_to_audit_fields maps reasoning / confidence / confidence_source /
    alternatives / model_ref onto the EndProcedureIteration the loop records.
    """
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(((_objective_measurement(0.0),),))
    brain = InMemoryDecidePort()
    brain.set_advice_sequence(
        [
            SteeringAdvice(
                verdict=SteeringVerdict.STOP,
                rationale="objective met",
                confidence=0.9,
                confidence_source=DecisionConfidenceSource.SELF_REPORTED,
                alternatives=("motor=1.0",),
                model_ref="grid_walk",
            )
        ]
    )
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await conductor.conduct_until_advised(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=_pass_block(),  # type: ignore[arg-type]
        decide_port=brain,
        objective=_objective(),
        space=_space(),
        objective_capture_name=_OBJECTIVE_NAME,
        point_to_captures=_point_to_captures,
    )

    assert result.succeeded is True
    prov = transcript.end_iteration_provenance[0]
    assert prov["reasoning"] == "objective met"
    assert prov["confidence"] == 0.9
    assert prov["confidence_source"] is DecisionConfidenceSource.SELF_REPORTED
    assert prov["alternatives"] == ("motor=1.0",)
    assert prov["model_ref"] == "grid_walk"
