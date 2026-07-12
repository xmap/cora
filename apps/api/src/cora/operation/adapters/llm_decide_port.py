"""LlmDecidePort: an LLM steering brain behind the `DecidePort` seam.

BUDGET NOTE: the steering brain is metered AND gated. Metered: with a
`usage_sink` wired (the conduct handlers wire one), every call's token
usage is surfaced on the conduct result, and the steer_experiment
driver posts it to the durable inference ledger against the
across-procedure Decision, so `SpendLookup` sees steering spend.
Gated: when built with a `SpendGuard`, a charged agent, and a clock
(the steer_experiment path), `_refuse_if_over_budget` runs the
per-call pre-estimate tier BEFORE each chat, raising
`DecideSpendRefusedError` on a would-be breach so no tokens are
bought; the conduct loop folds the refusal into a deferred steering
decision. Transport-failed calls (timeout, rate limit) reach no sink;
their tokens, if any were consumed server-side, are an accepted
undercount in the permissive direction the coarse tier documents.

The DECIDE-axis analogue of the LLM agents in the Agent BC, but homed in
the Operation BC because it implements `DecidePort` (which lives here) and
consumes only the `LLM` port and `cora.shared` steering value types, never
`cora.agent`. Given the full `SteeringEvidence`, it asks the LLM for one
structured advice (`Measure` a next point, or `Stop`) and maps the answer
onto a validated `SteeringAdvice`.

## Stateless by construction

Like every `DecidePort` brain, it holds no cross-call STEERING memory:
the full `SteeringEvidence.observations` is handed over each call and
serialised into the prompt, so a replay that re-drives an earlier turn
yields the same request. The one instance field that accumulates is
spend telemetry (the in-conduct actuals the budget gate projects with),
which never influences advice. The LLM's own non-determinism is captured at the seam per
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

from cora.infrastructure.observability.gen_ai import (
    compute_cost_usd,
    estimate_llm_call_ceiling,
)
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
    DecideSpendRefusedError,
    DecideTimeoutError,
    SteeringAdvice,
    SteeringEvidence,
    SteeringLlmCall,
    SteeringPoint,
    SteeringVerdict,
)
from cora.shared.decision_signals import DecisionConfidenceSource

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from uuid import UUID

    from cora.infrastructure.ports.clock import Clock
    from cora.infrastructure.ports.llm import LLM, LLMChatRequest, ModelRef
    from cora.infrastructure.ports.spend_guard import SpendGuard


class LlmDecidePort:
    """An LLM-backed, stateless steering brain implementing `DecidePort`.

    Satisfies the `DecidePort` Protocol structurally. Constructed with an
    `LLM` port and the `ModelRef` to steer with; the factory
    (`build_decide_port`, `llm` substrate) injects the kernel's LLM.
    """

    def __init__(
        self,
        *,
        llm: LLM,
        model_ref: ModelRef = DEFAULT_LLM_DECIDE_MODEL,
        usage_sink: Callable[[SteeringLlmCall], None] | None = None,
        spend_guard: SpendGuard | None = None,
        spend_agent_id: UUID | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._llm = llm
        self._model_ref = model_ref
        self._usage_sink = usage_sink
        self._spend_guard = spend_guard
        self._spend_agent_id = spend_agent_id
        self._clock = clock
        # In-conduct actuals: the ledger is only posted per turn (after the
        # conduct returns), so without this the whole loop would be judged
        # against one frozen baseline and a long conduct could stack many
        # small calls past a cap. Spend telemetry, not steering memory: the
        # brain stays stateless for replay purposes (a fresh instance is
        # built per conduct, and advice still depends only on the evidence).
        self._conduct_spent_usd = 0.0
        self._conduct_spent_tokens = 0

    async def advise_next(self, evidence: SteeringEvidence) -> SteeringAdvice:
        """Ask the LLM for the next steering action, or a stop.

        Serialises the full evidence, calls the LLM, and maps the parsed
        structured output onto a validated `SteeringAdvice`. Raises a
        `DecidePort` exception (never an `LLMError`) so the conduct loop
        folds any brain fault into a deferred decision.
        """
        payload = evidence_to_payload(evidence)
        request = build_llm_decide_chat_request(payload, model_ref=self._model_ref)
        await self._refuse_if_over_budget(request)
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

        self._conduct_spent_usd += compute_cost_usd(self._model_ref, response.usage)
        self._conduct_spent_tokens += (response.usage.input_tokens or 0) + (
            response.usage.output_tokens or 0
        )
        if self._usage_sink is not None:
            # Before parsing: a malformed answer still cost real tokens,
            # and the ledger records what was spent, not what was useful.
            self._usage_sink(
                SteeringLlmCall(
                    provider=self._model_ref.provider,
                    request_model=self._model_ref.model,
                    response_model=response.model_id,
                    usage=response.usage,
                )
            )
        return self._advice_from_parsed(response.parsed, evidence)

    async def _refuse_if_over_budget(self, request: LLMChatRequest) -> None:
        """The per-call pre-estimate gate: refuse BEFORE tokens are bought.

        Active only when the brain was built with a guard, an agent to
        charge, and a clock (the steer_experiment driver's path). The
        projection adds three parts: the ledger baseline (inside the
        guard), the actual cost of the calls THIS conduct already made
        (the ledger only hears about them after the turn posts), and a
        deliberate ceiling for the next call (see
        `estimate_llm_call_ceiling`), so a long conduct cannot stack many
        small calls past a cap against a frozen baseline. Residual
        overspend is one call's estimate error plus cross-conduct races,
        which the reserve tier owns. An unpriced model has no ceiling but
        the guard still runs with zero estimates, so the lifecycle stop
        and the already-over-cap refusal survive a missing PRICING entry.
        Raises `DecideSpendRefusedError`, which the conduct loop folds
        into a deferred steering decision.
        """
        if self._spend_guard is None or self._spend_agent_id is None or self._clock is None:
            return
        # The structured-output schema is billed input too; string length is
        # a fair stand-in for its serialized size.
        input_chars = (
            len(request.user_message.text)
            + sum(len(block.text) for block in request.system.blocks)
            + len(str(request.structured_output_schema))
        )
        ceiling = estimate_llm_call_ceiling(
            self._model_ref,
            input_chars=input_chars,
            max_output_tokens=request.max_output_tokens,
        )
        # An unpriced model has no cost ceiling, but the guard still runs
        # with zero estimates: the lifecycle stop (a suspended agent) and
        # the already-over-cap refusal must not depend on pricing coverage.
        estimated_cost = ceiling.cost_usd if ceiling is not None else 0.0
        estimated_tokens = ceiling.tokens if ceiling is not None else 0
        reason = await self._spend_guard.refusal_reason(
            agent_id=self._spend_agent_id,
            estimated_cost_usd=estimated_cost + self._conduct_spent_usd,
            estimated_tokens=estimated_tokens + self._conduct_spent_tokens,
            as_of=self._clock.now(),
        )
        if reason is not None:
            raise DecideSpendRefusedError(reason)

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
