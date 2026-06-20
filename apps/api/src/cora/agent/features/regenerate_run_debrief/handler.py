"""Application handler for the `regenerate_run_debrief` slice.

Pattern C from the design memo: operator-triggered on-demand
RunDebriefer. The handler is the HTTP-side equivalent of the
subscriber: load Run, build payload (reusing the same prompt
module), call LLM, compose `DecisionRegistered` via the slice's
pure `decide()`, append.

## Differences from the subscriber

  - `principal_id` is the operator's UUID (from HTTP header), NOT
    the agent's. The agent is the WHO of the Decision (`actor_id`);
    the operator is the WHO of the COMMAND (`principal_id`).
  - `decision_id` is a fresh UUIDv7 from the kernel's `IdGenerator`
    (NOT UUID5-derived). Idempotency lives at the HTTP envelope
    via `Idempotency-Key` (Brandur), wrapped at wire.py.
  - `parent_id` is operator-supplied (optional), forming a PROV-O
    `wasInformedBy` chain to the prior auto-fired Debrief.
  - Authorize port IS called (HTTP-handler convention).

## Cross-aggregate validation

The handler pre-loads cross-aggregate refs and reports failures
via aggregate-state errors hoisted from this slice
(cross-BC gate-review):

  - Run aggregate must exist (`load_run` returns non-None);
    raises `cora.run.aggregates.run.state.RunNotFoundError` ->
    HTTP 404 (already-mapped by Run BC's routes).
  - RunDebriefer Agent's Actor must exist and be active; raises
    `AgentNotSeededError` / `AgentDeactivatedError` (both in
    `cora.agent.aggregates.agent.state`) -> HTTP 400.
  - When `parent_decision_id` is supplied: parent Decision must
    exist (`DecisionParentNotFoundError` from
    `cora.decision.aggregates.decision`; HTTP 409 per Decision
    BC's existing mapping), have `context == "RunDebrief"`
    (`DecisionParentAgentMismatchError`; HTTP 400), AND reference
    the same `run_id` in its `inputs`
    (`DecisionParentRunMismatchError`; HTTP 400).

The parent-context check (PR-author note: architecture gate-review)
catches accidental cross-agent chains where the
operator passes a Decision id authored by a different agent
context (eg. a `PolicyGrant` Decision).

## DebriefDeferred fallback

Same as the subscriber: when the LLM call exhausts, the handler
composes a `DecisionRegistered` with `choice="DebriefDeferred"`
via the same `decide()` and writes it. Operator can retry by
re-issuing the MCP call with a different Idempotency-Key (a same-
key retry replays the cached DebriefDeferred; the operator must
mint a fresh key to bypass the cache).
"""

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID, uuid5

from cora.access.aggregates.actor import load_actor
from cora.agent.aggregates.agent import AgentDeactivatedError, AgentNotSeededError
from cora.agent.errors import UnauthorizedError
from cora.agent.features.regenerate_run_debrief.command import RegenerateRunDebrief
from cora.agent.features.regenerate_run_debrief.context import RegenerateRunDebriefContext
from cora.agent.features.regenerate_run_debrief.decider import decide
from cora.agent.prompts import (
    RunDebriefPayload,
    build_run_debrief_chat_request,
)
from cora.agent.seed import RUN_DEBRIEFER_AGENT_ID, RUN_DEBRIEFER_AGENT_NAME
from cora.agent.subscribers.run_debriefer import redact_secrets
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_RUN_DEBRIEF,
    DECISION_REASONING_OPERATION_CHAT,
    DecisionParentAgentMismatchError,
    DecisionParentNotFoundError,
    DecisionParentRunMismatchError,
    event_type_name,
    load_decision,
    to_payload,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import (
    AgentInferenceTrace,
    Deny,
    InferenceRecorder,
    LLMChatRequest,
    LLMError,
    LLMResponse,
)
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import RunNotFoundError, load_run

_STREAM_TYPE = "Decision"
_COMMAND_NAME = "RegenerateRunDebrief"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare regenerate_run_debrief handler -- what `bind()` returns."""

    async def __call__(
        self,
        command: RegenerateRunDebrief,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """regenerate_run_debrief handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: RegenerateRunDebrief,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a regenerate_run_debrief handler closed over the shared deps."""
    if deps.llm is None:
        msg = (
            "regenerate_run_debrief handler requires kernel.llm to be set; "
            "configure ANTHROPIC_API_KEY or inject a FakeLLM."
        )
        raise RuntimeError(msg)
    llm = deps.llm

    async def handler(
        command: RegenerateRunDebrief,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        log = _log.bind(
            command_name=_COMMAND_NAME,
            run_id=str(command.run_id),
            parent_decision_id=(
                str(command.parent_decision_id) if command.parent_decision_id is not None else None
            ),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )
        log.info("regenerate_run_debrief.start")

        authz = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(authz, Deny):
            log.info("regenerate_run_debrief.denied", reason=authz.reason)
            raise UnauthorizedError(authz.reason)

        # Pre-load Run aggregate.
        run = await load_run(deps.event_store, command.run_id)
        if run is None:
            raise RunNotFoundError(command.run_id)

        # Pre-load RunDebriefer Agent's Actor and gate on active.
        actor = await load_actor(deps.event_store, RUN_DEBRIEFER_AGENT_ID)
        if actor is None:
            raise AgentNotSeededError(RUN_DEBRIEFER_AGENT_ID, RUN_DEBRIEFER_AGENT_NAME)
        if not actor.active:
            raise AgentDeactivatedError(RUN_DEBRIEFER_AGENT_ID)

        # Pre-load parent Decision when ref set; enforce same-agent +
        # same-Run scope.
        if command.parent_decision_id is not None:
            parent = await load_decision(deps.event_store, command.parent_decision_id)
            if parent is None:
                raise DecisionParentNotFoundError(command.parent_decision_id)
            parent_context = parent.context.value
            if parent_context != DECISION_CONTEXT_RUN_DEBRIEF:
                raise DecisionParentAgentMismatchError(
                    command.parent_decision_id,
                    parent_context,
                )
            parent_run_id = _extract_parent_run_id(parent.inputs)
            if parent_run_id != command.run_id:
                raise DecisionParentRunMismatchError(
                    command.parent_decision_id,
                    parent_run_id,
                )

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        payload = RunDebriefPayload(
            terminal_event_type="RegenerateRunDebrief:on-demand",
            terminal_event_reason=None,
            terminal_event_occurred_at=now.isoformat(),
            run_id=command.run_id,
            run_name=run.name.value,
            run_status=str(run.status),
            plan_id=run.plan_id,
            subject_id=run.subject_id,
            campaign_id=run.campaign_id,
            effective_parameters=run.effective_parameters,
            adjustment_count=run.adjustment_count,
            last_adjusted_at=(
                run.last_adjusted_at.isoformat() if run.last_adjusted_at is not None else None
            ),
            interrupted_at=None,
        )
        request = build_run_debrief_chat_request(payload)

        response: LLMResponse | None = None
        try:
            response = await llm.chat(request)
        except LLMError as exc:
            log.warning(
                "regenerate_run_debrief.llm_failed",
                error_class=type(exc).__name__,
                error_message=redact_secrets(str(exc)[:200]),
            )
            decider_context = RegenerateRunDebriefContext(
                actor=actor,
                choice="DebriefDeferred",
                confidence=None,
                reasoning=(
                    f"LLM call failed with {type(exc).__name__}; on-demand "
                    "debrief regeneration deferred. Operator may retry with a "
                    "fresh Idempotency-Key to bypass the cached failure."
                ),
                extra_inputs={"failure_error_class": type(exc).__name__},
            )
            outcome = "deferred"
        else:
            decider_context = RegenerateRunDebriefContext(
                actor=actor,
                choice=str(response.parsed["choice"]),
                confidence=(
                    float(response.parsed["confidence"])
                    if response.parsed["confidence"] is not None
                    else None
                ),
                reasoning=str(response.parsed["reasoning"]),
            )
            outcome = "success"

        domain_events = decide(
            state=None,
            command=command,
            context=decider_context,
            now=now,
            new_id=new_id,
        )
        # regenerate_run_debrief's decider always returns exactly one
        # DecisionRegistered; unpack to fail loud if a future maintainer
        # adds a second event.
        (domain_event,) = domain_events
        new_event = to_new_event(
            event_type=event_type_name(domain_event),
            payload=to_payload(domain_event),
            occurred_at=domain_event.occurred_at,
            # Derive event_id from decision_id so the (decision_id,
            # event_id) pair stays stable for downstream observability.
            event_id=uuid5(new_id, "event:0"),
            command_name=_COMMAND_NAME,
            correlation_id=correlation_id,
            causation_id=causation_id,
            principal_id=principal_id,
        )
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=new_id,
            expected_version=0,
            events=[new_event],
        )

        # Capture model provenance for the regenerated Decision, only when the
        # LLM actually ran (the DebriefDeferred path has no response). After
        # the append so the recorder's lazy logbook-open finds the Decision.
        if outcome == "success" and response is not None:
            await _record_inference(
                deps.inference_recorder,
                decision_id=new_id,
                request=request,
                response=response,
                occurred_at=now,
                principal_id=RUN_DEBRIEFER_AGENT_ID,
                correlation_id=correlation_id,
                causation_id=causation_id,
                log=log,
            )

        log.info("regenerate_run_debrief.success", outcome=outcome, decision_id=str(new_id))
        return new_id

    return handler


async def _record_inference(
    recorder: InferenceRecorder,
    *,
    decision_id: UUID,
    request: LLMChatRequest,
    response: LLMResponse,
    occurred_at: datetime,
    principal_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None,
    log: Any,
) -> None:
    """Best-effort capture of the on-demand LLM call's model provenance.

    Mirrors the subscriber path: fire-and-forget (the recorder never raises
    per its port contract; the try/except is defense-in-depth), deterministic
    inference `event_id`, recorded only after the Decision append commits.
    The inference is attributed to the RunDebriefer agent principal (the WHO of
    the Decision), so the operator-initiated regenerate carries the same authz
    requirement as the auto-fired subscriber path.
    """
    trace = AgentInferenceTrace(
        decision_id=decision_id,
        event_id=uuid5(decision_id, "inference:0"),
        occurred_at=occurred_at,
        operation_name=DECISION_REASONING_OPERATION_CHAT,
        provider_name=request.model_ref.provider,
        request_model=request.model_ref.model,
        response_model=response.model_id,
        finish_reasons=(response.stop_reason,) if response.stop_reason else (),
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        request_max_tokens=request.max_output_tokens,
        agent_id=str(RUN_DEBRIEFER_AGENT_ID),
        agent_name=RUN_DEBRIEFER_AGENT_NAME,
    )
    try:
        await recorder.record(
            trace,
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
    except Exception as exc:
        log.warning(
            "regenerate_run_debrief.inference_record_failed",
            error_class=type(exc).__name__,
            error_message=redact_secrets(str(exc)[:200]),
        )


def _extract_parent_run_id(inputs: dict[str, object] | None) -> UUID | None:
    """Pull `run_id` from the parent Decision's `inputs`.

    Both the subscriber + this handler put `run_id` in
    `inputs` for RunDebrief Decisions, so the same key is
    where the chain link lives. Returns None if absent (which is
    unusual for a RunDebrief Decision but defensive) or malformed.
    The handler treats a None return as a same-Run mismatch
    (parent-run-id != command-run-id), raising
    `DecisionParentRunMismatchError`.
    """
    if inputs is None:
        return None
    raw = inputs.get("run_id")
    if raw is None:
        return None
    try:
        return UUID(str(raw))
    except ValueError:
        return None
