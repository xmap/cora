"""Unit tests for LlmDecidePort: the LLM steering brain behind DecidePort.

These pin the happy paths (Measure with a valid point; Stop), the
error-translation table (each `LLMError` -> the matching `Decide*Error`
the conduct loop folds), the answer-validation guards (unknown verdict,
Measure without a point, a point over an unknown axis), the provenance
fields (model_ref + self-reported confidence source), and the factory
wiring (`build_decide_port(substrate="llm")` needs an injected llm and
returns an LlmDecidePort). The LLM is a `FakeLLM` returning canned
parsed dicts, so no network traffic.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from cora.infrastructure.ports.llm import (
    FakeLLM,
    FakeLLMResponse,
    LLMAuthenticationError,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMSchemaValidationError,
    LLMServerError,
    LLMTimeoutError,
)
from cora.operation.adapters.decide_port_config import (
    DecidePortConfig,
    build_decide_port,
)
from cora.operation.adapters.llm_decide_port import LlmDecidePort
from cora.operation.ports.decide_port import (
    DecideAdviceMalformedError,
    DecideNotAvailableError,
    DecidePort,
    DecideTimeoutError,
    SteeringAxis,
    SteeringEvidence,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringObservation,
    SteeringPoint,
    SteeringSpace,
    SteeringVerdict,
)
from cora.operation.ports.measurement import Measurement, Quality
from cora.shared.decision_signals import DecisionConfidenceSource

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _space() -> SteeringSpace:
    return SteeringSpace(axes=(SteeringAxis(name="x", lower=0.0, upper=10.0),))


def _maximize(target: str = "flux") -> SteeringObjective:
    return SteeringObjective(kind=SteeringObjectiveKind.MAXIMIZE, target_measurement_name=target)


def _obs(
    x: float,
    flux: float | None,
    *,
    succeeded: bool = True,
    quality: Quality = "Good",
    name: str = "flux",
) -> SteeringObservation:
    measurements: tuple[Measurement, ...] = ()
    if flux is not None:
        measurements = (
            Measurement(value=flux, kind="Scalar", quality=quality, produced_at=_T0, name=name),
        )
    return SteeringObservation(
        point=SteeringPoint(coordinates={"x": x}),
        measurements=measurements,
        succeeded=succeeded,
    )


def _evidence(*observations: SteeringObservation) -> SteeringEvidence:
    return SteeringEvidence(
        objective=_maximize(),
        space=_space(),
        observations=tuple(observations),
        iteration_index=len(observations),
    )


def _response(parsed: dict[str, Any]) -> FakeLLMResponse:
    return FakeLLMResponse(parsed=parsed)


async def test_advise_next_measure_returns_valid_point() -> None:
    llm = FakeLLM(
        [
            _response(
                {
                    "verdict": "Measure",
                    "next_point": {"x": 4.2},
                    "confidence": 0.7,
                    "rationale": "flux is rising toward the upper half of the range",
                }
            )
        ]
    )
    port = LlmDecidePort(llm=llm)

    advice = await port.advise_next(_evidence(_obs(1.0, 10.0), _obs(2.0, 20.0)))

    assert advice.verdict is SteeringVerdict.MEASURE
    assert advice.next_point is not None
    assert advice.next_point.coordinates == {"x": 4.2}
    assert advice.confidence == 0.7
    assert advice.confidence_source is DecisionConfidenceSource.SELF_REPORTED
    assert advice.model_ref == "anthropic:claude-sonnet-4-5"


async def test_advise_next_stop_carries_no_point() -> None:
    llm = FakeLLM(
        [
            _response(
                {
                    "verdict": "Stop",
                    "confidence": 0.9,
                    "rationale": "objective plateaued; budget nearly spent",
                }
            )
        ]
    )
    port = LlmDecidePort(llm=llm)

    advice = await port.advise_next(_evidence(_obs(1.0, 10.0)))

    assert advice.verdict is SteeringVerdict.STOP
    assert advice.next_point is None


async def test_advise_next_serialises_full_evidence_to_the_llm() -> None:
    llm = FakeLLM([_response({"verdict": "Stop", "confidence": 0.5, "rationale": "done"})])
    port = LlmDecidePort(llm=llm)

    await port.advise_next(_evidence(_obs(1.0, 10.0), _obs(2.0, 20.0)))

    assert len(llm.received) == 1
    request = llm.received[0]
    # The observations travel in the user message (data), never the system prompt.
    assert "observations" in request.user_message.text
    assert "20.0" in request.user_message.text or "20" in request.user_message.text
    assert request.model_ref.model == "claude-sonnet-4-5"


@pytest.mark.parametrize(
    ("llm_error", "expected"),
    [
        (LLMTimeoutError("slow"), DecideTimeoutError),
        (LLMRateLimitError("429"), DecideNotAvailableError),
        (LLMServerError("500"), DecideNotAvailableError),
        (LLMAuthenticationError("401"), DecideNotAvailableError),
        (LLMInvalidRequestError("400"), DecideNotAvailableError),
        (LLMSchemaValidationError("bad shape"), DecideAdviceMalformedError),
    ],
)
async def test_llm_errors_translate_to_decide_taxonomy(
    llm_error: Exception, expected: type[Exception]
) -> None:
    llm = FakeLLM([llm_error])  # type: ignore[list-item]
    port = LlmDecidePort(llm=llm)

    with pytest.raises(expected):
        await port.advise_next(_evidence(_obs(1.0, 10.0)))


async def test_unknown_verdict_is_malformed() -> None:
    llm = FakeLLM([_response({"verdict": "Ponder", "confidence": 0.5, "rationale": "hmm"})])
    port = LlmDecidePort(llm=llm)

    with pytest.raises(DecideAdviceMalformedError):
        await port.advise_next(_evidence(_obs(1.0, 10.0)))


async def test_measure_without_point_is_malformed() -> None:
    llm = FakeLLM([_response({"verdict": "Measure", "confidence": 0.5, "rationale": "go"})])
    port = LlmDecidePort(llm=llm)

    with pytest.raises(DecideAdviceMalformedError):
        await port.advise_next(_evidence(_obs(1.0, 10.0)))


async def test_point_over_unknown_axis_is_malformed() -> None:
    llm = FakeLLM(
        [
            _response(
                {
                    "verdict": "Measure",
                    "next_point": {"y": 3.0},  # 'y' is not a declared axis
                    "confidence": 0.6,
                    "rationale": "hallucinated axis",
                }
            )
        ]
    )
    port = LlmDecidePort(llm=llm)

    with pytest.raises(DecideAdviceMalformedError):
        await port.advise_next(_evidence(_obs(1.0, 10.0)))


async def test_aclose_is_noop() -> None:
    port = LlmDecidePort(llm=FakeLLM([]))
    assert await port.aclose() is None


def test_factory_llm_substrate_builds_llm_decide_port() -> None:
    port = build_decide_port(DecidePortConfig(substrate="llm"), llm=FakeLLM([]))
    assert isinstance(port, LlmDecidePort)
    assert isinstance(port, DecidePort)


def test_factory_llm_substrate_requires_llm() -> None:
    with pytest.raises(ValueError, match="requires an llm port"):
        build_decide_port(DecidePortConfig(substrate="llm"))
