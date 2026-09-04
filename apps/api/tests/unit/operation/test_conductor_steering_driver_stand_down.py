"""The steered loop re-reads its driver's stand-down switch every iteration.

`conduct_until_advised` authorizes once, at entry, and that authz already
consults principal liveness. But the loop it guards can run for dozens of
passes, so a single read at the top means an operator switching the driving
agent off waits out the whole loop. These tests pin the re-read at each
iteration boundary.

Held, not aborted: the Procedure is healthy and its measured passes are worth
keeping. Standing an agent down means "stop acting", not "destroy the run".

The check is OPT-IN by driver id, and once opted in it is mandatory: a caller
that names a driver but wires no lookup raises rather than silently proceeding
without the switch. A permissive default would make the check absent in
exactly the deployment that forgot to wire it.
"""

from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.principal_liveness_lookup import PrincipalLiveness
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.in_memory_decide_port import InMemoryDecidePort
from cora.operation.conductor import Conductor, ConductorResult
from cora.operation.ports.decide_port import (
    SteeringAdvice,
    SteeringPoint,
    SteeringVerdict,
)
from tests.unit.operation._helpers import (
    MOTOR_ADDR as _MOTOR_ADDR,
)
from tests.unit.operation._helpers import (
    OBJECTIVE_NAME as _OBJECTIVE_NAME,
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

_DRIVER_ID = UUID("01900000-0000-7000-8000-0000577f0001")


class _ScriptedLiveness:
    """Reports ACTIVE for the first `active_for` reads, then DEACTIVATED.

    Scripted rather than fixed so a test can place the stand-down at a
    specific iteration boundary and prove the loop stopped THERE, not merely
    that it stopped.
    """

    def __init__(self, active_for: int) -> None:
        self._active_for = active_for
        self.reads = 0

    async def liveness_of(self, principal_id: UUID) -> PrincipalLiveness:
        self.reads += 1
        if self.reads <= self._active_for:
            return PrincipalLiveness.ACTIVE
        return PrincipalLiveness.DEACTIVATED


class _UnregisteredLiveness:
    async def liveness_of(self, principal_id: UUID) -> PrincipalLiveness:
        return PrincipalLiveness.UNREGISTERED


class _NeverCalledLiveness:
    def __init__(self) -> None:
        self.reads = 0

    async def liveness_of(self, principal_id: UUID) -> PrincipalLiveness:
        self.reads += 1
        return PrincipalLiveness.ACTIVE


def _measure(n: int) -> list[SteeringAdvice]:
    """`n` Measure verdicts then a Stop, so a loop left to itself terminates."""
    return [
        SteeringAdvice(
            verdict=SteeringVerdict.MEASURE,
            next_point=SteeringPoint(coordinates={_MOTOR_ADDR: float(i + 1)}),
        )
        for i in range(n)
    ] + [SteeringAdvice(verdict=SteeringVerdict.STOP)]


def _build(
    liveness: object | None, *, passes: int = 8
) -> tuple[Conductor, _Transcript, InMemoryDecidePort]:
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(
        tuple((_objective_measurement(1.0),) for _ in range(passes + 2))
    )
    brain = InMemoryDecidePort()
    brain.set_advice_sequence(_measure(passes))
    conductor = _conductor(
        transcript,
        compute_port=compute,
        control_port=control,
        principal_liveness_lookup=liveness,
    )
    return conductor, transcript, brain


async def _run(
    conductor: Conductor, brain: InMemoryDecidePort, *, driver_id: UUID | None
) -> ConductorResult:
    return await conductor.conduct_until_advised(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=_pass_block(),  # type: ignore[arg-type]
        decide_port=brain,
        objective=_objective(),
        space=_space(),
        objective_capture_name=_OBJECTIVE_NAME,
        point_to_captures=_point_to_captures,
        steering_driver_id=driver_id,
    )


@pytest.mark.unit
async def test_loop_holds_at_the_boundary_where_the_driver_was_stood_down() -> None:
    liveness = _ScriptedLiveness(active_for=2)
    conductor, transcript, brain = _build(liveness)

    result = await _run(conductor, brain, driver_id=_DRIVER_ID)

    assert result.held is True
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "SteeringDriverStoodDown"
    assert result.failure.target == "hold"
    # Two passes ran, the third boundary parked it: the loop stopped WHERE the
    # switch flipped, not merely at some point after.
    assert transcript.start_iteration_indices == [1, 2]
    assert "hold_procedure" in " ".join(transcript.events)
    assert "abort_procedure" not in transcript.events
    assert "complete_procedure" not in transcript.events


@pytest.mark.unit
async def test_stand_down_leaves_no_iteration_open() -> None:
    """The check fires at the loop top, so every started pass is also closed
    and the hold is the only FSM transition left to make."""
    conductor, transcript, brain = _build(_ScriptedLiveness(active_for=2))

    await _run(conductor, brain, driver_id=_DRIVER_ID)

    assert transcript.start_iteration_indices == transcript.end_iteration_indices


@pytest.mark.unit
async def test_unregistered_driver_counts_as_stood_down() -> None:
    """A driver whose Actor stream does not exist cannot have been switched
    on; treating "cannot find it" as "carry on" is a silent pass."""
    conductor, transcript, brain = _build(_UnregisteredLiveness())

    result = await _run(conductor, brain, driver_id=_DRIVER_ID)

    assert result.held is True
    assert transcript.start_iteration_indices == []


@pytest.mark.unit
async def test_active_driver_runs_the_loop_to_its_own_terminal() -> None:
    """The check must not perturb a loop whose driver stays switched on: the
    brain's Stop still completes the Procedure."""
    liveness = _ScriptedLiveness(active_for=99)
    conductor, transcript, brain = _build(liveness)

    result = await _run(conductor, brain, driver_id=_DRIVER_ID)

    assert result.held is False
    assert "complete_procedure" in transcript.events
    # Exactly one read per iteration boundary, and no more: the loop exits
    # from inside the final pass on the brain's Stop, so it never returns to
    # the top for another read.
    assert liveness.reads == len(transcript.start_iteration_indices)


@pytest.mark.unit
async def test_no_driver_never_consults_the_switch() -> None:
    """A human calling the route owns their own conduct and has no agent
    stand-down switch; the loop must not invent one for them."""
    liveness = _NeverCalledLiveness()
    conductor, transcript, brain = _build(liveness)

    result = await _run(conductor, brain, driver_id=None)

    assert liveness.reads == 0
    assert result.held is False
    assert "complete_procedure" in transcript.events


@pytest.mark.unit
async def test_driver_named_without_a_lookup_raises() -> None:
    """Opt-in by driver id makes the switch mandatory. The permissive-default
    shape every sibling lookup ships would make this check silently absent in
    exactly the deployment that forgot to wire it."""
    conductor, _, brain = _build(None)

    with pytest.raises(ValueError, match="stand-down switch cannot be read"):
        await _run(conductor, brain, driver_id=_DRIVER_ID)
