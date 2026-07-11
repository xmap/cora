"""MCP tool for the `append_inferences` slice.

Single-entry-per-call shape at the MCP boundary (LLMs construct
one tool call per trace event; batching is more natural at the
HTTP layer where producers buffer their own batches). Internally
wraps the single entry as a length-1 tuple and calls the same
batch-shaped handler.

## OpenTelemetry MCP semconv alignment (gate-review L12)

Per the survey corpus: OTel published gen_ai/mcp semconv that
says MCP servers should propagate trace context via `params._meta`.
This tool's gen_ai.* fields are already the right vocabulary; when
the MCP server-side trace propagation lands as a separate phase,
incoming `params._meta` becomes the source of trace context and
this tool reads + threads it. No schema change to the entry.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.decision.features.append_inferences.command import (
    AppendInferences,
    ReasoningEntryInput,
)
from cora.decision.features.append_inferences.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class AppendReasoningEntriesOutput(BaseModel):
    """Structured output of the `append_inferences` MCP tool."""

    event_count: int = Field(..., ge=0)


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `append_inferences` tool on the FastMCP server."""

    @mcp.tool(
        name="append_inferences",
        description=(
            "Append one AI-decider reasoning entry to a Decision's reasoning "
            "logbook. Lazy open-on-first-write: the logbook is opened "
            "automatically on the first append. Producer supplies UUIDv7 "
            "event_id; retries with the same id are silent no-ops (PK "
            "dedup). Fields follow OpenTelemetry GenAI semantic-convention "
            "v1.38: provider_name + operation_name + request_model are "
            "required discriminators; rest are optional."
        ),
    )
    async def append_reasoning_entries_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        decision_id: Annotated[UUID, Field(description="Target decision's id.")],
        event_id: Annotated[
            UUID,
            Field(description="Producer-supplied UUIDv7 entry id (dedup key)."),
        ],
        occurred_at: Annotated[
            datetime,
            Field(description="Domain time (ISO-8601 with timezone) of the trace event."),
        ],
        operation_name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=100,
                description=(
                    "OTel gen_ai.operation.name. Well-known: chat, "
                    "text_completion, embeddings, execute_tool, "
                    "invoke_agent, create_agent."
                ),
            ),
        ],
        provider_name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=100,
                description=(
                    "OTel gen_ai.provider.name (replaces deprecated "
                    "gen_ai.system). E.g. anthropic, openai, google."
                ),
            ),
        ],
        request_model: Annotated[
            str,
            Field(min_length=1, max_length=200, description="OTel gen_ai.request.model."),
        ],
        duration: Annotated[int | None, Field(default=None, ge=0)] = None,
        response_id: Annotated[str | None, Field(default=None, max_length=200)] = None,
        response_model: Annotated[str | None, Field(default=None, max_length=200)] = None,
        request_temperature: Annotated[float | None, Field(default=None)] = None,
        request_top_p: Annotated[float | None, Field(default=None)] = None,
        request_max_tokens: Annotated[int | None, Field(default=None, ge=0)] = None,
        output_type: Annotated[str | None, Field(default=None, max_length=100)] = None,
        finish_reasons: Annotated[
            list[str] | None,
            Field(default=None, max_length=16),
        ] = None,
        input_tokens: Annotated[int | None, Field(default=None, ge=0, le=1_000_000_000)] = None,
        output_tokens: Annotated[int | None, Field(default=None, ge=0, le=1_000_000_000)] = None,
        cost_usd: Annotated[
            float | None,
            Field(
                default=None,
                ge=0.0,
                allow_inf_nan=False,
                description=(
                    "Actual call cost in USD computed from usage tokens and "
                    "provider pricing (CORA custom; no OTel attribute exists "
                    "for call cost)."
                ),
            ),
        ] = None,
        agent_id: Annotated[
            str | None,
            Field(
                default=None,
                max_length=200,
                description=(
                    "OTel gen_ai.agent.id. Principal-bound: when set, it MUST equal "
                    "the calling principal's id (agent-attributed entries are the "
                    "spend ledger the AgentBudget gate sums; self-reporting only). "
                    "Mismatches reject the whole batch with 403."
                ),
            ),
        ] = None,
        agent_name: Annotated[str | None, Field(default=None, max_length=200)] = None,
        agent_description: Annotated[str | None, Field(default=None, max_length=2000)] = None,
        conversation_id: Annotated[str | None, Field(default=None, max_length=200)] = None,
        tool_name: Annotated[str | None, Field(default=None, max_length=200)] = None,
        tool_call_id: Annotated[str | None, Field(default=None, max_length=200)] = None,
        tool_type: Annotated[
            str | None,
            Field(
                default=None,
                max_length=100,
                description=("OTel gen_ai.tool.type. Values: Extension, Function, Datastore."),
            ),
        ] = None,
        messages: Annotated[
            dict[str, Any] | None,
            Field(
                default=None,
                description=("Opt-in PII-gated payload (prompt + completion bodies)."),
            ),
        ] = None,
    ) -> AppendReasoningEntriesOutput:
        handler = get_handler()
        entry = ReasoningEntryInput(
            event_id=event_id,
            occurred_at=occurred_at,
            operation_name=operation_name,
            provider_name=provider_name,
            request_model=request_model,
            duration=duration,
            response_id=response_id,
            response_model=response_model,
            request_temperature=request_temperature,
            request_top_p=request_top_p,
            request_max_tokens=request_max_tokens,
            output_type=output_type,
            finish_reasons=tuple(finish_reasons or []),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            agent_id=agent_id,
            agent_name=agent_name,
            agent_description=agent_description,
            conversation_id=conversation_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            tool_type=tool_type,
            messages=messages,
        )
        count = await handler(
            AppendInferences(decision_id=decision_id, entries=(entry,)),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return AppendReasoningEntriesOutput(event_count=count)
