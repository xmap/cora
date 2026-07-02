"""Behavioural tests for `Conductor.conduct_until_advised_from` (steered RESUME).

Coverage for the DECIDE-axis twin of `conduct_from`: resuming a Held steered
Procedure by re-seeding the brain from the recorded closed passes, closing any
pass a mid-crash left open, RE-ASKING the brain at the frontier, then continuing
the loop. Closed passes are NOT re-driven and NOT re-measured (strategy A:
recorded results replayed, side effects not re-run); the next move is an absolute
one from wherever the hardware sits.

Asserted properties:
  - resume issues resume_procedure with the re-establishment boundary =
    the count of recovered observations, then re-asks the brain at the frontier
  - a pass left open by a mid-crash hold is CLOSED (end_iteration) before the
    frontier so the loop's start_iteration does not collide with it
  - the loop's start_iteration numbering continues from fsm_iteration_count,
    which after an abandoned pass exceeds the observation count
  - the frontier re-ask sees the FULL recovered history; a STOP completes with no
    new pass, a MEASURE seeds the next pass at the brain-advised point
  - the actuation-kind fold across recovered passes survives the interruption,
    so a simulated prefix completes as Hybrid, never laundered to Physical
  - the closed passes touch NO hardware and consume NO objective measurements
  - a Conductor missing the resume handler raises RuntimeError (a wiring bug)
"""

from uuid import uuid4

import pytest

from cora.infrastructure.ports.clock import FakeClock
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.in_memory_decide_port import InMemoryDecidePort
from cora.operation.conductor import Conductor
from cora.operation.ports.control_port import ActuationKind
from cora.operation.ports.decide_port import (
    SteeringAdvice,
    SteeringObservation,
    SteeringPoint,
    SteeringVerdict,
)
from cora.operation.ports.measurement import Measurement
from tests.unit.operation._helpers import (
    FIXED_NOW as _FIXED_NOW,
)
from tests.unit.operation._helpers import (
    MOTOR_ADDR as _MOTOR_ADDR,
)
from tests.unit.operation._helpers import (
    OBJECTIVE_NAME as _OBJECTIVE_NAME,
)
from tests.unit.operation._helpers import (
    FakeAppendStep as _FakeAppendStep,
)
from tests.unit.operation._helpers import (
    FakeIdGen as _FakeIdGen,
)
from tests.unit.operation._helpers import (
    Transcript as _Transcript,
)
from tests.unit.operation._helpers import (
    build_conductor as _conductor,
)
from tests.unit.operation._helpers import (
    objective as _objective,
)
from tests.unit.operation._helpers import (
    objective_measurement as _objective_measurement,
)
from tests.unit.operation._helpers import (
    pass_block as _pass_block,
)
from tests.unit.operation._helpers import (
    point_to_captures as _point_to_captures,
)
from tests.unit.operation._helpers import (
    space as _space,
)


def _closed_pass(
    coordinate: float,
    value: float,
    *,
    kind: ActuationKind | None = None,
) -> SteeringObservation:
    """One already-closed pass as reconstructed from the record (self-describing)."""
    return SteeringObservation(
        point=SteeringPoint(coordinates={_MOTOR_ADDR: coordinate}),
        measurements=(
            Measurement(
                value=value,
                kind="Scalar",
                quality="Good",
                produced_at=_FIXED_NOW,
                name=_OBJECTIVE_NAME,
                units="pixel",
            ),
        ),
        actuation_kind=kind,
        succeeded=True,
    )


async def _conduct_from(
    conductor: Conductor,
    *,
    closed: tuple[SteeringObservation, ...],
    fsm_iteration_count: int,
    open_iteration_index: int | None,
    brain: InMemoryDecidePort,
) -> object:
    return await conductor.conduct_until_advised_from(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=_pass_block(),  # type: ignore[arg-type]
        decide_port=brain,
        objective=_objective(),
        space=_space(),
        objective_capture_name=_OBJECTIVE_NAME,
        point_to_captures=_point_to_captures,
        closed_observations=closed,
        fsm_iteration_count=fsm_iteration_count,
        open_iteration_index=open_iteration_index,
    )


@pytest.mark.unit
async def test_conduct_from_frontier_stop_completes_with_no_new_pass() -> None:
    """A frontier re-ask that returns STOP completes immediately, running no pass."""
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()  # no measurements queued: no pass may run
    brain = InMemoryDecidePort()
    # Two recovered passes -> frontier re-ask is at evidence.iteration_index 2.
    brain.set_advice_sequence(
        [
            SteeringAdvice(verdict=SteeringVerdict.STOP),  # 0: unused
            SteeringAdvice(verdict=SteeringVerdict.STOP),  # 1: unused
            SteeringAdvice(verdict=SteeringVerdict.STOP),  # 2: the frontier re-ask
        ]
    )
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await _conduct_from(
        conductor,
        closed=(_closed_pass(0.0, 2.0), _closed_pass(3.0, 0.5)),
        fsm_iteration_count=2,
        open_iteration_index=None,
        brain=brain,
    )

    assert result.succeeded is True  # type: ignore[attr-defined]
    assert transcript.events[0] == "resume_procedure"
    assert transcript.resume_boundaries == [2]
    assert transcript.events[-1] == "complete_procedure"
    # No pass ran: no start_iteration, no hardware write.
    assert transcript.start_iteration_indices == []


@pytest.mark.unit
async def test_conduct_from_frontier_measure_then_stop_runs_one_pass() -> None:
    """A frontier MEASURE runs one pass at the advised point, then a STOP completes."""
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(((_objective_measurement(0.2),),))  # one frontier pass
    brain = InMemoryDecidePort()
    # InMemoryDecidePort keys advice on evidence.iteration_index. 1 recovered
    # pass -> frontier re-ask at index len(closed)-1 = 0 (MEASURE 5.0). The new
    # pass runs as FSM iteration fsm_count+1 = 2; its post-pass advise is at
    # iteration_count-1 = 1 (STOP).
    brain.set_advice_sequence(
        [
            SteeringAdvice(
                verdict=SteeringVerdict.MEASURE,
                next_point=SteeringPoint(coordinates={_MOTOR_ADDR: 5.0}),
            ),  # 0: frontier re-ask
            SteeringAdvice(verdict=SteeringVerdict.STOP),  # 1: post-pass advise
        ]
    )
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await _conduct_from(
        conductor,
        closed=(_closed_pass(0.0, 2.0),),
        fsm_iteration_count=1,
        open_iteration_index=None,
        brain=brain,
    )

    assert result.succeeded is True  # type: ignore[attr-defined]
    # One recovered pass (fsm_count=1) -> the new pass is start_iteration[2].
    assert transcript.start_iteration_indices == [2]
    # The frontier MEASURE advised 5.0 -> the pass measured there.
    landed = await control.read(_MOTOR_ADDR)
    assert landed.value == pytest.approx(5.0)


@pytest.mark.unit
async def test_conduct_from_closes_a_dangling_open_iteration_before_the_frontier() -> None:
    """A pass left open by a mid-crash hold is ended before the loop starts.

    fsm_iteration_count=2 with only ONE recovered observation models a crash
    mid-pass-2 (pass 2 started + counted, no outcome survived). open_iteration
    _index=2 must be closed so the loop's next start_iteration (3) does not
    collide, and the frontier re-ask (over the 1 recovered observation) drives on.
    """
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(((_objective_measurement(0.2),),))
    brain = InMemoryDecidePort()
    # 1 recovered pass -> frontier re-ask at index 0 (MEASURE 6.0). The dangling
    # iteration is 2; the new pass is fsm_count+1 = 3, post-advise at index 2.
    brain.set_advice_sequence(
        [
            SteeringAdvice(
                verdict=SteeringVerdict.MEASURE,
                next_point=SteeringPoint(coordinates={_MOTOR_ADDR: 6.0}),
            ),  # 0: frontier re-ask (1 recovered observation)
            SteeringAdvice(verdict=SteeringVerdict.STOP),  # 1 unused
            SteeringAdvice(verdict=SteeringVerdict.STOP),  # 2: post-pass advise
        ]
    )
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await _conduct_from(
        conductor,
        closed=(_closed_pass(0.0, 2.0),),
        fsm_iteration_count=2,
        open_iteration_index=2,
        brain=brain,
    )

    assert result.succeeded is True  # type: ignore[attr-defined]
    # The dangling iteration 2 was ended first (before any new start_iteration).
    assert 2 in transcript.end_iteration_indices
    # The new pass is start_iteration[3] (fsm_count 2 + 1), no collision.
    assert transcript.start_iteration_indices == [3]


@pytest.mark.unit
async def test_conduct_from_folds_simulated_prefix_into_terminal_kind() -> None:
    """A simulated recovered prefix folds with a physical frontier -> not Physical."""
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(((_objective_measurement(0.2),),))
    brain = InMemoryDecidePort()
    # 2 recovered passes -> frontier re-ask at index 1 (MEASURE 4.0). The new
    # pass is fsm_count+1 = 3, post-advise at index 2.
    brain.set_advice_sequence(
        [
            SteeringAdvice(verdict=SteeringVerdict.STOP),  # 0 unused
            SteeringAdvice(
                verdict=SteeringVerdict.MEASURE,
                next_point=SteeringPoint(coordinates={_MOTOR_ADDR: 4.0}),
            ),  # 1: frontier re-ask (2 recovered observations)
            SteeringAdvice(verdict=SteeringVerdict.STOP),  # 2: post-pass advise
        ]
    )
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await _conduct_from(
        conductor,
        closed=(
            _closed_pass(0.0, 2.0, kind=ActuationKind.SIMULATED),
            _closed_pass(3.0, 0.5, kind=ActuationKind.SIMULATED),
        ),
        fsm_iteration_count=2,
        open_iteration_index=None,
        brain=brain,
    )

    assert result.actuation_kind is not None  # type: ignore[attr-defined]
    assert result.actuation_kind is not ActuationKind.PHYSICAL  # type: ignore[attr-defined]


@pytest.mark.unit
async def test_conduct_from_closed_passes_consume_no_hardware() -> None:
    """The recovered passes are replayed: only frontier passes drive the port.

    Exactly ONE measurement is queued: if a recovered pass re-measured, the
    sequence would exhaust and fail. Its success proves replay-not-re-run.
    """
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(((_objective_measurement(0.2),),))
    brain = InMemoryDecidePort()
    # 3 recovered passes -> frontier re-ask at index 2 (MEASURE 9.0). The new
    # pass is fsm_count+1 = 4, post-advise at index 3.
    brain.set_advice_sequence(
        [
            SteeringAdvice(verdict=SteeringVerdict.STOP),  # 0 unused
            SteeringAdvice(verdict=SteeringVerdict.STOP),  # 1 unused
            SteeringAdvice(
                verdict=SteeringVerdict.MEASURE,
                next_point=SteeringPoint(coordinates={_MOTOR_ADDR: 9.0}),
            ),  # 2: frontier re-ask (3 recovered observations)
            SteeringAdvice(verdict=SteeringVerdict.STOP),  # 3: post-pass advise
        ]
    )
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await _conduct_from(
        conductor,
        closed=(
            _closed_pass(0.0, 2.0),
            _closed_pass(3.0, 0.5),
            _closed_pass(6.0, 0.3),
        ),
        fsm_iteration_count=3,
        open_iteration_index=None,
        brain=brain,
    )

    assert result.succeeded is True  # type: ignore[attr-defined]
    assert transcript.resume_boundaries == [3]
    assert transcript.start_iteration_indices == [4]


@pytest.mark.unit
async def test_conduct_from_without_resume_handler_raises_runtime_error() -> None:
    """A Conductor missing the resume handler rejects conduct_from with RuntimeError."""
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    brain = InMemoryDecidePort()
    conductor = Conductor(
        control_port=control,
        append_step=_FakeAppendStep(),
        clock=FakeClock(_FIXED_NOW),
        id_generator=_FakeIdGen(),
        compute_port=compute,
    )

    with pytest.raises(RuntimeError, match="requires resume_procedure"):
        await _conduct_from(
            conductor,
            closed=(_closed_pass(0.0, 2.0),),
            fsm_iteration_count=1,
            open_iteration_index=None,
            brain=brain,
        )
