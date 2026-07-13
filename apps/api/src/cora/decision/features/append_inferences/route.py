"""HTTP route for the `append_inferences` slice.

`POST /decisions/{decision_id}/inferences` returns 200 OK
with `{"event_count": N}` on success. Body shape carries a list
of OTel gen_ai.* entries; producer supplies UUIDv7 event_ids per
entry; the store dedups silently via Postgres PK.

## Response shape: 200 + event_count is the locked contract

The 8c-b standards survey looked at Langfuse / Phoenix / Datadog
ingestion APIs (which use 207 partial-success). Their 207 is
warranted because they have actual per-entry failure modes (per-
entry validation, rate limits, quotas). Our shape doesn't:
Pydantic catches structural errors at the boundary (422 for the
whole batch); Postgres `ON CONFLICT (event_id) DO NOTHING` handles
dedup silently. The only meaningful per-entry distinction would
be "newly-inserted vs deduped retry", and producers re-call
with the same event_ids safely either way.

200 + `event_count` is therefore the FINAL API contract for 8c-b,
not an interim shape. Per-entry status is deferred-with-trigger:
first consumer that genuinely needs the distinction (an audit UI
distinguishing new entries from retried ones; a producer that
gates further requests on dedup count) triggers a refactor. Until
then, simpler is correct.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.decision.features.append_inferences.command import (
    AppendInferences,
    ReasoningEntryInput,
)
from cora.decision.features.append_inferences.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)

_REASONING_ENTRY_BATCH_MAX = 100
"""Max entries per batch. Generous enough for AI-agent burst
patterns (token-stream batches, multi-tool calls per turn);
small enough that a single bad batch can't OOM the handler.
Larger batches should split client-side."""


class ReasoningEntryRequest(BaseModel):
    """One reasoning entry's input payload (OTel gen_ai.* shape).

    Required: provider_name + operation_name + request_model
    (NOT NULL discriminators per OTel semconv v1.38). Rest are
    optional; messages is the opt-in PII-gated payload.
    """

    event_id: UUID = Field(
        ...,
        description=(
            "Producer-supplied UUIDv7 entry id. Idempotency / dedup "
            "key; re-issuing the same id is a silent no-op."
        ),
    )
    occurred_at: datetime = Field(
        ...,
        description="Domain time (ISO-8601 with timezone) of the trace event.",
    )
    operation_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description=(
            "OTel gen_ai.operation.name. Well-known values: chat, "
            "text_completion, embeddings, execute_tool, invoke_agent, "
            "create_agent. Open string; new operation names accepted."
        ),
    )
    provider_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description=(
            "OTel gen_ai.provider.name (replaces deprecated gen_ai.system). "
            "Examples: anthropic, openai, google."
        ),
    )
    request_model: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="OTel gen_ai.request.model (the requested model id).",
    )
    duration: int | None = Field(
        default=None, ge=0, description="Span duration (end_time - start_time)."
    )
    response_id: str | None = Field(default=None, max_length=200)
    response_model: str | None = Field(default=None, max_length=200)
    request_temperature: float | None = Field(default=None)
    request_top_p: float | None = Field(default=None)
    request_max_tokens: int | None = Field(default=None, ge=0)
    output_type: str | None = Field(default=None, max_length=100)
    finish_reasons: list[str] = Field(
        default_factory=list[str],
        max_length=16,
        description="OTel gen_ai.response.finish_reasons (multiple stops possible).",
    )
    input_tokens: int | None = Field(default=None, ge=0, le=1_000_000_000)
    output_tokens: int | None = Field(default=None, ge=0, le=1_000_000_000)
    cost_usd: float | None = Field(
        default=None,
        ge=0.0,
        le=100_000.0,
        allow_inf_nan=False,
        description=(
            "Actual call cost in USD computed from usage tokens and provider "
            "pricing (CORA custom; no OTel attribute exists for call cost). "
            "Upper bound 100000: no single LLM call costs six figures, and "
            "an unbounded value would let one poisoned entry exhaust any "
            "instrument envelope and permanently corrupt a sealed books "
            "figure."
        ),
    )
    agent_id: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "OTel gen_ai.agent.id. Principal-bound: when set, it MUST equal "
            "the calling principal's id (agent-attributed entries are the "
            "spend ledger the AgentBudget gate sums; self-reporting only). "
            "Mismatches reject the whole batch with 403."
        ),
    )
    agent_name: str | None = Field(default=None, max_length=200)
    agent_description: str | None = Field(default=None, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=200)
    tool_name: str | None = Field(default=None, max_length=200)
    tool_call_id: str | None = Field(default=None, max_length=200)
    tool_type: str | None = Field(
        default=None,
        max_length=100,
        description="OTel gen_ai.tool.type. Values: Extension, Function, Datastore.",
    )
    messages: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Opt-in PII-gated payload: prompt + completion message bodies "
            "(OTel event-payload split). Producer responsible for JSON-"
            "roundtrippability."
        ),
    )

    model_config = {"extra": "forbid"}


class AppendReasoningEntriesRequest(BaseModel):
    """Body for `POST /decisions/{decision_id}/inferences`."""

    entries: list[ReasoningEntryRequest] = Field(
        ...,
        min_length=1,
        max_length=_REASONING_ENTRY_BATCH_MAX,
        description=(f"List of reasoning entries to append (1-{_REASONING_ENTRY_BATCH_MAX})."),
    )

    model_config = {"extra": "forbid"}


class AppendReasoningEntriesResponse(BaseModel):
    """Response body for the append slice."""

    event_count: int = Field(
        ...,
        ge=0,
        description=(
            "Number of entries accepted by the store (includes "
            "silently-deduped retries; producer can re-call with the "
            "same event_ids safely)."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.decision.append_inferences
    return handler


router = APIRouter(tags=["decision"])


@router.post(
    "/decisions/{decision_id}/inferences",
    status_code=status.HTTP_200_OK,
    response_model=AppendReasoningEntriesResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": (
                "Authorize port denied the command, or an entry's "
                "agent_id does not match the calling principal "
                "(agent-attributed entries must be self-reported)."
            ),
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Decision exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation: empty entries "
                "list, batch over cap, missing required OTel fields, "
                "invalid types."
            ),
        },
    },
    summary=(
        "Append a batch of AI-decider reasoning entries to a Decision's "
        "reasoning logbook (lazy open-on-first-write)."
    ),
)
async def post_decisions_reasoning_entries(
    decision_id: Annotated[UUID, Path(description="Target decision's id.")],
    body: AppendReasoningEntriesRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> AppendReasoningEntriesResponse:
    entries = tuple(
        ReasoningEntryInput(
            event_id=e.event_id,
            occurred_at=e.occurred_at,
            operation_name=e.operation_name,
            provider_name=e.provider_name,
            request_model=e.request_model,
            duration=e.duration,
            response_id=e.response_id,
            response_model=e.response_model,
            request_temperature=e.request_temperature,
            request_top_p=e.request_top_p,
            request_max_tokens=e.request_max_tokens,
            output_type=e.output_type,
            finish_reasons=tuple(e.finish_reasons),
            input_tokens=e.input_tokens,
            output_tokens=e.output_tokens,
            cost_usd=e.cost_usd,
            agent_id=e.agent_id,
            agent_name=e.agent_name,
            agent_description=e.agent_description,
            conversation_id=e.conversation_id,
            tool_name=e.tool_name,
            tool_call_id=e.tool_call_id,
            tool_type=e.tool_type,
            messages=e.messages,
        )
        for e in body.entries
    )
    count = await handler(
        AppendInferences(decision_id=decision_id, entries=entries),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return AppendReasoningEntriesResponse(event_count=count)
