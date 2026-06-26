"""Shared test harness for `Conductor.conduct_until_advised` (the steered loop).

Lifted verbatim (behaviour-preserving) from the steered-loop behavioural module
so both that module and the replay-determinism module drive the loop through one
set of fakes: record-only FSM + iteration-boundary handlers writing a
`Transcript`, an `InMemoryControlPort` for the seeded correction setpoint, an
`InMemoryComputePort` that deposits the objective metric, and the one-pass block
/ space / objective / point-to-captures the steered tests share. No behaviour
lives here that is specific to one scenario; per-scenario brains and assertions
stay in the test modules.

The module is underscore-prefixed so pytest does not collect it; the exported
symbols are public (callers alias them to module-private names, mirroring
`build_deps as _build_deps_shared` elsewhere in the suite).
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from cora.infrastructure.ports.clock import FakeClock
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
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
    SteeringAxis,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringPoint,
    SteeringSpace,
)
from cora.operation.ports.measurement import Measurement
from cora.recipe.aggregates.recipe.body import CaptureRef

FIXED_NOW = datetime(2026, 6, 25, 9, 0, 0, tzinfo=UTC)
MOTOR_ADDR = "motor"
OBJECTIVE_NAME = "offset"


@dataclass
class FakeAppendStep:
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
class Transcript:
    """Records the FSM + iteration boundary calls in order for assertions."""

    events: list[str] = field(default_factory=list[str])
    start_iteration_indices: list[int] = field(default_factory=list[int])
    end_iteration_converged: list[bool | None] = field(default_factory=list[bool | None])
    end_iteration_advised_stop: list[bool | None] = field(default_factory=list[bool | None])
    end_iteration_provenance: list[dict[str, object]] = field(
        default_factory=list[dict[str, object]]
    )


def _make_handlers(transcript: Transcript) -> dict[str, object]:
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
class FakeIdGen:
    def new_id(self) -> UUID:
        return uuid4()


def build_conductor(
    transcript: Transcript,
    *,
    compute_port: InMemoryComputePort,
    control_port: InMemoryControlPort,
) -> Conductor:
    handlers = _make_handlers(transcript)
    return Conductor(
        control_port=control_port,
        append_step=FakeAppendStep(),
        clock=FakeClock(FIXED_NOW),
        id_generator=FakeIdGen(),
        compute_port=compute_port,
        start_procedure=handlers["start_procedure"],  # type: ignore[arg-type]
        complete_procedure=handlers["complete_procedure"],  # type: ignore[arg-type]
        abort_procedure=handlers["abort_procedure"],  # type: ignore[arg-type]
        start_iteration=handlers["start_iteration"],  # type: ignore[arg-type]
        end_iteration=handlers["end_iteration"],  # type: ignore[arg-type]
    )


def objective_measurement(value: float) -> Measurement:
    return Measurement(
        value=value,
        kind="Scalar",
        quality="Good",
        produced_at=FIXED_NOW,
        name=OBJECTIVE_NAME,
        units="pixel",
    )


def pass_block() -> tuple[object, ...]:
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
            capture_name=OBJECTIVE_NAME,
        ),
        SetpointStep(
            address=MOTOR_ADDR,
            value=CaptureRef(capture_name=MOTOR_ADDR),
        ),
    )


def space() -> SteeringSpace:
    return SteeringSpace(axes=(SteeringAxis(name=MOTOR_ADDR, lower=0.0, upper=10.0),))


def objective() -> SteeringObjective:
    return SteeringObjective(
        kind=SteeringObjectiveKind.SATISFY,
        target_measurement_name=OBJECTIVE_NAME,
        target_value=0.0,
    )


def point_to_captures(point: SteeringPoint) -> dict[str, object]:
    return {MOTOR_ADDR: point.coordinates[MOTOR_ADDR]}
