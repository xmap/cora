"""Replay-determinism property for `Conductor.conduct_until_advised` (S5).

The steered loop is the DECIDE-axis twin of the convergence loop, and like it
the loop is PURE in-process state driven from iteration 0: it never reads the
event store, it reconstructs the evidence each pass from a local observation
list, and the one-pass step block is pinned once and re-walked verbatim. So a
re-drive of the same loop over identical inputs, with a brain whose advice is a
pure function of the evidence, reproduces the run byte for byte: the same
iteration boundaries, the same seeded coordinates landing on the control port,
the same advice provenance on the ledger, and the same terminal.

SCOPE: the property is locked for the loop's DECISIONS, the FSM + iteration
boundaries, the evidence the brain weighed, the seeded coordinates, the advice
provenance, and the terminal. The per-step activity-append payload carries a
fresh event_id (and an append timestamp) by design, so that stream is
intentionally outside this property; the loop mints no other non-determinism.

That is the keystone the design memo named (the seed-the-captures mechanic is
"the ONLY one that is BOTH 6c-untouched AND replay-deterministic"). These tests
LOCK it for the two brains the loop can actually reach today (the stateless
InMemoryDecidePort and the real, equally-stateless GridWalkDecidePort), and one
invariant test records the scope decision on the record: the property holds with
NO advised-coordinate field on the iteration event.

CONDITIONAL ON A PURE-FUNCTION BRAIN. The property proven here is replay safety
for a brain whose advice depends only on the evidence (re-deriving the same
answer from the same observations). A NON-deterministic or stateful brain (a
real GP, gpCAM, an LLM) is NOT covered: re-querying it on replay could diverge.
Making replay safe for such a brain is a deferred build-#2 leg that re-seeds a
RECORDED next_point for closed passes and consults the brain only at the open
frontier; it needs three additive pieces together (an advised_next_point field
on the iteration event, a decide-loop resume entry, and a ValueCaptured
observation-replay channel) and should be earned WITH that first non-deterministic
adapter, not minted speculatively.
"""

import dataclasses
from dataclasses import dataclass
from uuid import UUID

import pytest

from cora.operation.adapters.grid_walk_decide_port import GridWalkDecidePort
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.in_memory_decide_port import InMemoryDecidePort
from cora.operation.aggregates.procedure.events import ProcedureIterationEnded
from cora.operation.conductor import ConductorResult
from cora.operation.features.end_iteration.command import EndProcedureIteration
from cora.operation.ports.decide_port import (
    DecidePort,
    SteeringAdvice,
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

# Fixed identifiers so two drives feed the brain byte-identical evidence (the
# SteeringEvidence carries procedure_id; uuid4 ids would make it differ between
# drives even though the loop behaviour does not depend on them).
_PROCEDURE_ID = UUID("00000000-0000-0000-0000-0000000000a1")
_PRINCIPAL_ID = UUID("00000000-0000-0000-0000-0000000000b2")
_CORRELATION_ID = UUID("00000000-0000-0000-0000-0000000000c3")

# Three objective metrics, none equal to the Satisfy target (0.0), so a grid
# walk runs to lattice exhaustion rather than an early objective-met Stop.
_METRICS = (2.0, 1.0, 0.5)


@dataclass
class _Drive:
    """The id-independent projections of one conduct_until_advised drive."""

    result: ConductorResult
    transcript: _Transcript
    received_evidence: tuple[SteeringEvidence, ...]
    final_motor: float


async def _drive(decide_port: DecidePort) -> _Drive:
    """Run one steered loop over fresh, identically-seeded fakes."""
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(tuple((_objective_measurement(v),) for v in _METRICS))
    conductor = _conductor(transcript, compute_port=compute, control_port=control)
    result = await conductor.conduct_until_advised(
        procedure_id=_PROCEDURE_ID,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        steps=_pass_block(),  # type: ignore[arg-type]
        decide_port=decide_port,
        objective=_objective(),
        space=_space(),
        objective_capture_name=_OBJECTIVE_NAME,
        point_to_captures=_point_to_captures,
    )
    final = await control.read(_MOTOR_ADDR)
    received = getattr(decide_port, "received_evidence", ())
    return _Drive(
        result=result,
        transcript=transcript,
        received_evidence=received,
        final_motor=final.value,
    )


def _seeded_brain() -> InMemoryDecidePort:
    """A stateless brain that measures twice then stops (3 passes total)."""
    brain = InMemoryDecidePort()
    brain.set_advice_sequence(
        [
            SteeringAdvice(
                verdict=SteeringVerdict.MEASURE,
                next_point=SteeringPoint(coordinates={_MOTOR_ADDR: 3.0}),
            ),
            SteeringAdvice(
                verdict=SteeringVerdict.MEASURE,
                next_point=SteeringPoint(coordinates={_MOTOR_ADDR: 6.0}),
            ),
            SteeringAdvice(verdict=SteeringVerdict.STOP),
        ]
    )
    return brain


@pytest.mark.unit
async def test_conduct_until_advised_redrive_reproduces_identical_transcript() -> None:
    """Re-driving the same stateless-brain loop yields a byte-identical transcript."""
    first = await _drive(_seeded_brain())
    second = await _drive(_seeded_brain())

    assert first.result.succeeded is True
    # The whole FSM + iteration-boundary trace matches event for event.
    assert first.transcript.events == second.transcript.events
    assert first.transcript.events[-1] == "complete_procedure"
    assert first.transcript.start_iteration_indices == second.transcript.start_iteration_indices
    assert first.transcript.start_iteration_indices == [1, 2, 3]
    assert first.transcript.end_iteration_converged == second.transcript.end_iteration_converged
    assert first.transcript.end_iteration_advised_stop == (
        second.transcript.end_iteration_advised_stop
    )
    assert first.transcript.end_iteration_advised_stop == [False, False, True]
    assert first.transcript.end_iteration_provenance == second.transcript.end_iteration_provenance


@pytest.mark.unit
async def test_conduct_until_advised_redrive_reproduces_identical_seeded_coordinates() -> None:
    """Re-driving reproduces the same seeded coordinates and the same evidence.

    The seed-the-captures keystone is what must be deterministic: each pass
    seeds the same point, the SetpointStep resolves the same write, and the
    brain sees the same observation history. Comparing the full evidence each
    drive showed the brain (objective, space, observations with their measured
    points) locks the reproduction, and the final motor read confirms the last
    advised point landed on the control port identically.
    """
    first = await _drive(_seeded_brain())
    second = await _drive(_seeded_brain())

    assert first.received_evidence == second.received_evidence
    # Pass 1 is the probe (axis lower 0.0); passes 2 and 3 are the advised points.
    seeded_points = [
        ev.observations[-1].point.coordinates[_MOTOR_ADDR] for ev in first.received_evidence
    ]
    assert seeded_points == [0.0, 3.0, 6.0]
    assert first.final_motor == pytest.approx(6.0)
    assert first.final_motor == pytest.approx(second.final_motor)


@pytest.mark.unit
async def test_conduct_until_advised_redrive_under_grid_walk_reproduces_identical_run() -> None:
    """A real stateless brain (GridWalkDecidePort) reproduces the run on re-drive.

    GridWalk derives its lattice position from len(observations), a pure
    function of the evidence, so it is the honest end-to-end check that the
    determinism is the loop's, not an artifact of the seeded fake. With three
    lattice points the loop probes 0.0 then walks 5.0, 10.0, then the grid is
    exhausted and it stops.
    """
    first = await _drive(GridWalkDecidePort(points_per_axis=3))
    second = await _drive(GridWalkDecidePort(points_per_axis=3))

    assert first.result.succeeded is True
    assert first.transcript.events == second.transcript.events
    assert first.transcript.events[-1] == "complete_procedure"
    assert first.transcript.start_iteration_indices == [1, 2, 3]
    assert first.transcript.end_iteration_advised_stop == [False, False, True]
    assert first.transcript.end_iteration_provenance == second.transcript.end_iteration_provenance
    assert first.final_motor == pytest.approx(10.0)
    assert first.final_motor == pytest.approx(second.final_motor)


@pytest.mark.unit
def test_conduct_until_advised_replay_determinism_needs_no_recorded_next_point() -> None:
    """The iteration carriers record NO advised coordinate; determinism is intrinsic.

    conduct_until_advised reproduces identically because the brain is a pure
    function of the evidence and the step block is pinned once, NOT because a
    next_point was persisted. These EXACT field sets pin that scope decision (the
    same forcing-function the projection-metadata frozenset tests use): neither
    the EndProcedureIteration command nor the ProcedureIterationEnded event
    carries a point/coordinate today, and adding `advised_next_point` so a replay
    can re-seed closed passes for a NON-deterministic brain (for example gpCAM)
    is a deferred build-#2 leg that MUST consciously update these sets.
    """
    assert {f.name for f in dataclasses.fields(EndProcedureIteration)} == {
        "procedure_id",
        "iteration_index",
        "converged",
        "reason",
        "advised_stop",
        "reasoning",
        "confidence",
        "confidence_source",
        "alternatives",
        "model_ref",
    }
    assert {f.name for f in dataclasses.fields(ProcedureIterationEnded)} == {
        "procedure_id",
        "iteration_index",
        "converged",
        "reason",
        "occurred_at",
        "advised_stop",
        "reasoning",
        "confidence",
        "confidence_source",
        "alternatives",
        "model_ref",
    }
