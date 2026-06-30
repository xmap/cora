"""Tests for the ExperimentSteerer across-procedure driver (steer_experiment).

White-box tests of the proactive across-procedure loop: it drives the
conduct_until_advised handler per procedure, applies the v1 deterministic
disposition rule (Continue / Conclude / Hold), records each across-procedure
Decision via the 2a seam (signed, monotonic turn), threads a Hold into an
agent-issued hold_procedure, and stands down if the agent is unseeded.

The conduct + hold handlers are FAKES returning canned results / recording calls,
so the loop's sequencing + dispositions are exercised without a real conductor.
The Decision writes go through a real in-memory kernel with the seeded agent.
"""

# white-box test of the runtime internals (private functions / constants)
# pyright: reportPrivateUsage=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.seed_experiment_steerer import (
    EXPERIMENT_STEERER_AGENT_ID,
    seed_experiment_steerer_agent,
)
from cora.api._experiment_steerer import _derive_decision_id, steer_experiment
from cora.decision.aggregates.decision import load_decision
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, UUIDv7Generator
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.adapters.decide_port_config import DecidePortConfig
from cora.operation.conductor import ConductorFailure
from cora.operation.features.conduct_until_advised import (
    ConductUntilAdvised,
    ConductUntilAdvisedResult,
)
from cora.operation.features.hold_procedure import HoldProcedure
from cora.operation.ports.decide_port import (
    SteeringAxis,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringSpace,
)
from cora.operation.ports.measurement import Measurement

_NOW = datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC)
_OBJECTIVE_NAME = "rotation_center"
_TARGET = 1024.0


def _kernel() -> Kernel:
    return make_inmemory_kernel(
        settings=Settings(),  # type: ignore[call-arg]
        clock=FakeClock(_NOW),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
    )


def _objective() -> SteeringObjective:
    return SteeringObjective(
        kind=SteeringObjectiveKind.SATISFY,
        target_measurement_name=_OBJECTIVE_NAME,
        target_value=_TARGET,
    )


def _space() -> SteeringSpace:
    return SteeringSpace(axes=(SteeringAxis(name="theta", lower=-5.0, upper=5.0),))


def _measurement(value: float) -> Measurement:
    return Measurement(
        value=value, kind="Scalar", quality="Good", produced_at=_NOW, name=_OBJECTIVE_NAME
    )


def _ok_result(procedure_id: UUID, center: float) -> ConductUntilAdvisedResult:
    """A succeeded steered procedure whose final measurement is `center`."""
    return ConductUntilAdvisedResult(
        procedure_id=procedure_id,
        completed_count=2,
        succeeded=True,
        failure=None,
        actuation_kind="Simulated",
        measurements=(_measurement(center),),
    )


def _faulted_result(procedure_id: UUID) -> ConductUntilAdvisedResult:
    return ConductUntilAdvisedResult(
        procedure_id=procedure_id,
        completed_count=0,
        succeeded=False,
        failure=ConductorFailure(
            step_index=0,
            source_kind="setpoint",
            target="theta",
            error_class="ControlNotConnectedError",
            message="theta not connected",
        ),
    )


class _FakeConduct:
    """Fake conduct_until_advised handler: returns canned results keyed by call order."""

    def __init__(self, results_by_proc: dict[UUID, ConductUntilAdvisedResult]) -> None:
        self._results = results_by_proc
        self.calls: list[ConductUntilAdvised] = []

    async def __call__(
        self,
        command: ConductUntilAdvised,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductUntilAdvisedResult:
        self.calls.append(command)
        return self._results[command.procedure_id]


class _FakeHold:
    """Fake hold_procedure handler: records the commands issued."""

    def __init__(self) -> None:
        self.calls: list[HoldProcedure] = []

    async def __call__(
        self,
        command: HoldProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        self.calls.append(command)


async def _steer(
    kernel: Kernel,
    *,
    procedure_ids: list[UUID],
    results: dict[UUID, ConductUntilAdvisedResult],
    hold: _FakeHold | None = None,
):
    conduct = _FakeConduct(results)
    hold = hold or _FakeHold()
    steps = await steer_experiment(
        kernel,
        conduct=conduct,
        hold_procedure=hold,
        procedure_ids=procedure_ids,
        objective=_objective(),
        space=_space(),
        objective_capture_name=_OBJECTIVE_NAME,
        decide=DecidePortConfig(substrate="grid_walk"),
        principal_id=EXPERIMENT_STEERER_AGENT_ID,
        correlation_id=uuid4(),
    )
    return steps, conduct, hold


@pytest.mark.unit
def test_driver_choice_constants_are_experiment_steering_choices() -> None:
    """The driver's local choice constants must be members of the closed vocabulary.

    They are re-declared string literals; this pins them to ExperimentSteeringChoice
    so a future enum rename cannot silently leave the driver emitting stale choices.
    """
    from cora.api._experiment_steerer import (
        _CHOICE_CONCLUDE,
        _CHOICE_CONTINUE,
        _CHOICE_HOLD,
    )
    from cora.decision.aggregates.decision import EXPERIMENT_STEERING_CHOICES

    assert {_CHOICE_CONTINUE, _CHOICE_CONCLUDE, _CHOICE_HOLD} <= EXPERIMENT_STEERING_CHOICES


@pytest.mark.unit
async def test_steer_continues_until_objective_met_then_concludes() -> None:
    """Two procedures miss the target (Continue), the third meets it (Conclude)."""
    kernel = _kernel()
    await seed_experiment_steerer_agent(kernel)
    p0, p1, p2, p3 = uuid4(), uuid4(), uuid4(), uuid4()
    results = {
        p0: _ok_result(p0, 1030.0),
        p1: _ok_result(p1, 1026.0),
        p2: _ok_result(p2, _TARGET),  # objective met -> Conclude
        p3: _ok_result(p3, _TARGET),  # never reached
    }

    steps, conduct, _hold = await _steer(kernel, procedure_ids=[p0, p1, p2, p3], results=results)

    assert [s.choice for s in steps] == ["Continue", "Continue", "Conclude"]
    assert [s.turn for s in steps] == [0, 1, 2]
    assert len(conduct.calls) == 3  # p3 never steered (loop stopped on Conclude)
    # Each turn recorded its own distinct Decision (fresh id per turn).
    decision_ids = [s.decision_id for s in steps]
    assert all(d is not None for d in decision_ids)
    assert len(set(decision_ids)) == len(decision_ids)
    for s in steps:
        assert s.decision_id is not None
        decision = await load_decision(kernel.event_store, s.decision_id)
        assert decision is not None
        assert decision.context.value == "ExperimentSteering"
        assert decision.choice.value == s.choice
        assert decision.decided_by == EXPERIMENT_STEERER_AGENT_ID


@pytest.mark.unit
async def test_steer_holds_on_faulted_procedure_and_links_decision() -> None:
    """A faulted steered procedure -> Hold, and an agent-issued hold_procedure
    carries the recorded Decision id via decided_by_decision_id."""
    kernel = _kernel()
    await seed_experiment_steerer_agent(kernel)
    p0, p1 = uuid4(), uuid4()
    results = {p0: _faulted_result(p0), p1: _ok_result(p1, _TARGET)}

    steps, conduct, hold = await _steer(kernel, procedure_ids=[p0, p1], results=results)

    assert [s.choice for s in steps] == ["Hold"]
    assert len(conduct.calls) == 1  # stopped after the fault; p1 never steered
    assert len(hold.calls) == 1
    held = hold.calls[0]
    assert held.procedure_id == p0
    assert held.decided_by_decision_id == steps[0].decision_id


@pytest.mark.unit
async def test_steer_stops_on_list_exhaustion_all_continue() -> None:
    """If no procedure meets the objective, the loop ends when the list is exhausted."""
    kernel = _kernel()
    await seed_experiment_steerer_agent(kernel)
    p0, p1 = uuid4(), uuid4()
    results = {p0: _ok_result(p0, 1030.0), p1: _ok_result(p1, 1029.0)}

    steps, conduct, hold = await _steer(kernel, procedure_ids=[p0, p1], results=results)

    assert [s.choice for s in steps] == ["Continue", "Continue"]
    assert len(conduct.calls) == 2
    assert hold.calls == []


@pytest.mark.unit
async def test_steer_records_signed_decisions() -> None:
    """Each across-procedure Decision is signed (agent rows are signed)."""
    import dataclasses

    from cora.infrastructure.signing import verify_signature
    from tests.unit.agent._helpers import Ed25519FakeSigner

    signer = Ed25519FakeSigner(kid="kid-experiment-steerer")
    kernel = dataclasses.replace(_kernel(), signer=signer)
    await seed_experiment_steerer_agent(kernel)
    p0 = uuid4()

    steps, _conduct, _hold = await _steer(
        kernel, procedure_ids=[p0], results={p0: _ok_result(p0, _TARGET)}
    )

    assert steps[0].choice == "Conclude"
    assert steps[0].decision_id is not None
    events, _ = await kernel.event_store.load("Decision", steps[0].decision_id)
    stored = events[0]
    assert stored.signature is not None
    assert stored.signature_kid == "kid-experiment-steerer"

    async def _resolver(kid: str) -> bytes:
        return signer.public_key_bytes

    await verify_signature(
        event_type=stored.event_type,
        payload=stored.payload,
        signature=stored.signature,
        kid=stored.signature_kid,
        resolve_public_key=_resolver,
    )


@pytest.mark.unit
async def test_steer_stands_down_when_agent_unseeded() -> None:
    """No seeded agent -> the first turn records nothing (None) and the loop stops."""
    kernel = _kernel()  # ExperimentSteerer NOT seeded
    p0, p1 = uuid4(), uuid4()
    results = {p0: _ok_result(p0, 1030.0), p1: _ok_result(p1, 1029.0)}

    steps, conduct, hold = await _steer(kernel, procedure_ids=[p0, p1], results=results)

    assert len(steps) == 1  # broke after the first stand-down
    assert steps[0].decision_id is None
    assert len(conduct.calls) == 1
    assert hold.calls == []
    # Nothing was written.
    events, _ = await kernel.event_store.load("Decision", _derive_decision_id(p0, 0))
    assert events == []
