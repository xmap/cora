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

from dataclasses import replace as dc_replace
from datetime import UTC, datetime
from uuid import UUID, uuid4, uuid5

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
from cora.infrastructure.ports.llm import LLMUsage
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
    SteeringLlmCall,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringSpace,
)
from cora.operation.ports.measurement import Measurement
from tests.unit.agent._helpers import FakeInferenceRecorder

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
    """No seeded agent -> the loop stops BEFORE conducting anything: a
    stood-down steerer must not burn LLM calls whose spend has no
    Decision to land on."""
    kernel = _kernel()  # ExperimentSteerer NOT seeded
    p0, p1 = uuid4(), uuid4()
    results = {p0: _ok_result(p0, 1030.0), p1: _ok_result(p1, 1029.0)}

    steps, conduct, hold = await _steer(kernel, procedure_ids=[p0, p1], results=results)

    assert steps == []
    assert conduct.calls == []
    assert hold.calls == []
    # Nothing was written.
    events, _ = await kernel.event_store.load("Decision", _derive_decision_id(p0, 0))
    assert events == []


def _sonnet_call(input_tokens: int = 1000, output_tokens: int = 100) -> SteeringLlmCall:
    return SteeringLlmCall(
        provider="anthropic",
        request_model="claude-sonnet-4-5",
        response_model="claude-sonnet-4-5-20250929",
        usage=LLMUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


@pytest.mark.unit
async def test_steer_posts_llm_usage_to_the_inference_ledger() -> None:
    """Each steered procedure's LLM calls land on its across-procedure
    Decision as inference rows: deterministic event ids, steerer
    attribution, and a real cost from the pricing table, so the spend
    ledger sees steering spend."""
    kernel = _kernel()
    recorder = FakeInferenceRecorder()
    object.__setattr__(kernel, "inference_recorder", recorder)
    await seed_experiment_steerer_agent(kernel)
    p0 = uuid4()
    result = dc_replace(_ok_result(p0, _TARGET), llm_calls=(_sonnet_call(), _sonnet_call(2000, 50)))
    steps, _conduct, _hold = await _steer(kernel, procedure_ids=[p0], results={p0: result})

    assert steps[0].choice == "Conclude"
    decision_id = steps[0].decision_id
    assert decision_id is not None
    assert len(recorder.calls) == 2
    first = recorder.calls[0]
    assert first.trace.decision_id == decision_id
    assert first.trace.event_id == uuid5(decision_id, "inference:0")
    assert recorder.calls[1].trace.event_id == uuid5(decision_id, "inference:1")
    assert first.trace.agent_id == str(EXPERIMENT_STEERER_AGENT_ID)
    assert first.principal_id == EXPERIMENT_STEERER_AGENT_ID
    assert first.trace.provider_name == "anthropic"
    assert first.trace.request_model == "claude-sonnet-4-5"
    assert first.trace.response_model == "claude-sonnet-4-5-20250929"
    # Sonnet pricing: $3/M input + $15/M output.
    assert first.trace.cost_usd == pytest.approx(1000 / 1e6 * 3 + 100 / 1e6 * 15)


@pytest.mark.unit
async def test_steer_stood_down_records_no_usage() -> None:
    """An unseeded agent conducts nothing, posts nothing: the stand-down
    now happens before any spend, so there is no unledgered burn."""
    kernel = _kernel()
    recorder = FakeInferenceRecorder()
    object.__setattr__(kernel, "inference_recorder", recorder)
    p0 = uuid4()
    result = dc_replace(_ok_result(p0, 1030.0), llm_calls=(_sonnet_call(),))

    steps, conduct, _hold = await _steer(kernel, procedure_ids=[p0], results={p0: result})

    assert steps == []
    assert conduct.calls == []
    assert recorder.calls == []


@pytest.mark.unit
async def test_steer_stamps_the_steerer_agent_id_onto_the_decide_config() -> None:
    """The driver stamps its agent onto the brain config so the
    pre-estimate gate has someone to charge; route callers cannot set
    this (the field is not on the wire models)."""
    kernel = _kernel()
    await seed_experiment_steerer_agent(kernel)
    p0 = uuid4()

    _steps, conduct, _hold = await _steer(
        kernel, procedure_ids=[p0], results={p0: _ok_result(p0, _TARGET)}
    )

    assert conduct.calls[0].decide.spend_agent_id == EXPERIMENT_STEERER_AGENT_ID


@pytest.mark.unit
async def test_steer_posts_each_turns_usage_onto_that_turns_own_decision() -> None:
    """Two steered procedures, one call each: the inference rows land on
    their own turn's Decision (a bug posting everything against the
    first or last Decision would cross-charge turns)."""
    kernel = _kernel()
    recorder = FakeInferenceRecorder()
    object.__setattr__(kernel, "inference_recorder", recorder)
    await seed_experiment_steerer_agent(kernel)
    p0, p1 = uuid4(), uuid4()
    results = {
        p0: dc_replace(_ok_result(p0, 1030.0), llm_calls=(_sonnet_call(),)),
        p1: dc_replace(_ok_result(p1, _TARGET), llm_calls=(_sonnet_call(2000, 50),)),
    }

    steps, _conduct, _hold = await _steer(kernel, procedure_ids=[p0, p1], results=results)

    assert [s.choice for s in steps] == ["Continue", "Conclude"]
    assert len(recorder.calls) == 2
    for step, recorded in zip(steps, recorder.calls, strict=True):
        assert step.decision_id is not None
        assert recorded.trace.decision_id == step.decision_id
        assert recorded.trace.event_id == uuid5(step.decision_id, "inference:0")


@pytest.mark.unit
def test_spend_agent_id_is_absent_from_the_conduct_wire_model() -> None:
    """The attribution boundary: route and MCP callers must not be able
    to charge an agent. DecideConfigRequest forbids extras, so absence
    from model_fields means a 422 for any caller who tries."""
    from cora.operation._advise_wire import DecideConfigRequest

    assert "spend_agent_id" not in DecideConfigRequest.model_fields
    assert DecideConfigRequest.model_config.get("extra") == "forbid"
