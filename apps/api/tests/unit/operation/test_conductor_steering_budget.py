"""The steered loop enforces its declared `SteeringBudget`, not merely reports it.

`SteeringBudget` (iterations_remaining, wall_clock_seconds_remaining) used to
be threaded into `SteeringEvidence` for the brain to weigh and nothing else:
a caller-declared cap that no code ever compared against anything. These
tests pin the loop-level guard (`_budget_exhausted` in `conductor.py`),
checked at the top of every pass, before `start_iteration`, alongside the
stand-down check and the absolute iteration ceiling.

Per [[project_decide_layer_stage1_design]]'s locked decision, an exhausted
budget completes the Procedure exactly as a brain-advised Stop does
(`_complete_advised`), recording WHICH dimension ran out as
`ProcedureCompleted.termination_reason`. It never aborts: the loop did
exactly what it was asked, which is the opposite of an abort's "interrupted
mid-pass" or "the criterion was never met".

Both dimensions are PER-CALL, not cumulative across a resume (see
`SteeringBudget`'s own docstring for why a cumulative accounting would be
unenforceable). The resume test in `test_conductor_conduct_until_advised_from.py`
pins that a resumed segment gets its own fresh allowance rather than the
prior segment's remainder.
"""

from uuid import uuid4

import pytest

from cora.infrastructure.ports.clock import FakeMonotonicClock
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.in_memory_decide_port import InMemoryDecidePort
from cora.operation.aggregates.procedure import ProcedureTerminationReason
from cora.operation.conductor import Conductor, ConductorResult
from cora.operation.ports.decide_port import (
    SteeringAdvice,
    SteeringBudget,
    SteeringEvidence,
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


def _measure_forever(n: int) -> list[SteeringAdvice]:
    """`n` Measure verdicts then a Stop, so a brain left unbudgeted terminates.

    Seeded with more MEASUREs than any budget in this file allows, so
    deleting the guard under test yields a DIFFERENT, well-defined run
    (complete on the brain's own Stop at pass n+1) rather than a hang.
    """
    return [
        SteeringAdvice(
            verdict=SteeringVerdict.MEASURE,
            next_point=SteeringPoint(coordinates={_MOTOR_ADDR: float(i + 1)}),
        )
        for i in range(n)
    ] + [SteeringAdvice(verdict=SteeringVerdict.STOP)]


class _ClockAdvancingBrain:
    """Always MEASUREs, advancing the injected `FakeMonotonicClock` by a fixed
    amount per call, so a wall-clock budget trips at a known, exact pass.

    The loop times itself off the monotonic clock, never `self._clock`
    (`conductor.py`'s own comment: wall time can step backwards under an NTP
    correction). A brain that advanced `self._clock` instead would prove
    nothing about the guard under test.
    """

    def __init__(self, clock: FakeMonotonicClock, seconds_per_call: float) -> None:
        self._clock = clock
        self._seconds_per_call = seconds_per_call

    async def advise_next(self, evidence: SteeringEvidence) -> SteeringAdvice:
        _ = evidence
        self._clock.advance(self._seconds_per_call)
        return SteeringAdvice(
            verdict=SteeringVerdict.MEASURE,
            next_point=SteeringPoint(coordinates={_MOTOR_ADDR: 1.0}),
        )

    async def aclose(self) -> None:
        return None


def _build(
    passes: int = 8, *, monotonic_clock: FakeMonotonicClock | None = None
) -> tuple[Conductor, _Transcript, InMemoryComputePort]:
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(
        tuple((_objective_measurement(1.0),) for _ in range(passes + 2))
    )
    conductor = _conductor(
        transcript,
        compute_port=compute,
        control_port=control,
        monotonic_clock=monotonic_clock,
    )
    return conductor, transcript, compute


async def _run(
    conductor: Conductor, brain: object, *, budget: SteeringBudget | None
) -> ConductorResult:
    return await conductor.conduct_until_advised(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=_pass_block(),  # type: ignore[arg-type]
        decide_port=brain,  # type: ignore[arg-type]
        objective=_objective(),
        space=_space(),
        objective_capture_name=_OBJECTIVE_NAME,
        point_to_captures=_point_to_captures,
        budget=budget,
    )


@pytest.mark.unit
async def test_an_iteration_budget_stops_the_loop_after_exactly_that_many_passes() -> None:
    conductor, transcript, _ = _build(passes=8)
    brain = InMemoryDecidePort()
    brain.set_advice_sequence(_measure_forever(8))

    result = await _run(conductor, brain, budget=SteeringBudget(iterations_remaining=3))

    assert transcript.start_iteration_indices == [1, 2, 3]
    assert transcript.events[-1] == "complete_procedure"
    assert "abort_procedure" not in transcript.events
    assert result.succeeded is True
    assert transcript.complete_termination_reasons == [
        ProcedureTerminationReason.BUDGET_ITERATIONS_EXHAUSTED
    ]


@pytest.mark.unit
async def test_a_wall_clock_budget_stops_the_loop_when_the_time_is_spent() -> None:
    monotonic = FakeMonotonicClock()
    conductor, transcript, _ = _build(passes=8, monotonic_clock=monotonic)
    brain = _ClockAdvancingBrain(monotonic, seconds_per_call=10.0)

    result = await _run(conductor, brain, budget=SteeringBudget(wall_clock_seconds_remaining=25.0))

    # pass1 -> clock=10s (10<25, proceed); pass2 -> 20s (20<25, proceed);
    # pass3 -> 30s (30>=25 at the NEXT loop-top check, so pass3 is the last).
    assert transcript.start_iteration_indices == [1, 2, 3]
    assert result.succeeded is True
    assert transcript.complete_termination_reasons == [
        ProcedureTerminationReason.BUDGET_WALL_CLOCK_EXHAUSTED
    ]


@pytest.mark.unit
async def test_a_zero_iteration_budget_stops_before_the_first_pass() -> None:
    """`iterations_remaining=0` is a real wire input (the field is `ge=0`, not
    `gt=0`), and it must refuse to run even a single pass: the brain is never
    consulted at all."""
    conductor, transcript, _ = _build(passes=8)
    brain = InMemoryDecidePort()
    brain.set_advice_sequence(_measure_forever(8))

    result = await _run(conductor, brain, budget=SteeringBudget(iterations_remaining=0))

    assert transcript.start_iteration_indices == []
    assert result.completed_count == 0
    assert brain.received_evidence == ()
    assert transcript.complete_termination_reasons == [
        ProcedureTerminationReason.BUDGET_ITERATIONS_EXHAUSTED
    ]


@pytest.mark.unit
async def test_a_wall_clock_budget_trips_at_the_exact_boundary_not_past_it() -> None:
    """`>=`, not `>`: elapsed time EQUAL to the remaining budget must already
    stop the loop, mirroring `iterations_remaining=0` stopping before pass 1
    rather than requiring passes_this_call to exceed it.

    Iterations is deliberately left unset, unlike the "both dimensions"
    tie-break test: that test's numbers happen to satisfy the ITERATIONS
    comparison at the same instant, so it cannot tell a correct `>=` on the
    wall-clock arm from a buggy `>` (iterations, checked first, fires
    either way). Isolating the dimension is what this test is for.
    """
    monotonic = FakeMonotonicClock()
    conductor, transcript, _ = _build(passes=8, monotonic_clock=monotonic)
    brain = _ClockAdvancingBrain(monotonic, seconds_per_call=20.0)

    await _run(conductor, brain, budget=SteeringBudget(wall_clock_seconds_remaining=20.0))

    # pass1 -> clock=20.0s exactly. The top-of-loop check before pass 2 sees
    # elapsed_ms == wall_clock_seconds_remaining * 1000.0 precisely: `>=`
    # stops HERE, so only 1 pass runs. A `>` off-by-one would let pass 2
    # start (elapsed 20000 > 20000 is False) and only stop after pass 2.
    assert transcript.start_iteration_indices == [1]
    assert transcript.complete_termination_reasons == [
        ProcedureTerminationReason.BUDGET_WALL_CLOCK_EXHAUSTED
    ]


@pytest.mark.unit
async def test_the_brains_stop_wins_over_an_exhausted_budget_on_the_same_turn() -> None:
    """A brain that advises Stop on the last budgeted pass completes for ITS
    reason, not the budget's: the Stop check is at the bottom of a pass, the
    budget check at the top of the next, so a Stop on pass 1 never reaches a
    second budget check at all."""
    conductor, transcript, _ = _build(passes=8)
    brain = InMemoryDecidePort()  # unseeded: advises Stop immediately

    result = await _run(conductor, brain, budget=SteeringBudget(iterations_remaining=1))

    assert transcript.start_iteration_indices == [1]
    assert result.succeeded is True
    assert transcript.complete_termination_reasons == [None]


@pytest.mark.unit
async def test_an_exhausted_budget_leaves_no_iteration_open() -> None:
    """The check fires at the loop top, so every started pass is also closed
    and the complete is the only FSM transition left to make."""
    conductor, transcript, _ = _build(passes=8)
    brain = InMemoryDecidePort()
    brain.set_advice_sequence(_measure_forever(8))

    await _run(conductor, brain, budget=SteeringBudget(iterations_remaining=3))

    assert transcript.start_iteration_indices == transcript.end_iteration_indices


@pytest.mark.unit
async def test_an_exhausted_budget_names_the_dimension_that_ran_out() -> None:
    conductor_a, transcript_a, _ = _build(passes=8)
    brain_a = InMemoryDecidePort()
    brain_a.set_advice_sequence(_measure_forever(8))
    await _run(conductor_a, brain_a, budget=SteeringBudget(iterations_remaining=2))

    monotonic = FakeMonotonicClock()
    conductor_b, transcript_b, _ = _build(passes=8, monotonic_clock=monotonic)
    brain_b = _ClockAdvancingBrain(monotonic, seconds_per_call=10.0)
    await _run(conductor_b, brain_b, budget=SteeringBudget(wall_clock_seconds_remaining=15.0))

    assert transcript_a.complete_termination_reasons == [
        ProcedureTerminationReason.BUDGET_ITERATIONS_EXHAUSTED
    ]
    assert transcript_b.complete_termination_reasons == [
        ProcedureTerminationReason.BUDGET_WALL_CLOCK_EXHAUSTED
    ]
    assert transcript_a.complete_termination_reasons != transcript_b.complete_termination_reasons


@pytest.mark.unit
async def test_both_dimensions_spent_on_the_same_turn_records_the_countable_one() -> None:
    """Iterations is checked first in `_budget_exhausted`. Chosen numbers make
    both dimensions cross their threshold at the SAME loop-top check (after
    pass 1: passes_this_call=1 meets iterations_remaining=1, and elapsed=20s
    meets wall_clock_seconds_remaining=20.0 at once), so the tie is real, not
    incidental."""
    monotonic = FakeMonotonicClock()
    conductor, transcript, _ = _build(passes=8, monotonic_clock=monotonic)
    brain = _ClockAdvancingBrain(monotonic, seconds_per_call=20.0)

    await _run(
        conductor,
        brain,
        budget=SteeringBudget(iterations_remaining=1, wall_clock_seconds_remaining=20.0),
    )

    assert transcript.start_iteration_indices == [1]
    assert transcript.complete_termination_reasons == [
        ProcedureTerminationReason.BUDGET_ITERATIONS_EXHAUSTED
    ]


@pytest.mark.unit
async def test_no_budget_leaves_the_loop_uncapped() -> None:
    conductor, transcript, _ = _build(passes=8)
    brain = InMemoryDecidePort()
    brain.set_advice_sequence(_measure_forever(3))

    result = await _run(conductor, brain, budget=None)

    assert transcript.start_iteration_indices == [1, 2, 3, 4]
    assert result.succeeded is True
    assert transcript.complete_termination_reasons == [None]


@pytest.mark.unit
async def test_an_unset_iteration_dimension_never_trips_even_past_a_huge_pass_count() -> None:
    """Only `wall_clock_seconds_remaining` is set; a brain that runs far more
    passes than any plausible iteration cap must stop on the CLOCK, proving
    the unset iterations dimension is skipped rather than treated as zero."""
    monotonic = FakeMonotonicClock()
    conductor, transcript, _ = _build(passes=50, monotonic_clock=monotonic)
    brain = _ClockAdvancingBrain(monotonic, seconds_per_call=10.0)

    await _run(conductor, brain, budget=SteeringBudget(wall_clock_seconds_remaining=15.0))

    assert transcript.start_iteration_indices == [1, 2]
    assert transcript.complete_termination_reasons == [
        ProcedureTerminationReason.BUDGET_WALL_CLOCK_EXHAUSTED
    ]


@pytest.mark.unit
async def test_an_unset_wall_clock_dimension_never_trips_even_past_a_huge_elapsed_time() -> None:
    """Only `iterations_remaining` is set; a brain that burns a huge amount of
    (fake) wall time per call must stop on the PASS COUNT, proving the unset
    wall-clock dimension is skipped rather than treated as zero."""
    monotonic = FakeMonotonicClock()
    conductor, transcript, _ = _build(passes=8, monotonic_clock=monotonic)
    brain = _ClockAdvancingBrain(monotonic, seconds_per_call=100_000.0)

    await _run(conductor, brain, budget=SteeringBudget(iterations_remaining=2))

    assert transcript.start_iteration_indices == [1, 2]
    assert transcript.complete_termination_reasons == [
        ProcedureTerminationReason.BUDGET_ITERATIONS_EXHAUSTED
    ]
