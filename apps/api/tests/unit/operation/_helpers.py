"""Shared helpers for Operation BC unit tests.

Two families live here, both hoisted at rule-of-three:

1. Event-seeding helpers (`seed_*`): complete_procedure / abort_procedure /
   append_activities handler tests all carried byte-identical
   `_seed_running_procedure` bodies (Registered + Started events appended
   directly to an in-memory event store).

2. The steered-loop conductor harness (`Transcript`, `build_conductor`,
   `pass_block`, `space`, `objective`, `point_to_captures`, ...): the
   behavioural and the replay-determinism modules for
   `conduct_until_advised` both drive the loop through one set of fakes
   (record-only FSM + iteration-boundary handlers, an InMemoryControlPort for
   the seeded correction setpoint, an InMemoryComputePort that deposits the
   objective metric). The per-BC helper-naming convention houses it here rather
   than in a scenario-specific module.

Per-test files import what they need; this module owns no test constants
(procedure_id, principal_id, etc.) for the seed helpers, so each test still
controls its own ID space and FixedIdGenerator queue. The steered-loop harness
carries its own fixed clock + addresses (the loop tests do not vary them).
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports.clock import FakeClock
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.aggregates.procedure import (
    ProcedureCompleted,
    ProcedureIterationStarted,
    ProcedureRegistered,
    ProcedureStarted,
    event_type_name,
    to_payload,
)
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


async def seed_registered_procedure(
    store: InMemoryEventStore,
    *,
    procedure_id: UUID,
    name: str = "Vessel-A bakeout",
    kind: str = "bakeout",
    target_asset_ids: tuple[UUID, ...] | None = None,
    parent_run_id: UUID | None = None,
    when: datetime,
    correlation_id: UUID,
    principal_id: UUID,
) -> None:
    """Append ProcedureRegistered to land the Procedure in `Defined`."""
    event = ProcedureRegistered(
        procedure_id=procedure_id,
        name=name,
        kind=kind,
        target_asset_ids=target_asset_ids or (),
        parent_run_id=parent_run_id,
        occurred_at=when,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=uuid4(),
        command_name="RegisterProcedure",
        correlation_id=correlation_id,
        principal_id=principal_id,
    )
    await store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=0,
        events=[new_event],
    )


async def seed_running_procedure(
    store: InMemoryEventStore,
    *,
    procedure_id: UUID,
    when: datetime,
    correlation_id: UUID,
    principal_id: UUID,
) -> None:
    """Append Registered + Started to land the Procedure in `Running`."""
    await seed_registered_procedure(
        store,
        procedure_id=procedure_id,
        when=when,
        correlation_id=correlation_id,
        principal_id=principal_id,
    )
    started = ProcedureStarted(procedure_id=procedure_id, occurred_at=when)
    new_event = to_new_event(
        event_type=event_type_name(started),
        payload=to_payload(started),
        occurred_at=started.occurred_at,
        event_id=uuid4(),
        command_name="StartProcedure",
        correlation_id=correlation_id,
        principal_id=principal_id,
    )
    await store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=1,
        events=[new_event],
    )


async def seed_completed_procedure(
    store: InMemoryEventStore,
    *,
    procedure_id: UUID,
    when: datetime,
    correlation_id: UUID,
    principal_id: UUID,
) -> None:
    """Append Registered + Started + Completed to reach a terminal `Completed`."""
    await seed_running_procedure(
        store,
        procedure_id=procedure_id,
        when=when,
        correlation_id=correlation_id,
        principal_id=principal_id,
    )
    completed = ProcedureCompleted(procedure_id=procedure_id, occurred_at=when)
    new_event = to_new_event(
        event_type=event_type_name(completed),
        payload=to_payload(completed),
        occurred_at=completed.occurred_at,
        event_id=uuid4(),
        command_name="CompleteProcedure",
        correlation_id=correlation_id,
        principal_id=principal_id,
    )
    await store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=2,
        events=[new_event],
    )


async def seed_running_procedure_with_open_iteration(
    store: InMemoryEventStore,
    *,
    procedure_id: UUID,
    iteration_index: int = 1,
    when: datetime,
    correlation_id: UUID,
    principal_id: UUID,
) -> None:
    """Append Registered + Started + IterationStarted to leave one iteration open."""
    await seed_running_procedure(
        store,
        procedure_id=procedure_id,
        when=when,
        correlation_id=correlation_id,
        principal_id=principal_id,
    )
    started = ProcedureIterationStarted(
        procedure_id=procedure_id,
        iteration_index=iteration_index,
        occurred_at=when,
    )
    new_event = to_new_event(
        event_type=event_type_name(started),
        payload=to_payload(started),
        occurred_at=started.occurred_at,
        event_id=uuid4(),
        command_name="StartProcedureIteration",
        correlation_id=correlation_id,
        principal_id=principal_id,
    )
    await store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=2,
        events=[new_event],
    )


# ----- steered-loop (`conduct_until_advised`) conductor harness -----
#
# Lifted verbatim (behaviour-preserving) so the behavioural module and the
# replay-determinism module drive the loop through one set of fakes. The
# exported symbols are public; callers alias them to module-private names,
# mirroring `build_deps as _build_deps_shared` elsewhere in the suite.

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


__all__ = [
    "FIXED_NOW",
    "MOTOR_ADDR",
    "OBJECTIVE_NAME",
    "FakeAppendStep",
    "FakeIdGen",
    "Transcript",
    "build_conductor",
    "objective",
    "objective_measurement",
    "pass_block",
    "point_to_captures",
    "seed_completed_procedure",
    "seed_registered_procedure",
    "seed_running_procedure",
    "seed_running_procedure_with_open_iteration",
    "space",
]
