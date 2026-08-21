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
    `cora.agent.aggregates.agent.state`) -> HTTP 400. A Suspended
    agent raises `AgentSuspendedError` (resume first); the budget
    gate is deliberately NOT applied on this operator-triggered
    path (conscious, human-accountable spend; still debited).
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

import time
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID, uuid5

from cora.access.aggregates.actor import load_actor
from cora.agent._model_ref import to_port_model_ref
from cora.agent.aggregates.agent import (
    AgentDeactivatedError,
    AgentKindMismatchError,
    AgentNotFoundError,
    AgentNotSeededError,
    AgentNotVersionedError,
    AgentStatus,
    AgentSuspendedError,
    load_agent,
)
from cora.agent.errors import UnauthorizedError
from cora.agent.features.regenerate_run_debrief.command import RegenerateRunDebrief
from cora.agent.features.regenerate_run_debrief.context import RegenerateRunDebriefContext
from cora.agent.features.regenerate_run_debrief.decider import decide
from cora.agent.prompts import (
    RunDebriefPayload,
    build_run_debrief_chat_request,
)
from cora.agent.prompts.run_debrief import DEFAULT_RUN_DEBRIEF_MODEL
from cora.agent.seed import (
    RUN_DEBRIEFER_AGENT_ID,
    RUN_DEBRIEFER_AGENT_KIND,
    RUN_DEBRIEFER_AGENT_NAME,
)
from cora.agent.subscribers._terminal_run_helpers import (
    extract_capture_progress,
    extract_interrupted_at,
    extract_reason,
    find_terminal_run_event,
)
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
from cora.infrastructure.observability.gen_ai import compute_cost_usd
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

# Stands in for a terminal event type when the Run has none. Reads as
# what it is: the only thing that happened was an operator asking.
_ON_DEMAND_NO_TERMINAL = "RegenerateRunDebrief:on-demand"

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
        # Which RunDebriefer performs this. Defaults to the seeded
        # singleton, so every existing caller is unaffected.
        debriefer_agent_id = command.agent_id or RUN_DEBRIEFER_AGENT_ID

        log = _log.bind(
            command_name=_COMMAND_NAME,
            run_id=str(command.run_id),
            debriefer_agent_id=str(debriefer_agent_id),
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
        actor = await load_actor(deps.event_store, debriefer_agent_id)
        if actor is None:
            # Two different failures wear the same shape here. The seeded
            # singleton being absent IS a deployment fault, and its message
            # sends the operator to the bootstrap seed. An operator-named
            # agent being absent is a bad id in the request, and the same
            # message would send them to a config file to look for a typo
            # they made in a URL.
            if command.agent_id is not None:
                raise AgentNotFoundError(debriefer_agent_id)
            raise AgentNotSeededError(debriefer_agent_id, RUN_DEBRIEFER_AGENT_NAME)
        if not actor.active:
            raise AgentDeactivatedError(debriefer_agent_id)

        agent = await load_agent(deps.event_store, debriefer_agent_id)

        # Identity before authorization. An operator-named agent has to
        # exist as an Agent, not merely as an Actor, and has to be a
        # RunDebriefer. The seeded default is exempt from the existence
        # half because the apply path already tolerates an Actor-only
        # deployment; an explicitly named one is a deliberate choice and
        # gets checked. This runs FIRST so that naming the wrong agent
        # says so, rather than telling the operator to promote an agent
        # that would still be the wrong one afterwards.
        if command.agent_id is not None:
            if agent is None:
                raise AgentNotFoundError(debriefer_agent_id)
            if agent.kind.value != RUN_DEBRIEFER_AGENT_KIND:
                raise AgentKindMismatchError(
                    debriefer_agent_id,
                    RUN_DEBRIEFER_AGENT_KIND,
                    agent.kind.value,
                )

        # Lifecycle gate, matching the subscribers': only a Versioned
        # agent acts. Suspension is split out because its remedy is
        # resume_agent while the rest is version_agent, and a missing
        # Agent stream stays permissive exactly as it does there. The
        # BUDGET gate is deliberately absent here: an operator-triggered
        # regenerate is a conscious, human-accountable spend (the coarse
        # post-hoc tier targets the autonomous subscribers), and the call
        # still debits the ledger.
        if agent is not None and agent.status is AgentStatus.SUSPENDED:
            raise AgentSuspendedError(debriefer_agent_id)
        if agent is not None and agent.status is not AgentStatus.VERSIONED:
            raise AgentNotVersionedError(debriefer_agent_id, agent.status)

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

        # What ended the Run, recovered from its own stream. The literal
        # that used to sit here described the REQUEST rather than the Run,
        # and the model read it as the Run having ended strangely: in a
        # live rehearsal a 14B model called four of five such Runs
        # anomalous and returned the reserved DebriefDeferred verdict,
        # while a larger model shrugged it off. Either way the debrief was
        # answering a question about the wrong event. The on-demand
        # discriminator is not lost; it has always been recorded
        # separately on the Decision's `inputs.trigger`, which is where
        # provenance belongs, rather than in the model's view of the Run.
        terminal = await find_terminal_run_event(deps.event_store, command.run_id)

        payload = RunDebriefPayload(
            # A Run with no terminal event has genuinely had nothing happen
            # to it but this request, so there the old literal is the
            # honest answer rather than a fallback.
            terminal_event_type=(
                terminal.event_type if terminal is not None else _ON_DEMAND_NO_TERMINAL
            ),
            terminal_event_reason=(extract_reason(terminal) if terminal is not None else None),
            terminal_event_occurred_at=(
                terminal.occurred_at.isoformat() if terminal is not None else now.isoformat()
            ),
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
            interrupted_at=(extract_interrupted_at(terminal) if terminal is not None else None),
            capture_progress=(extract_capture_progress(terminal) if terminal is not None else None),
        )
        # Same rule as the subscriber: serve the model the Agent
        # declares, so an operator-triggered regenerate cannot reach a
        # model the catalog never approved for it.
        request = build_run_debrief_chat_request(
            payload,
            model_ref=(
                to_port_model_ref(agent.model_ref)
                if agent is not None
                else DEFAULT_RUN_DEBRIEF_MODEL
            ),
        )

        response: LLMResponse | None = None
        call_started_at = time.monotonic()
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
        duration_ms = round((time.monotonic() - call_started_at) * 1000)

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
                duration_ms=duration_ms,
                occurred_at=now,
                principal_id=debriefer_agent_id,
                debriefer_agent_id=debriefer_agent_id,
                debriefer_agent_name=(
                    str(agent.name) if agent is not None else RUN_DEBRIEFER_AGENT_NAME
                ),
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
    duration_ms: int,
    occurred_at: datetime,
    principal_id: UUID,
    debriefer_agent_id: UUID,
    debriefer_agent_name: str,
    correlation_id: UUID,
    causation_id: UUID | None,
    log: Any,
) -> None:
    """Best-effort capture of the on-demand LLM call's model provenance.

    Mirrors the subscriber path: fire-and-forget (the recorder never raises
    per its port contract; the try/except is defense-in-depth), deterministic
    inference `event_id`, recorded only after the Decision append commits.
    The inference is attributed to the agent that performed the debrief, which
    is also the principal the recorder authorizes under, so the
    operator-initiated regenerate carries the same authz requirement as the
    auto-fired subscriber path.

    The two have to be the SAME agent. `append_inferences` refuses a trace
    whose `agent_id` disagrees with its principal, and it refuses it quietly
    from the caller's point of view, because inference capture is
    fire-and-forget and the Decision has already committed. A mismatch
    therefore costs no error and no Decision, only the provenance: the model,
    the token counts, and the cost silently fail to reach
    `entries_decision_inferences`, which is the table the spend lookup and the
    record export both read.

    `duration_ms` is measured by the caller around `llm.chat(...)`, not here.
    `tool_type` is derived from whether a tool actually mediated the call
    (`response.tool_call_id` set), not a blind "function" constant: a
    local/JSON-mode adapter reaches structured output without one.
    """
    trace = AgentInferenceTrace(
        decision_id=decision_id,
        event_id=uuid5(decision_id, "inference:0"),
        occurred_at=occurred_at,
        operation_name=DECISION_REASONING_OPERATION_CHAT,
        provider_name=request.model_ref.provider,
        request_model=request.model_ref.model,
        response_id=response.response_id,
        response_model=response.model_id,
        finish_reasons=(response.stop_reason,) if response.stop_reason else (),
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cache_creation_input_tokens=response.usage.cache_creation_input_tokens,
        cache_read_input_tokens=response.usage.cache_read_input_tokens,
        cost_usd=compute_cost_usd(request.model_ref, response.usage),
        request_max_tokens=request.max_output_tokens,
        request_temperature=request.temperature,
        request_top_p=request.top_p,
        agent_id=str(debriefer_agent_id),
        agent_name=debriefer_agent_name,
        output_type="json",
        duration=duration_ms,
        tool_name=response.tool_name,
        tool_call_id=response.tool_call_id,
        tool_type="function" if response.tool_call_id is not None else None,
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
