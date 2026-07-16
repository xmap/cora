"""Anthropic implementation of `LLM`.

Lives under `cora.agent.adapters` per the cross-BC
adapter-ownership convention (Safety BC owns
`PostgresClearanceLookup`, Caution BC owns `PostgresCautionLookup`,
Agent BC owns this).

## Structured output via tool-use

The Anthropic API exposes structured output through the
tool-use-as-structured-output convention: define a single tool
whose `input_schema` IS the desired output schema, set
`tool_choice` to force that tool, then parse the resulting
`tool_use` block's `input` field as the output.

This convention has been stable since Claude 3.5 Sonnet (mid-2024)
and survives across model upgrades. The adapter generates the
synthetic tool name `cora_structured_output` (a single name across
all calls so the cache layer for the tools block remains stable;
the `input_schema` differs per call but the tool definition's
position in the request is identical).

## Cache breakpoints

`LLMContentBlock.cache` markers are translated to
`cache_control={"type": "ephemeral", "ttl": ...}` on the
corresponding `TextBlockParam`. Anthropic accepts at most 4
cache-marked blocks per request across system + tools + messages;
the adapter raises `LLMInvalidRequestError` BEFORE the API call
when this is exceeded so misconfigured prompts fail loudly.

When any breakpoint requests the `"1h"` TTL, the adapter sets the
`anthropic-beta: extended-cache-ttl-2025-04-11` header (the 1h tier
is gated behind this beta flag).

## Retries

The Anthropic SDK ships with `max_retries=2` exponential backoff
out of the box (0.5s to 8s on 408/409/429/5xx + connection
errors). The adapter uses this default unchanged per the design
memo lock; setting `max_retries=2` explicitly here makes the value
auditable from the adapter without grepping SDK source. The
10-minute request timeout is a defensive ceiling: RunDebriefer
generation typically completes in 5-15 seconds; 600s catches
catastrophic provider stalls without paying for a forever-hung
subscriber call.

## Error translation

After the SDK exhausts inner retries, any remaining SDK error is
translated to the `LLM` taxonomy so consumers depend only on
the port-level error classes. Mapping:

  - `AuthenticationError` (401 / 403) -> `LLMAuthenticationError`
  - `RateLimitError` (429)            -> `LLMRateLimitError`
  - `APITimeoutError`                 -> `LLMTimeoutError`
  - `BadRequestError` (400)           -> `LLMInvalidRequestError`
  - `InternalServerError` (5xx)       -> `LLMServerError`
  - `APIConnectionError`              -> `LLMServerError` (network-flavored)
  - Any other `APIStatusError`        -> `LLMServerError` (defensive default)
  - Tool-use missing / schema mismatch on response -> `LLMSchemaValidationError`
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import anthropic
from anthropic.types import (
    CacheControlEphemeralParam,
    TextBlockParam,
    ToolParam,
    ToolUseBlock,
)
from opentelemetry import trace

from cora.infrastructure.observability.gen_ai import record_llm_call
from cora.infrastructure.ports.llm import (
    CacheBreakpoint,
    LLMAuthenticationError,
    LLMChatRequest,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMResponse,
    LLMSchemaValidationError,
    LLMServerError,
    LLMTimeoutError,
    LLMUsage,
    ModelRef,
)

if TYPE_CHECKING:
    from anthropic.types.tool_choice_tool_param import ToolChoiceToolParam

# Single stable tool name across every call so the tools-layer
# cache breakpoint stays warm. The schema differs per call (lives
# in `input_schema`); the name does not.
_STRUCTURED_OUTPUT_TOOL_NAME = "cora_structured_output"

# Anthropic's per-request limit on cache_control markers. Exceeding
# it is rejected by the API; we validate client-side so adapters
# fail loudly with a useful message instead of cryptic 400.
_MAX_CACHE_BREAKPOINTS = 4

# Default request-level timeout for one LLM call (seconds). Catches
# catastrophic stalls without exceeding the design's 10-minute
# ceiling. Adjustable via constructor for tests / future tuning.
_DEFAULT_REQUEST_TIMEOUT_SECONDS = 600.0

# Anthropic SDK default retries; pinned here for auditability per
# the design memo (max_retries=2, exponential 0.5s-8s).
_DEFAULT_MAX_RETRIES = 2

# Beta header required when any cache breakpoint requests the 1h
# TTL. The 5m TTL is the default tier and doesn't need a header.
_EXTENDED_CACHE_TTL_BETA = "extended-cache-ttl-2025-04-11"

_tracer = trace.get_tracer("cora.agent.llm")


class AnthropicLLM:
    """Production `LLM` implementation backed by `anthropic.AsyncAnthropic`.

    Constructor accepts `api_key` directly (read from `Settings.anthropic_api_key`
    by the Kernel factory) rather than implicitly via the SDK's env-var
    lookup. Centralising the credential at the composition root keeps
    sensitive material off the global environment for the rest of the
    process and gives tests a clean injection point.

    Optionally accepts an explicit `client: AsyncAnthropic` for tests
    that want to wire a mock or a recorded fixture; production wiring
    leaves it `None` and the adapter constructs its own.
    """

    def __init__(
        self,
        *,
        api_key: str,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        request_timeout_seconds: float = _DEFAULT_REQUEST_TIMEOUT_SECONDS,
        client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        self._client = client or anthropic.AsyncAnthropic(
            api_key=api_key,
            max_retries=max_retries,
            timeout=request_timeout_seconds,
        )

    async def aclose(self) -> None:
        """Release the underlying httpx connection pool.

        Wired into `Kernel.Teardown` from `cora.api.main` so the
        FastAPI lifespan closes the SDK client at shutdown. Without
        this the underlying `httpx.AsyncClient` leaks its connection
        pool on every process exit (a watch item flagged at gate
        review).
        """
        await self._client.close()

    async def chat(self, request: LLMChatRequest) -> LLMResponse:
        cache_count = _count_cache_breakpoints(request)
        if cache_count > _MAX_CACHE_BREAKPOINTS:
            msg = (
                f"LLMChatRequest has {cache_count} cache breakpoints; "
                f"Anthropic accepts at most {_MAX_CACHE_BREAKPOINTS}. "
                "Merge layers or drop a breakpoint."
            )
            raise LLMInvalidRequestError(msg)

        system_blocks: list[TextBlockParam] = [
            _to_text_block_param(block.text, block.cache) for block in request.system.blocks
        ]
        user_blocks: list[TextBlockParam] = [
            _to_text_block_param(request.user_message.text, request.user_message.cache)
        ]

        synthetic_tool = ToolParam(
            name=_STRUCTURED_OUTPUT_TOOL_NAME,
            description=(
                "Emit the structured Decision payload. Always call this tool exactly "
                "once; do not return free-form prose. Every field in the input_schema "
                "is required unless marked optional."
            ),
            input_schema=cast("dict[str, object]", dict(request.structured_output_schema)),
        )
        tool_choice: ToolChoiceToolParam = {
            "type": "tool",
            "name": _STRUCTURED_OUTPUT_TOOL_NAME,
        }

        extra_headers = _maybe_extended_cache_header(request)
        model_id = _resolve_model_id(request.model_ref)

        with _tracer.start_as_current_span("llm.chat") as span:
            try:
                message = await self._client.messages.create(
                    model=model_id,
                    max_tokens=request.max_output_tokens,
                    system=system_blocks,
                    messages=[{"role": "user", "content": user_blocks}],
                    tools=[synthetic_tool],
                    tool_choice=tool_choice,
                    extra_headers=extra_headers,
                )
            except anthropic.AuthenticationError as exc:
                raise LLMAuthenticationError(str(exc)) from exc
            except anthropic.RateLimitError as exc:
                raise LLMRateLimitError(str(exc)) from exc
            except anthropic.APITimeoutError as exc:
                raise LLMTimeoutError(str(exc)) from exc
            except anthropic.BadRequestError as exc:
                raise LLMInvalidRequestError(str(exc)) from exc
            except anthropic.InternalServerError as exc:
                raise LLMServerError(str(exc)) from exc
            except anthropic.APIConnectionError as exc:
                raise LLMServerError(f"network error: {exc}") from exc
            except anthropic.APIStatusError as exc:
                # Defensive default for any APIStatusError subclass not
                # named above. Mapping to LLMServerError treats it as
                # retryable; the alternative (silently surfacing the SDK
                # exception) would skip the retry layer.
                raise LLMServerError(str(exc)) from exc

            parsed = _extract_structured_output(message)
            raw_text = _extract_raw_text(message)
            usage = _to_llm_usage(message.usage)
            response_model_id = message.model
            stop_reason = message.stop_reason or "end_turn"

            # `record_llm_call` returns the computed USD cost; the
            # adapter intentionally discards it here. The cost is
            # persisted on the `cora.agent.llm.cost.usd` histogram
            # (where dashboards consume it), and durably by the LLM
            # producers, which recompute it via `compute_cost_usd`
            # (same pure function, same inputs) onto the inference
            # entry's cost_usd. Surfacing it on `LLMResponse` would
            # force every consumer to think about pricing semantics;
            # consumers that want the value compute it from usage.
            record_llm_call(
                span,
                provider_name="anthropic",
                request_model_ref=request.model_ref,
                response_model_id=response_model_id,
                usage=usage,
                stop_reason=stop_reason,
                max_tokens=request.max_output_tokens,
            )

            return LLMResponse(
                parsed=parsed,
                raw_text=raw_text,
                usage=usage,
                stop_reason=stop_reason,
                model_id=response_model_id,
            )


def _count_cache_breakpoints(request: LLMChatRequest) -> int:
    """Sum cache markers across system + user blocks.

    The adapter does NOT include the synthetic structured-output
    tool in the count because it never carries `cache_control` here
    (the schema differs per call so caching the tool definition
    would be meaningless). Tools-layer caching for stable tools
    (such as a future RecipeScreener) lands when an additive `tools`
    field appears on `LLMChatRequest`.
    """
    count = 0
    for block in request.system.blocks:
        if block.cache is not None:
            count += 1
    if request.user_message.cache is not None:
        count += 1
    return count


def _to_text_block_param(
    text: str,
    cache: CacheBreakpoint | None,
) -> TextBlockParam:
    if cache is None:
        return {"type": "text", "text": text}
    cache_control = CacheControlEphemeralParam(type="ephemeral", ttl=cache.ttl)
    return {"type": "text", "text": text, "cache_control": cache_control}


def _maybe_extended_cache_header(request: LLMChatRequest) -> dict[str, str]:
    """Return the beta header dict when any breakpoint asks for 1h TTL.

    Empty dict otherwise (`AsyncAnthropic.messages.create(extra_headers={})`
    is a no-op; we always pass the kwarg so the SDK doesn't trip on
    `None` in some edge path).
    """
    needs_1h = any(
        block.cache is not None and block.cache.ttl == "1h" for block in request.system.blocks
    ) or (request.user_message.cache is not None and request.user_message.cache.ttl == "1h")
    if needs_1h:
        return {"anthropic-beta": _EXTENDED_CACHE_TTL_BETA}
    return {}


def _resolve_model_id(model_ref: ModelRef) -> str:
    """Resolve `ModelRef` to the API-level model identifier.

    Anthropic accepts either `claude-opus-4-7` (latest stable) or
    a pinned snapshot like `claude-opus-4-7-20260301`. We compose
    `<model>-<snapshot_pin>` when a pin is set; otherwise the bare
    model name selects "latest stable for this model family" per
    Anthropic's convention.
    """
    if model_ref.snapshot_pin is None:
        return model_ref.model
    return f"{model_ref.model}-{model_ref.snapshot_pin}"


def _extract_structured_output(message: anthropic.types.Message) -> dict[str, object]:
    """Find the synthetic-tool input block; raise if absent or wrong-named.

    The SDK's typing guarantees `ToolUseBlock.input` is `dict[str, object]`
    (Anthropic JSON-decodes server-side). We trust the type at the
    structural level and validate presence-by-name, not shape.
    """
    for block in message.content:
        if isinstance(block, ToolUseBlock) and block.name == _STRUCTURED_OUTPUT_TOOL_NAME:
            return block.input
    msg = (
        f"response had no tool_use block named {_STRUCTURED_OUTPUT_TOOL_NAME!r}; "
        f"stop_reason={message.stop_reason}, content_block_types="
        f"{[b.type for b in message.content]}"
    )
    raise LLMSchemaValidationError(msg)


def _extract_raw_text(message: anthropic.types.Message) -> str:
    """Concatenate every TextBlock in the response into a single string.

    Tool-use-structured-output responses often have zero TextBlocks
    (the model went straight to the tool call). Returning `""` in
    that case is intentional: the structured output is in `parsed`,
    not in raw_text.
    """
    parts: list[str] = []
    for block in message.content:
        if block.type == "text":
            parts.append(block.text)
    return "".join(parts)


def _to_llm_usage(usage: anthropic.types.Usage) -> LLMUsage:
    """Map Anthropic's Usage shape to the port-level LLMUsage.

    Cache fields default to 0 in `Usage` when caching wasn't used
    or the provider didn't return them; the dataclass coerces None
    to 0 defensively.
    """
    return LLMUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_creation_input_tokens=usage.cache_creation_input_tokens or 0,
        cache_read_input_tokens=usage.cache_read_input_tokens or 0,
    )


__all__ = ["AnthropicLLM"]
