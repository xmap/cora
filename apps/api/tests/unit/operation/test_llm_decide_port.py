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
from uuid import UUID

import pytest

from cora.infrastructure.ports import FakeClock
from cora.infrastructure.ports.llm import (
    FakeLLM,
    FakeLLMResponse,
    LLMAuthenticationError,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMSchemaValidationError,
    LLMServerError,
    LLMTimeoutError,
    LLMUsage,
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
    DecideSpendRefusedError,
    DecideTimeoutError,
    SteeringAxis,
    SteeringEvidence,
    SteeringLlmCall,
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


@pytest.mark.unit
async def test_advise_next_reports_usage_to_the_sink() -> None:
    llm = FakeLLM(
        [
            FakeLLMResponse(
                parsed={"verdict": "Stop", "confidence": 0.5, "rationale": "done"},
                usage=LLMUsage(input_tokens=1200, output_tokens=80),
                model_id="claude-sonnet-4-5-20250929",
            )
        ]
    )
    calls: list[SteeringLlmCall] = []
    port = LlmDecidePort(llm=llm, usage_sink=calls.append)

    await port.advise_next(_evidence(_obs(1.0, 10.0)))

    assert len(calls) == 1
    call = calls[0]
    assert call.provider == "anthropic"
    assert call.request_model == "claude-sonnet-4-5"
    assert call.response_model == "claude-sonnet-4-5-20250929"
    assert call.usage.input_tokens == 1200
    assert call.usage.output_tokens == 80


@pytest.mark.unit
async def test_malformed_advice_still_reports_usage() -> None:
    """A hallucinated verdict still cost real tokens; the sink hears about
    the call before parsing so the ledger records what was spent."""
    llm = FakeLLM(
        [
            FakeLLMResponse(
                parsed={"verdict": "Ponder", "confidence": 0.5, "rationale": "hmm"},
                usage=LLMUsage(input_tokens=500, output_tokens=20),
            )
        ]
    )
    calls: list[SteeringLlmCall] = []
    port = LlmDecidePort(llm=llm, usage_sink=calls.append)

    with pytest.raises(DecideAdviceMalformedError):
        await port.advise_next(_evidence(_obs(1.0, 10.0)))

    assert len(calls) == 1
    assert calls[0].usage.input_tokens == 500


@pytest.mark.unit
async def test_transport_error_reports_no_usage() -> None:
    """A call that never returned has no provider-reported usage; the sink
    stays silent (the documented permissive undercount)."""
    llm = FakeLLM([LLMServerError("boom")])  # type: ignore[list-item]
    calls: list[SteeringLlmCall] = []
    port = LlmDecidePort(llm=llm, usage_sink=calls.append)

    with pytest.raises(DecideNotAvailableError):
        await port.advise_next(_evidence(_obs(1.0, 10.0)))

    assert calls == []


@pytest.mark.unit
async def test_build_decide_port_threads_usage_sink_to_the_llm_arm() -> None:
    llm = FakeLLM([FakeLLMResponse(parsed={"verdict": "Stop", "rationale": "ok"})])
    calls: list[SteeringLlmCall] = []
    port = build_decide_port(DecidePortConfig(substrate="llm"), llm=llm, usage_sink=calls.append)

    await port.advise_next(_evidence(_obs(1.0, 10.0)))

    assert len(calls) == 1


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


class _SpyGuard:
    """SpendGuard spy: records the ask, answers with a canned reason."""

    def __init__(self, reason: str | None) -> None:
        self._reason = reason
        self.asks: list[dict[str, object]] = []

    async def refusal_reason(
        self,
        *,
        agent_id: UUID,
        estimated_cost_usd: float,
        estimated_tokens: int,
        as_of: datetime,
    ) -> str | None:
        self.asks.append(
            {
                "agent_id": agent_id,
                "estimated_cost_usd": estimated_cost_usd,
                "estimated_tokens": estimated_tokens,
                "as_of": as_of,
            }
        )
        return self._reason


_GATE_NOW = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)
_GATE_AGENT_ID = UUID("01900000-0000-7000-8000-0000aaaa0077")


@pytest.mark.unit
async def test_refusing_guard_stops_the_call_before_any_tokens() -> None:
    llm = FakeLLM([_response({"verdict": "Stop", "rationale": "never reached"})])
    calls: list[SteeringLlmCall] = []
    guard = _SpyGuard("monthly_usd_cap of 100 would be breached")
    port = LlmDecidePort(
        llm=llm,
        usage_sink=calls.append,
        spend_guard=guard,
        spend_agent_id=_GATE_AGENT_ID,
        clock=FakeClock(_GATE_NOW),
    )

    with pytest.raises(DecideSpendRefusedError):
        await port.advise_next(_evidence(_obs(1.0, 10.0)))

    assert llm.received == []
    assert calls == []
    assert len(guard.asks) == 1


@pytest.mark.unit
async def test_granting_guard_sees_a_positive_ceiling_then_the_call_proceeds() -> None:
    llm = FakeLLM([_response({"verdict": "Stop", "rationale": "done"})])
    guard = _SpyGuard(None)
    port = LlmDecidePort(
        llm=llm,
        spend_guard=guard,
        spend_agent_id=_GATE_AGENT_ID,
        clock=FakeClock(_GATE_NOW),
    )

    advice = await port.advise_next(_evidence(_obs(1.0, 10.0)))

    assert advice.verdict is SteeringVerdict.STOP
    assert len(llm.received) == 1
    ask = guard.asks[0]
    assert ask["agent_id"] == _GATE_AGENT_ID
    assert ask["as_of"] == _GATE_NOW
    assert isinstance(ask["estimated_cost_usd"], float)
    assert ask["estimated_cost_usd"] > 0
    assert isinstance(ask["estimated_tokens"], int)
    assert ask["estimated_tokens"] > 0


@pytest.mark.unit
async def test_guard_without_a_charged_agent_is_not_consulted() -> None:
    """Route-driven conduct has no spend_agent_id; the guard stays silent
    and the call is operator-accountable, mirroring regenerate."""
    llm = FakeLLM([_response({"verdict": "Stop", "rationale": "done"})])
    guard = _SpyGuard("would refuse if asked")
    port = LlmDecidePort(
        llm=llm,
        spend_guard=guard,
        spend_agent_id=None,
        clock=FakeClock(_GATE_NOW),
    )

    await port.advise_next(_evidence(_obs(1.0, 10.0)))

    assert guard.asks == []
    assert len(llm.received) == 1


@pytest.mark.unit
async def test_build_decide_port_threads_the_gate_trio_to_the_llm_arm() -> None:
    """Mutation catcher: dropping spend_guard / spend_agent_id / clock from
    the factory's llm arm silently disarms production gating while every
    direct-construction test stays green."""
    llm = FakeLLM([_response({"verdict": "Stop", "rationale": "never reached"})])
    guard = _SpyGuard("cap would be breached")
    port = build_decide_port(
        DecidePortConfig(substrate="llm", spend_agent_id=_GATE_AGENT_ID),
        llm=llm,
        spend_guard=guard,
        clock=FakeClock(_GATE_NOW),
    )

    with pytest.raises(DecideSpendRefusedError):
        await port.advise_next(_evidence(_obs(1.0, 10.0)))

    assert llm.received == []


@pytest.mark.unit
async def test_second_ask_projects_the_first_calls_actual_spend() -> None:
    """The ledger only hears about a conduct's calls after the turn posts,
    so the brain adds its own in-conduct actuals to each projection; a
    long conduct cannot stack calls against a frozen baseline."""
    llm = FakeLLM(
        [
            FakeLLMResponse(
                parsed={"verdict": "Measure", "next_point": {"x": 1.0}, "rationale": "go"},
                usage=LLMUsage(input_tokens=1_000_000, output_tokens=0),
            ),
            FakeLLMResponse(
                parsed={"verdict": "Stop", "rationale": "done"},
                usage=LLMUsage(input_tokens=0, output_tokens=0),
            ),
        ]
    )
    guard = _SpyGuard(None)
    port = LlmDecidePort(
        llm=llm,
        spend_guard=guard,
        spend_agent_id=_GATE_AGENT_ID,
        clock=FakeClock(_GATE_NOW),
    )

    await port.advise_next(_evidence(_obs(1.0, 10.0)))
    await port.advise_next(_evidence(_obs(1.0, 10.0)))

    first, second = guard.asks
    # Sonnet base input is $3/M: one million input tokens adds ~$3 of
    # recorded-but-unposted spend to the second projection.
    assert second["estimated_cost_usd"] >= first["estimated_cost_usd"] + 2.9  # type: ignore[operator]
    assert second["estimated_tokens"] >= first["estimated_tokens"] + 1_000_000  # type: ignore[operator]
