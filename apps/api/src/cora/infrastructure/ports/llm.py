"""LLM: synchronous LLM-chat abstraction for agent BCs.

Current consumers: the RunDebriefer and CautionDrafter subscribers.
Future agents (RecipeScreener, Strategy, Budget) consume the same
port.

## Why a port

CORA's "agents as bounded contexts" stance ([[project-architecture]])
requires the LLM call to sit behind a port so:

  - Subscribers, deciders, and tests never import a vendor SDK.
  - The production adapter (`AnthropicLLM` from
    `cora.agent.adapters.anthropic_llm`) is swappable with
    `FakeLLM` test stubs that return canned responses with
    zero network traffic.
  - Provider-agnostic semantics let a future `OpenAILLM` /
    local-model adapter slot in without subscriber changes; only the
    Kernel-construction site picks the adapter.

## Cache-breakpoint model

Anthropic exposes prompt caching as `cache_control` markers on
specific content blocks. The port carries this as a
`CacheBreakpoint` field on `LLMContentBlock`: a breakpoint means
"everything up to and including this block is cached". The 8f-b
RunDebriefer layout uses 4 breakpoints (Anthropic's hard maximum):

  1. Tools layer (cached, 1h TTL)              -- empty for RunDebriefer v1
  2. Instructions + Decision schema (1h TTL)
  3. Per-Plan examples (1h TTL)
  4. Per-Run payload (uncached, variable suffix)

The TTL choice is encoded in `CacheBreakpoint.ttl`; the adapter
sets the `anthropic-beta: extended-cache-ttl-2025-04-11` header
when any breakpoint requests `"1h"`.

## Structured output

RunDebriefer and every planned agent emit a JSON-shaped Decision; the
port carries this as `structured_output_schema: dict[str, Any]` (a
JSON Schema). The Anthropic adapter implements this via the
tool-use-as-structured-output convention (defines a single synthetic
tool whose `input_schema` IS the desired output schema, forces
`tool_choice` to it, parses the `tool_use` block's `input` as the
output). This convention has been stable since the Sonnet 3.5 launch
in mid-2024 and survives the response_format proposal.

## Errors

The adapter translates SDK-specific exceptions into this port's
taxonomy. Subscriber-level retry logic (Brandur envelope + projection
bookmark) is built on top and depends on the error class
to decide retryability.

## Tools (deferred)

The `chat()` signature deliberately omits a `tools` parameter
because RunDebriefer is a read-only synthesis call.
RecipeScreener is the first tool-using agent and triggers
the additive port extension; the structured-output tool-use
shenanigan is invisible to the port consumer.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

type CacheTTL = Literal["5m", "1h"]
"""Anthropic prompt-cache TTL. Only two values supported as of 2026-02.

`"5m"` is the default Anthropic cache TTL (no extra headers
required). `"1h"` requires the `anthropic-beta:
extended-cache-ttl-2025-04-11` header and is the load-bearing tier
for RunDebriefer's 4000-5300 token cached prefix.
"""


@dataclass(frozen=True)
class ModelRef:
    """Provider + model + optional snapshot pin.

    Structurally identical to the `Agent.model_ref` aggregate VO in
    `cora.agent.aggregates.agent.state.ModelRef` — same three fields,
    same semantics. The duplication is intentional:

      - The **aggregate VO** carries domain invariants (length caps,
        whitespace trim, `InvalidModelRefError` rejection at write
        time) because callers can supply arbitrary input via
        `define_agent`.
      - This **wire shape** is what the LLM consumes; the agent
        BC's subscriber translates `Agent.model_ref ->
        LLM.ModelRef` per call. By that point the values are
        already validated; re-validating at the port would duplicate
        invariant enforcement.

    Hoisting both into one shared location is a watch item; trigger
    is "second LLM-consuming agent ships and the translation
    pattern triples". Pre-trigger: 2 dataclasses with the same fields
    and a per-call translation, documented here and on the agent
    aggregate's `ModelRef`. See [[project-run-debrief-design]] for
    the translation site.

    `provider` is a free string today (for example, `"anthropic"`); future
    `OpenAILLM` would set `"openai"`. `model` is the
    provider's model identifier. `snapshot_pin` is the dated /
    versioned snapshot suffix when the provider exposes one; `None`
    means "latest stable" semantics per provider convention.
    """

    provider: str
    model: str
    snapshot_pin: str | None = None


@dataclass(frozen=True)
class CacheBreakpoint:
    """Marks the end of a cached prefix layer.

    Attached to an `LLMContentBlock`; the adapter sets
    `cache_control` on the corresponding API block. Anthropic
    caches "everything from the start of the request up to and
    including this block" per breakpoint.
    """

    ttl: CacheTTL = "5m"


@dataclass(frozen=True)
class LLMContentBlock:
    """A single block of text in the prompt.

    A `cache` breakpoint instructs the adapter to mark this block
    with `cache_control`. Anthropic accepts at most 4
    cache-marked blocks per request across system + tools + messages
    combined; the adapter validates this and raises
    `LLMInvalidRequestError` if exceeded so misconfigured prompts
    fail fast at call time, not at the API edge.
    """

    text: str
    cache: CacheBreakpoint | None = None


@dataclass(frozen=True)
class LLMSystemPrompt:
    """Layered system prompt; each layer is one `LLMContentBlock`.

    The adapter concatenates the blocks (in order) into the API's
    system field. Blocks with a `cache` breakpoint mark cache
    boundaries; blocks without it inherit the cache state of the
    preceding block (cached if any preceding block has a
    breakpoint, uncached otherwise).
    """

    blocks: tuple[LLMContentBlock, ...]


@dataclass(frozen=True)
class LLMUsage:
    """Token counts reported by the provider after a successful call.

    `cache_creation_input_tokens` and `cache_read_input_tokens` are
    Anthropic-specific telemetry that feeds the cost histogram.
    Both default to 0 for providers that don't report cache stats
    (or when caching is not used).
    """

    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass(frozen=True)
class LLMResponse:
    """Result of a single `LLM.chat()` call.

    `parsed` is the structured output already JSON-decoded and
    schema-validated by the adapter. `raw_text` is the assistant's
    final text content; for tool-use-structured-output calls it's
    the concatenation of text blocks that preceded the tool_use
    block (often empty for pure structured-output calls).

    `stop_reason` is provider-neutral but follows Anthropic's
    vocabulary today (`end_turn`, `tool_use`, `max_tokens`,
    `stop_sequence`).

    `model_id` is the actual model that responded (the snapshot
    selected by the provider when `ModelRef.snapshot_pin` is
    `None`), surfaced for the `gen_ai.response.model` OTel
    attribute and observability dashboards.

    `response_id` is the provider's own message id (`gen_ai.response.id`):
    the join key into the provider's own logs when a recorded verdict is
    disputed. `tool_call_id` / `tool_name` are populated only by adapters
    that reach structured output through forced tool-use (the Anthropic
    family); an adapter that asks for JSON output directly (no tool
    involved) leaves both `None`, which is the honest value, not a gap.

    `gpu_seconds` is populated only by `LocalLLM`: the occupancy-share GPU
    time its meter measured for this call. Every other adapter serves over
    a vendor API with no GPU to attribute, so it stays `None` there, which
    is the honest value, not a gap. This is the only channel from the
    adapter that measured the time to the producers that build the durable
    inference trace.
    """

    parsed: Mapping[str, Any]
    raw_text: str
    usage: LLMUsage
    stop_reason: str
    model_id: str
    response_id: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    gpu_seconds: float | None = None


class LLMError(Exception):
    """Base for every LLM failure surfaced to consumers.

    Subscriber-level retry logic uses isinstance checks on the
    subclasses below to decide retryability and backoff strategy.
    """


class LLMRateLimitError(LLMError):
    """Provider returned 429 after the adapter's inner retries."""


class LLMServerError(LLMError):
    """Provider returned 5xx after the adapter's inner retries."""


class LLMTimeoutError(LLMError):
    """Adapter's request timeout elapsed before a response."""


class LLMAuthenticationError(LLMError):
    """Provider returned 401/403 (bad / missing API key, banned org)."""


class LLMInvalidRequestError(LLMError):
    """Provider returned 4xx other than 401/403/429 (malformed request)."""


class LLMSchemaValidationError(LLMError):
    """Adapter received a response that failed structured-output schema validation.

    Raised when the provider's tool-use input or JSON output doesn't
    match `structured_output_schema`. The adapter never retries this
    automatically (the prompt or schema is at fault, not the call);
    The outer retry layer may emit a `DebriefDeferred` Decision
    after enough of these.
    """


@dataclass(frozen=True)
class LLMChatRequest:
    """Bundled `chat()` arguments.

    Carried as a dataclass (rather than expanded keyword args on the
    Protocol) so future fields (`tools`, etc.) are additive without
    breaking the Protocol signature, and so the test stubs can
    pattern-match on the whole request shape.

    ## Sampling, and why it is recorded rather than left to the provider

    `temperature` and `top_p` are the sampling dials. They are optional
    and default to `None`, meaning "whatever the provider does", which
    is what every call did before they existed.

    The reason they exist is provenance, not tuning. The durable
    inference record has carried `request_temperature` and
    `request_top_p` columns since it was built, named for the
    OpenTelemetry GenAI convention, and no producer ever filled them:
    on the pilot record, 583 of 583 calls recorded their max-token
    bound and 0 of 583 recorded how they were sampled. A verdict whose
    sampling is unknown cannot be re-run, and the catalog's
    archivability tier was claiming otherwise.

    A caller that sets neither still records nothing, which is honest.
    A caller that sets them gets what it asked for written down beside
    the model and the cost.
    """

    system: LLMSystemPrompt
    user_message: LLMContentBlock
    structured_output_schema: Mapping[str, Any]
    model_ref: ModelRef
    max_output_tokens: int = 1024
    temperature: float | None = None
    top_p: float | None = None


class LLM(Protocol):
    """Synchronous-style chat call against an LLM provider.

    "Synchronous-style" in the sense of one request -> one response;
    the call itself is `async` to integrate with the FastAPI / asyncpg
    event loop. Streaming is deferred to a later phase (no consumer
    needs it; the RunDebriefer subscriber writes the Decision after
    the full response arrives).
    """

    async def chat(self, request: LLMChatRequest) -> LLMResponse: ...


@dataclass(frozen=True)
class FakeLLMResponse:
    """Configures one canned response from `FakeLLM`."""

    parsed: Mapping[str, Any]
    raw_text: str = ""
    usage: LLMUsage = field(default_factory=lambda: LLMUsage(input_tokens=0, output_tokens=0))
    stop_reason: str = "end_turn"
    model_id: str = "fake-model-v1"
    response_id: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    gpu_seconds: float | None = None


class FakeLLM:
    """Test stub LLM adapter returning a fixed queue of responses.

    Mirrors the `AllowAllAuthorize` / `AlwaysQuietCautionLookup`
    test-default convention for the LLM. Construct with a list
    of `FakeLLMResponse` (or `LLMError` instances to simulate
    failures); each `chat()` call pops one off the front. Empty
    queue raises `FakeLLMExhaustedError` so accidentally over-calling
    the stub fails loudly.

    `received` accumulates every `LLMChatRequest` the adapter saw, in
    order, so tests can pin both response shape and call-time inputs
    (system prompt layering, schema, model_ref).

    Production tests of the RunDebriefer subscriber build one of
    these per scenario and pin the resulting Decision event
    payload + usage telemetry against the canned response.
    """

    def __init__(
        self,
        responses: list[FakeLLMResponse | LLMError] | None = None,
    ) -> None:
        self._queue: list[FakeLLMResponse | LLMError] = list(responses) if responses else []
        self.received: list[LLMChatRequest] = []

    async def chat(self, request: LLMChatRequest) -> LLMResponse:
        self.received.append(request)
        if not self._queue:
            msg = (
                f"FakeLLM queue exhausted after {len(self.received)} "
                "call(s); enqueue more responses or assert on call count first"
            )
            raise FakeLLMExhaustedError(msg)
        head = self._queue.pop(0)
        if isinstance(head, LLMError):
            raise head
        return LLMResponse(
            parsed=head.parsed,
            raw_text=head.raw_text,
            usage=head.usage,
            stop_reason=head.stop_reason,
            model_id=head.model_id,
            response_id=head.response_id,
            tool_call_id=head.tool_call_id,
            tool_name=head.tool_name,
            gpu_seconds=head.gpu_seconds,
        )

    def enqueue(self, response: FakeLLMResponse | LLMError) -> None:
        """Append one more response to the queue."""
        self._queue.append(response)


class FakeLLMExhaustedError(LLMError):
    """`FakeLLM.chat()` called more times than responses enqueued."""


__all__ = [
    "LLM",
    "CacheBreakpoint",
    "CacheTTL",
    "FakeLLM",
    "FakeLLMExhaustedError",
    "FakeLLMResponse",
    "LLMAuthenticationError",
    "LLMChatRequest",
    "LLMContentBlock",
    "LLMError",
    "LLMInvalidRequestError",
    "LLMRateLimitError",
    "LLMResponse",
    "LLMSchemaValidationError",
    "LLMServerError",
    "LLMSystemPrompt",
    "LLMTimeoutError",
    "LLMUsage",
    "ModelRef",
]
