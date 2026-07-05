"""LlmDecidePort: an LLM steering brain behind the `DecidePort` seam.

The DECIDE-axis analogue of the LLM agents in the Agent BC, but homed in
the Operation BC because it implements `DecidePort` (which lives here) and
consumes only the `LLM` port and `cora.shared` steering value types, never
`cora.agent`. Given the full `SteeringEvidence`, it asks the LLM for one
structured advice (`Measure` a next point, or `Stop`) and maps the answer
onto a validated `SteeringAdvice`.

## Stateless by construction

Like every `DecidePort` brain, it holds no cross-call memory: the full
`SteeringEvidence.observations` is handed over each call and serialised
into the prompt, so a replay that re-drives an earlier turn yields the same
request. The LLM's own non-determinism is captured at the seam per
[[project_non_determinism_principle]]: the caller records the returned
advice onto its event stream, so a replay never re-asks the model.

## Error translation

The adapter catches the `LLMError` family and re-raises the `DecidePort`
taxonomy the conduct loop already folds into a deferred steering decision
(never crashing the loop):

  - `LLMTimeoutError`         -> `DecideTimeoutError`
  - `LLMRateLimitError`,      -> `DecideNotAvailableError`
    `LLMServerError`,
    `LLMAuthenticationError`,
    `LLMInvalidRequestError`
  - `LLMSchemaValidationError`-> `DecideAdviceMalformedError`

## Answer validation

`SteeringAdvice.__post_init__` already rejects a malformed verdict/point
pairing and an out-of-range confidence. The adapter adds one guard the
port cannot: every axis name the LLM proposes in `next_point` must be a
real axis in the supplied `SteeringSpace` (mirrors CautionDrafter's
hallucinated-target defence). An unknown axis raises
`DecideAdviceMalformedError`. Coordinate-range validation (a value inside
an axis bound / among its choices) is left to the caller's point-to-step
translation, exactly as the other brains leave it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from cora.infrastructure.ports.llm import (
    LLMAuthenticationError,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMSchemaValidationError,
    LLMServerError,
    LLMTimeoutError,
)
from cora.operation.adapters._llm_decide_prompt import (
    DEFAULT_LLM_DECIDE_MODEL,
    build_llm_decide_chat_request,
    evidence_to_payload,
)
from cora.operation.ports.decide_port import (
    DecideAdviceMalformedError,
    DecideNotAvailableError,
    DecideTimeoutError,
    SteeringAdvice,
    SteeringEvidence,
    SteeringPoint,
    SteeringVerdict,
)
from cora.shared.decision_signals import DecisionConfidenceSource

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cora.infrastructure.ports.llm import LLM, ModelRef


class LlmDecidePort:
    """An LLM-backed, stateless steering brain implementing `DecidePort`.

    Satisfies the `DecidePort` Protocol structurally. Constructed with an
    `LLM` port and the `ModelRef` to steer with; the factory
    (`build_decide_port`, `llm` substrate) injects the kernel's LLM.
    """

    def __init__(self, *, llm: LLM, model_ref: ModelRef = DEFAULT_LLM_DECIDE_MODEL) -> None:
        self._llm = llm
        self._model_ref = model_ref

    async def advise_next(self, evidence: SteeringEvidence) -> SteeringAdvice:
        """Ask the LLM for the next steering action, or a stop.

        Serialises the full evidence, calls the LLM, and maps the parsed
        structured output onto a validated `SteeringAdvice`. Raises a
        `DecidePort` exception (never an `LLMError`) so the conduct loop
        folds any brain fault into a deferred decision.
        """
        payload = evidence_to_payload(evidence)
        request = build_llm_decide_chat_request(payload, model_ref=self._model_ref)
        try:
            response = await self._llm.chat(request)
        except LLMTimeoutError as exc:
            raise DecideTimeoutError(request.max_output_tokens) from exc
        except LLMSchemaValidationError as exc:
            raise DecideAdviceMalformedError(f"LLM structured output invalid: {exc}") from exc
        except (
            LLMRateLimitError,
            LLMServerError,
            LLMAuthenticationError,
            LLMInvalidRequestError,
        ) as exc:
            raise DecideNotAvailableError(f"LLM call failed: {type(exc).__name__}") from exc

        return self._advice_from_parsed(response.parsed, evidence)

    def _advice_from_parsed(
        self, parsed: Mapping[str, Any], evidence: SteeringEvidence
    ) -> SteeringAdvice:
        """Map the parsed LLM output onto a validated `SteeringAdvice`.

        The schema forces the shape, but a hallucinating model can still
        emit an unknown verdict, a point over an axis the space does not
        declare, or a Measure with no point. The unknown-axis guard is
        adapter-specific; the verdict/point pairing and confidence range
        are enforced by `SteeringAdvice.__post_init__`, whose
        `DecideAdviceMalformedError` propagates unchanged.
        """
        raw_verdict = str(parsed.get("verdict", ""))
        try:
            verdict = SteeringVerdict(raw_verdict)
        except ValueError as exc:
            raise DecideAdviceMalformedError(f"unknown verdict {raw_verdict!r}") from exc

        next_point: SteeringPoint | None = None
        if verdict is SteeringVerdict.MEASURE:
            raw_point = parsed.get("next_point")
            if not isinstance(raw_point, dict):
                raise DecideAdviceMalformedError("Measure verdict requires a next_point object")
            point_map = cast("dict[str, Any]", raw_point)
            coordinates: dict[str, Any] = {str(k): v for k, v in point_map.items()}
            known_axes = {axis.name for axis in evidence.space.axes}
            unknown = sorted(name for name in coordinates if name not in known_axes)
            if unknown:
                raise DecideAdviceMalformedError(
                    f"next_point names axes not in the space: {unknown}"
                )
            next_point = SteeringPoint(coordinates=coordinates)

        confidence = parsed.get("confidence")
        rationale = parsed.get("rationale")
        return SteeringAdvice(
            verdict=verdict,
            next_point=next_point,
            rationale=str(rationale) if rationale is not None else None,
            confidence=float(confidence) if confidence is not None else None,
            confidence_source=DecisionConfidenceSource.SELF_REPORTED,
            model_ref=f"{self._model_ref.provider}:{self._model_ref.model}",
        )

    async def aclose(self) -> None:
        """No-op: the adapter holds no resources of its own.

        The injected `LLM` port owns its client lifecycle; the adapter
        does not close it (the kernel that created the LLM does).
        """
        return None


__all__ = ["LlmDecidePort"]
