"""Unit tests for `AnthropicLLM`.

Tests use a `_FakeAsyncAnthropic` client injected via the adapter's
`client` constructor kwarg. The fake records every `messages.create`
call and returns canned `anthropic.types.Message` objects so the
adapter logic (cache_control wiring, tool_choice forcing,
structured-output extraction, error translation) is exercised
without ever hitting the network.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false

from typing import Any

import anthropic
import httpx
import pytest
from anthropic.types import (
    Message,
    TextBlock,
    ToolUseBlock,
    Usage,
)

from cora.agent.adapters import AnthropicLLM
from cora.infrastructure.ports.llm import (
    CacheBreakpoint,
    LLMAuthenticationError,
    LLMChatRequest,
    LLMContentBlock,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMSchemaValidationError,
    LLMServerError,
    LLMSystemPrompt,
    LLMTimeoutError,
    ModelRef,
)


class _FakeMessages:
    """Captures messages.create kwargs; returns a canned Message or raises."""

    def __init__(self, response: Message | Exception) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Message:
        self.calls.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class _FakeAsyncAnthropic:
    def __init__(self, response: Message | Exception) -> None:
        self.messages = _FakeMessages(response)


def _ok_message(
    parsed: dict[str, object] | None = None,
    *,
    text_preamble: str = "",
    model: str = "claude-haiku-4-5",
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    stop_reason: str = "tool_use",
) -> Message:
    """Build a Message that the adapter can parse successfully."""
    content: list[Any] = []
    if text_preamble:
        content.append(TextBlock(type="text", text=text_preamble, citations=None))
    content.append(
        ToolUseBlock(
            type="tool_use",
            id="toolu_test_01",
            name="cora_structured_output",
            input=parsed if parsed is not None else {"choice": "NominalCompletion"},
        )
    )
    return Message(
        id="msg_test_01",
        type="message",
        role="assistant",
        content=content,
        model=model,
        stop_reason=stop_reason,  # type: ignore[arg-type]
        stop_sequence=None,
        usage=Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_input_tokens=cache_creation_input_tokens,
            cache_read_input_tokens=cache_read_input_tokens,
            cache_creation=None,
            server_tool_use=None,
            service_tier=None,
        ),
    )


def _basic_request(
    *,
    system_blocks: tuple[LLMContentBlock, ...] = (LLMContentBlock(text="You are CORA."),),
    user_text: str = "Debrief this Run.",
    user_cache: CacheBreakpoint | None = None,
    schema: dict[str, object] | None = None,
    model: str = "claude-haiku-4-5",
    provider: str = "anthropic",
    snapshot_pin: str | None = None,
    max_output_tokens: int = 512,
) -> LLMChatRequest:
    return LLMChatRequest(
        system=LLMSystemPrompt(blocks=system_blocks),
        user_message=LLMContentBlock(text=user_text, cache=user_cache),
        structured_output_schema=schema or {"type": "object"},
        model_ref=ModelRef(provider=provider, model=model, snapshot_pin=snapshot_pin),
        max_output_tokens=max_output_tokens,
    )


def _make_status_error(
    cls: type[anthropic.APIStatusError],
    *,
    status_code: int,
    body_message: str = "boom",
) -> anthropic.APIStatusError:
    """Construct an SDK APIStatusError subclass for the fake to raise.

    The SDK requires a Response object; httpx.Response with the
    matching status_code is what the SDK constructs internally.
    """
    response = httpx.Response(
        status_code=status_code,
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    return cls(message=body_message, response=response, body={"error": {"message": body_message}})


# ---------- Happy path ----------


@pytest.mark.unit
async def test_returns_parsed_output_from_tool_use_block() -> None:
    fake = _FakeAsyncAnthropic(_ok_message(parsed={"choice": "DegradedCompletion"}))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    result = await adapter.chat(_basic_request())
    assert result.parsed == {"choice": "DegradedCompletion"}


@pytest.mark.unit
async def test_concatenates_text_blocks_into_raw_text() -> None:
    fake = _FakeAsyncAnthropic(_ok_message(parsed={"x": 1}, text_preamble="thinking out loud"))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    result = await adapter.chat(_basic_request())
    assert result.raw_text == "thinking out loud"


@pytest.mark.unit
async def test_raw_text_empty_when_response_has_no_text_blocks() -> None:
    """Tool-use-only responses (pure structured output) have empty raw_text."""
    fake = _FakeAsyncAnthropic(_ok_message(parsed={}, text_preamble=""))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    result = await adapter.chat(_basic_request())
    assert result.raw_text == ""


@pytest.mark.unit
async def test_response_id_and_tool_provenance_surface_on_llm_response() -> None:
    """`message.id` and the structured-output block's `.id` / `.name` were
    read by the adapter and discarded (see
    [[project-inference-duration-unwritten]]); they must now reach
    `LLMResponse` so the inference ledger can record them."""
    fake = _FakeAsyncAnthropic(_ok_message(parsed={"choice": "NominalCompletion"}))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    result = await adapter.chat(_basic_request())
    assert result.response_id == "msg_test_01"
    assert result.tool_call_id == "toolu_test_01"
    assert result.tool_name == "cora_structured_output"


@pytest.mark.unit
async def test_usage_includes_cache_tokens() -> None:
    fake = _FakeAsyncAnthropic(
        _ok_message(
            parsed={},
            input_tokens=10,
            output_tokens=5,
            cache_creation_input_tokens=4000,
            cache_read_input_tokens=1000,
        )
    )
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    result = await adapter.chat(_basic_request())
    assert result.usage.cache_creation_input_tokens == 4000
    assert result.usage.cache_read_input_tokens == 1000


@pytest.mark.unit
async def test_response_model_id_carries_actual_provider_snapshot() -> None:
    fake = _FakeAsyncAnthropic(_ok_message(parsed={}, model="claude-opus-4-7-20260301"))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    result = await adapter.chat(
        _basic_request(model="claude-opus-4-7")  # no pin requested
    )
    assert result.model_id == "claude-opus-4-7-20260301"


# ---------- Cache wiring ----------


@pytest.mark.unit
async def test_cache_breakpoint_attaches_cache_control_to_block() -> None:
    fake = _FakeAsyncAnthropic(_ok_message(parsed={}))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    req = _basic_request(
        system_blocks=(
            LLMContentBlock(text="layer-1 cached"),
            LLMContentBlock(text="layer-2 cached for 1h", cache=CacheBreakpoint(ttl="1h")),
        )
    )
    await adapter.chat(req)
    call = fake.messages.calls[0]
    system_param = call["system"]
    assert system_param[0] == {"type": "text", "text": "layer-1 cached"}
    assert system_param[1]["cache_control"]["type"] == "ephemeral"
    assert system_param[1]["cache_control"]["ttl"] == "1h"


@pytest.mark.unit
async def test_user_block_cache_control_passed_through() -> None:
    fake = _FakeAsyncAnthropic(_ok_message(parsed={}))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    req = _basic_request(user_cache=CacheBreakpoint(ttl="5m"))
    await adapter.chat(req)
    call = fake.messages.calls[0]
    user_blocks = call["messages"][0]["content"]
    assert user_blocks[0]["cache_control"]["ttl"] == "5m"


@pytest.mark.unit
async def test_extended_cache_header_set_when_any_breakpoint_uses_1h() -> None:
    fake = _FakeAsyncAnthropic(_ok_message(parsed={}))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    req = _basic_request(
        system_blocks=(LLMContentBlock(text="x", cache=CacheBreakpoint(ttl="1h")),)
    )
    await adapter.chat(req)
    assert fake.messages.calls[0]["extra_headers"] == {
        "anthropic-beta": "extended-cache-ttl-2025-04-11"
    }


@pytest.mark.unit
async def test_extended_cache_header_absent_for_5m_only() -> None:
    fake = _FakeAsyncAnthropic(_ok_message(parsed={}))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    req = _basic_request(
        system_blocks=(LLMContentBlock(text="x", cache=CacheBreakpoint(ttl="5m")),)
    )
    await adapter.chat(req)
    assert fake.messages.calls[0]["extra_headers"] == {}


@pytest.mark.unit
async def test_rejects_more_than_four_cache_breakpoints() -> None:
    fake = _FakeAsyncAnthropic(_ok_message(parsed={}))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    blocks = tuple(
        LLMContentBlock(text=f"layer-{i}", cache=CacheBreakpoint(ttl="5m")) for i in range(5)
    )
    req = _basic_request(system_blocks=blocks)
    with pytest.raises(LLMInvalidRequestError, match="5 cache breakpoints"):
        await adapter.chat(req)
    # Fail-fast: no API call made.
    assert fake.messages.calls == []


# ---------- Tool-choice / structured output ----------


@pytest.mark.unit
async def test_forces_structured_output_tool_choice() -> None:
    fake = _FakeAsyncAnthropic(_ok_message(parsed={}))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    schema: dict[str, object] = {
        "type": "object",
        "properties": {"choice": {"type": "string"}},
    }
    await adapter.chat(_basic_request(schema=schema))
    call = fake.messages.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "cora_structured_output"}
    tools = call["tools"]
    assert len(tools) == 1
    assert tools[0]["name"] == "cora_structured_output"
    assert tools[0]["input_schema"] == schema


@pytest.mark.unit
async def test_raises_when_response_missing_tool_use_block() -> None:
    """Defensive: model returned plain text instead of calling the
    forced tool. Adapter raises LLMSchemaValidationError so the
    outer retry layer can decide on a refresh or DebriefDeferred."""
    text_only = Message(
        id="msg_test",
        type="message",
        role="assistant",
        content=[TextBlock(type="text", text="I refuse", citations=None)],
        model="claude-haiku-4-5",
        stop_reason="end_turn",
        stop_sequence=None,
        usage=Usage(
            input_tokens=1,
            output_tokens=1,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
            cache_creation=None,
            server_tool_use=None,
            service_tier=None,
        ),
    )
    fake = _FakeAsyncAnthropic(text_only)
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    with pytest.raises(LLMSchemaValidationError, match="no tool_use block"):
        await adapter.chat(_basic_request())


# ---------- Model ID resolution ----------


@pytest.mark.unit
async def test_model_id_uses_bare_name_when_no_snapshot_pin() -> None:
    fake = _FakeAsyncAnthropic(_ok_message(parsed={}))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    await adapter.chat(_basic_request(model="claude-opus-4-7", snapshot_pin=None))
    assert fake.messages.calls[0]["model"] == "claude-opus-4-7"


@pytest.mark.unit
async def test_model_id_appends_snapshot_pin_when_set() -> None:
    fake = _FakeAsyncAnthropic(_ok_message(parsed={}))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    await adapter.chat(_basic_request(model="claude-opus-4-7", snapshot_pin="20260301"))
    assert fake.messages.calls[0]["model"] == "claude-opus-4-7-20260301"


# ---------- Error translation ----------


@pytest.mark.unit
async def test_authentication_error_translates() -> None:
    fake = _FakeAsyncAnthropic(_make_status_error(anthropic.AuthenticationError, status_code=401))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    with pytest.raises(LLMAuthenticationError):
        await adapter.chat(_basic_request())


@pytest.mark.unit
async def test_rate_limit_translates() -> None:
    fake = _FakeAsyncAnthropic(_make_status_error(anthropic.RateLimitError, status_code=429))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    with pytest.raises(LLMRateLimitError):
        await adapter.chat(_basic_request())


@pytest.mark.unit
async def test_bad_request_translates() -> None:
    fake = _FakeAsyncAnthropic(_make_status_error(anthropic.BadRequestError, status_code=400))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    with pytest.raises(LLMInvalidRequestError):
        await adapter.chat(_basic_request())


@pytest.mark.unit
async def test_server_error_translates() -> None:
    fake = _FakeAsyncAnthropic(_make_status_error(anthropic.InternalServerError, status_code=500))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    with pytest.raises(LLMServerError):
        await adapter.chat(_basic_request())


@pytest.mark.unit
async def test_connection_error_translates_to_server_error() -> None:
    fake = _FakeAsyncAnthropic(
        anthropic.APIConnectionError(
            message="connection reset",
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
        )
    )
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    with pytest.raises(LLMServerError, match="network error"):
        await adapter.chat(_basic_request())


@pytest.mark.unit
async def test_timeout_error_translates() -> None:
    fake = _FakeAsyncAnthropic(
        anthropic.APITimeoutError(
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        )
    )
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    with pytest.raises(LLMTimeoutError):
        await adapter.chat(_basic_request())


@pytest.mark.unit
async def test_unknown_apistatuserror_subclass_translates_to_server_error() -> None:
    """Defensive default: any `APIStatusError` not named in the
    explicit except chain (eg. a future `ConflictError` subclass
    the SDK adds) must translate to `LLMServerError` so the iter-2b
    retry layer treats it as retryable. Without this pin the
    defensive `except anthropic.APIStatusError` at the bottom of the
    chain would silently relax retry semantics on a future SDK
    bump. Closes gate-review test-coverage P1 #1."""
    fake = _FakeAsyncAnthropic(
        _make_status_error(anthropic.APIStatusError, status_code=418, body_message="teapot")
    )
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    with pytest.raises(LLMServerError, match="teapot"):
        await adapter.chat(_basic_request())


@pytest.mark.unit
async def test_synthetic_tool_name_stable_across_calls() -> None:
    """The Anthropic prompt cache is keyed by exact prefix bytes; a
    rename of the synthetic tool name would silently invalidate
    every cached prefix in production. Pin the tool name as a
    cross-call invariant so a refactor that renames it (well-
    intentioned or not) fails this test before reaching the cache.
    Closes gate-review test-coverage P1 #2."""
    fake = _FakeAsyncAnthropic(_ok_message(parsed={}))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    await adapter.chat(_basic_request())
    fake.messages._response = _ok_message(parsed={"different": "schema"})
    await adapter.chat(_basic_request(schema={"type": "object", "x": "y"}))
    tool_names = [call["tools"][0]["name"] for call in fake.messages.calls]
    tool_choice_names = [call["tool_choice"]["name"] for call in fake.messages.calls]
    assert tool_names == ["cora_structured_output", "cora_structured_output"]
    assert tool_choice_names == ["cora_structured_output", "cora_structured_output"]


@pytest.mark.unit
async def test_none_cache_token_fields_coerce_to_zero() -> None:
    """Anthropic's `Usage.cache_creation_input_tokens` and
    `cache_read_input_tokens` are `int | None` on the SDK; the
    adapter's `or 0` coercion (anthropic_llm.py:347-348)
    converts None to 0 so `LLMUsage` stays `int` everywhere. Pin
    the coercion so a refactor to `int()` cast doesn't crash on
    None. Closes gate-review test-coverage P1 #4."""
    none_usage_message = Message(
        id="msg_test",
        type="message",
        role="assistant",
        content=[
            ToolUseBlock(
                type="tool_use",
                id="toolu_test",
                name="cora_structured_output",
                input={},
            )
        ],
        model="claude-haiku-4-5",
        stop_reason="tool_use",
        stop_sequence=None,
        usage=Usage(
            input_tokens=10,
            output_tokens=5,
            cache_creation_input_tokens=None,  # <-- the case
            cache_read_input_tokens=None,  # <-- the case
            cache_creation=None,
            server_tool_use=None,
            service_tier=None,
        ),
    )
    fake = _FakeAsyncAnthropic(none_usage_message)
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    result = await adapter.chat(_basic_request())
    assert result.usage.cache_creation_input_tokens == 0
    assert result.usage.cache_read_input_tokens == 0


# ---------- Defaults / constructor ----------


@pytest.mark.unit
def test_constructor_builds_sdk_client_when_none_passed() -> None:
    """No client= kwarg means the adapter constructs its own
    AsyncAnthropic. We can't talk to the network in unit tests but
    we can verify the construction doesn't raise."""
    adapter = AnthropicLLM(api_key="sk-test")
    assert adapter is not None


@pytest.mark.unit
async def test_max_output_tokens_flows_to_api_call() -> None:
    fake = _FakeAsyncAnthropic(_ok_message(parsed={}))
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]
    await adapter.chat(_basic_request(max_output_tokens=2048))
    assert fake.messages.calls[0]["max_tokens"] == 2048


@pytest.mark.unit
async def test_chat_rejects_a_model_ref_priced_as_another_provider() -> None:
    """The direct path refuses a mismatch too, not just the gateway's.

    Cost resolves from `ModelRef.provider` while the serving route comes
    from configuration, so an entry priced as a gateway purchase but
    served direct bills one vendor's call at another's rate. Guarding
    only the gateway direction left the quieter half of that mistake
    unguarded: the direct adapter would have served it without comment.
    """
    fake = _FakeAsyncAnthropic(_ok_message())
    adapter = AnthropicLLM(api_key="sk-test", client=fake)  # type: ignore[arg-type]

    with pytest.raises(LLMInvalidRequestError) as excinfo:
        await adapter.chat(_basic_request(provider="argo"))

    assert "argo" in str(excinfo.value)
    assert "anthropic" in str(excinfo.value)
    assert fake.messages.calls == []
