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

from uuid import uuid4

import pytest

from cora.infrastructure.ports.clock import FakeClock
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.in_memory_decide_port import InMemoryDecidePort
from cora.operation.conductor import Conductor
from cora.operation.ports.decide_port import (
    DecideTimeoutError,
    SteeringAdvice,
    SteeringEvidence,
    SteeringPoint,
    SteeringVerdict,
)
from cora.shared.decision_signals import DecisionConfidenceSource
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
