"""Unit tests for the DecidePort seam: VO self-validation, the audit mapper,
the in-memory fake, and the factory.

S1 ships the port surface with no conductor or wiring, so these tests pin the
contract in isolation: `SteeringAdvice` rejects malformed brain answers at
construction, `advice_to_audit_fields` projects the provenance subset, and
`InMemoryDecidePort` (built via `build_decide_port`) replays seeded advice by
iteration then advises Stop.
"""

import math

import pytest

from cora.operation.adapters.decide_port_config import DecidePortConfig, build_decide_port
from cora.operation.adapters.in_memory_decide_port import InMemoryDecidePort
from cora.operation.ports.decide_port import (
    AdviceAuditFields,
    DecideAdviceMalformedError,
    DecidePort,
    SteeringAdvice,
    SteeringAxis,
    SteeringEvidence,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringPoint,
    SteeringSpace,
    SteeringVerdict,
    advice_to_audit_fields,
)
from cora.shared.decision_signals import REASONING_MAX_LENGTH, DecisionConfidenceSource


def _objective() -> SteeringObjective:
    return SteeringObjective(kind=SteeringObjectiveKind.MAXIMIZE, target_measurement_name="flux")


def _space() -> SteeringSpace:
    return SteeringSpace(axes=(SteeringAxis(name="energy", lower=8.0, upper=12.0),))


def _evidence(iteration_index: int) -> SteeringEvidence:
    return SteeringEvidence(objective=_objective(), space=_space(), iteration_index=iteration_index)


def test_steering_advice_measure_without_next_point_is_rejected() -> None:
    with pytest.raises(DecideAdviceMalformedError):
        SteeringAdvice(verdict=SteeringVerdict.MEASURE, next_point=None)


def test_steering_advice_stop_with_next_point_is_rejected() -> None:
    with pytest.raises(DecideAdviceMalformedError):
        SteeringAdvice(
            verdict=SteeringVerdict.STOP,
            next_point=SteeringPoint(coordinates={"energy": 9.0}),
        )


def test_steering_advice_confidence_out_of_range_is_rejected() -> None:
    with pytest.raises(DecideAdviceMalformedError):
        SteeringAdvice(
            verdict=SteeringVerdict.STOP,
            confidence=1.5,
        )


def test_steering_advice_confidence_nan_is_rejected() -> None:
    with pytest.raises(DecideAdviceMalformedError):
        SteeringAdvice(verdict=SteeringVerdict.STOP, confidence=math.nan)


def test_steering_advice_overlong_rationale_is_rejected() -> None:
    with pytest.raises(DecideAdviceMalformedError):
        SteeringAdvice(
            verdict=SteeringVerdict.STOP,
            rationale="x" * (REASONING_MAX_LENGTH + 1),
        )


def test_steering_advice_valid_measure_constructs() -> None:
    advice = SteeringAdvice(
        verdict=SteeringVerdict.MEASURE,
        next_point=SteeringPoint(coordinates={"energy": 9.5}),
        rationale="acquisition peak",
        confidence=0.8,
        confidence_source=DecisionConfidenceSource.SELF_REPORTED,
    )
    assert advice.next_point is not None
    assert advice.next_point.coordinates["energy"] == 9.5


def test_advice_to_audit_fields_projects_provenance_subset() -> None:
    advice = SteeringAdvice(
        verdict=SteeringVerdict.MEASURE,
        next_point=SteeringPoint(coordinates={"energy": 9.5}),
        rationale="acquisition peak",
        confidence=0.8,
        confidence_source=DecisionConfidenceSource.LOGPROB,
        alternatives=("energy=9.0", "energy=10.0"),
        model_ref="gridwalk:v1",
    )
    fields = advice_to_audit_fields(advice)
    assert fields == AdviceAuditFields(
        reasoning="acquisition peak",
        confidence=0.8,
        confidence_source=DecisionConfidenceSource.LOGPROB,
        alternatives=("energy=9.0", "energy=10.0"),
        model_ref="gridwalk:v1",
    )


async def test_in_memory_decide_port_replays_seeded_advice_by_iteration() -> None:
    port = InMemoryDecidePort()
    first = SteeringAdvice(
        verdict=SteeringVerdict.MEASURE,
        next_point=SteeringPoint(coordinates={"energy": 9.0}),
    )
    second = SteeringAdvice(
        verdict=SteeringVerdict.MEASURE,
        next_point=SteeringPoint(coordinates={"energy": 10.0}),
    )
    port.set_advice_sequence([first, second])

    assert await port.advise_next(_evidence(0)) is first
    assert await port.advise_next(_evidence(1)) is second


async def test_in_memory_decide_port_advises_stop_past_the_sequence() -> None:
    port = InMemoryDecidePort()
    port.set_advice_sequence(
        [
            SteeringAdvice(
                verdict=SteeringVerdict.MEASURE,
                next_point=SteeringPoint(coordinates={"energy": 9.0}),
            )
        ]
    )

    exhausted = await port.advise_next(_evidence(1))
    assert exhausted.verdict is SteeringVerdict.STOP
    assert exhausted.next_point is None


async def test_in_memory_decide_port_advises_stop_with_no_sequence() -> None:
    port = InMemoryDecidePort()
    advice = await port.advise_next(_evidence(0))
    assert advice.verdict is SteeringVerdict.STOP


async def test_in_memory_decide_port_aclose_is_noop() -> None:
    port = InMemoryDecidePort()
    assert await port.aclose() is None


def test_build_decide_port_default_returns_runtime_checkable_decide_port() -> None:
    port = build_decide_port()
    assert isinstance(port, DecidePort)
    assert isinstance(port, InMemoryDecidePort)


def test_build_decide_port_in_memory_config_returns_in_memory() -> None:
    port = build_decide_port(DecidePortConfig(substrate="in_memory"))
    assert isinstance(port, InMemoryDecidePort)


def test_steering_advice_confidence_at_inclusive_bounds_constructs() -> None:
    assert SteeringAdvice(verdict=SteeringVerdict.STOP, confidence=0.0).confidence == 0.0
    assert SteeringAdvice(verdict=SteeringVerdict.STOP, confidence=1.0).confidence == 1.0


def test_steering_advice_confidence_below_range_is_rejected() -> None:
    with pytest.raises(DecideAdviceMalformedError):
        SteeringAdvice(verdict=SteeringVerdict.STOP, confidence=-0.1)


async def test_in_memory_decide_port_replay_is_stateless_across_iterations() -> None:
    port = InMemoryDecidePort()
    first = SteeringAdvice(
        verdict=SteeringVerdict.MEASURE,
        next_point=SteeringPoint(coordinates={"energy": 9.0}),
    )
    second = SteeringAdvice(
        verdict=SteeringVerdict.MEASURE,
        next_point=SteeringPoint(coordinates={"energy": 10.0}),
    )
    port.set_advice_sequence([first, second])

    # A stateless brain returns the same advice for the same iteration
    # regardless of call order: drive forward, then replay an earlier turn.
    assert await port.advise_next(_evidence(1)) is second
    assert await port.advise_next(_evidence(0)) is first
    assert await port.advise_next(_evidence(1)) is second
