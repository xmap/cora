"""Contract tests for OpenAICompatibleBackend against a fake OpenAI server."""

from dataclasses import replace

import pytest
from pytest_httpserver import HTTPServer

from cora.agent.adapters.openai_compatible_backend import OpenAICompatibleBackend
from cora.infrastructure.ports.llm import (
    LLMChatRequest,
    LLMContentBlock,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMServerError,
    LLMSystemPrompt,
    ModelRef,
)


def _request() -> LLMChatRequest:
    return LLMChatRequest(
        system=LLMSystemPrompt(blocks=(LLMContentBlock(text="you are a helper"),)),
        user_message=LLMContentBlock(text="summarize the run"),
        structured_output_schema={"type": "object", "properties": {"summary": {"type": "string"}}},
        model_ref=ModelRef(provider="local", model="llama-3.3-70b"),
    )


def _backend(httpserver: HTTPServer) -> OpenAICompatibleBackend:
    return OpenAICompatibleBackend(base_url=httpserver.url_for("/"), model="llama-3.3-70b")


@pytest.mark.unit
async def test_parses_a_chat_completion_into_a_local_completion(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/v1/chat/completions", method="POST").respond_with_json(
        {
            "model": "llama-3.3-70b-instruct",
            "choices": [{"message": {"content": '{"summary": "ok"}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 42, "completion_tokens": 7},
        }
    )

    completion = await _backend(httpserver).complete(_request())

    assert completion.parsed == {"summary": "ok"}
    assert completion.usage.input_tokens == 42
    assert completion.usage.output_tokens == 7
    assert completion.model_id == "llama-3.3-70b-instruct"
    assert completion.stop_reason == "stop"
    # No "id" in the fixture body (matches most OpenAI-compatible engines
    # that omit it): response_id must stay None, not a fabricated value.
    assert completion.response_id is None


@pytest.mark.unit
async def test_response_id_surfaces_when_the_server_reports_one(httpserver: HTTPServer) -> None:
    """Never uses tool-calling (structured output is
    `response_format=json_schema` directly), so `response_id` is the only
    provenance field this path can ever populate; `tool_call_id` /
    `tool_name` stay None on `LLMResponse` regardless."""
    httpserver.expect_request("/v1/chat/completions", method="POST").respond_with_json(
        {
            "id": "chatcmpl-abc123",
            "model": "llama-3.3-70b-instruct",
            "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
            "usage": {},
        }
    )

    completion = await _backend(httpserver).complete(_request())

    assert completion.response_id == "chatcmpl-abc123"


@pytest.mark.unit
async def test_sends_the_openai_structured_output_request(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/v1/chat/completions", method="POST").respond_with_json(
        {"choices": [{"message": {"content": "{}"}}], "usage": {}}
    )

    await _backend(httpserver).complete(_request())

    body = httpserver.log[0][0].get_json()
    assert body["model"] == "llama-3.3-70b"
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"]["type"] == "object"
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["system", "user"]


@pytest.mark.unit
async def test_omits_sampling_from_the_wire_when_the_caller_sets_none(
    httpserver: HTTPServer,
) -> None:
    """Silence is the honest default.

    Inventing a value would put a sampling claim on the provenance
    record that no caller ever made.
    """
    httpserver.expect_request("/v1/chat/completions", method="POST").respond_with_json(
        {"choices": [{"message": {"content": "{}"}}], "usage": {}}
    )

    await _backend(httpserver).complete(_request())

    body = httpserver.log[0][0].get_json()
    assert "temperature" not in body
    assert "top_p" not in body


@pytest.mark.unit
async def test_sends_the_sampling_the_caller_set(httpserver: HTTPServer) -> None:
    """Zero must reach the wire, not be swallowed as falsy.

    Zero is exactly the value the debrief tasks pin, so a truthiness
    check here would silently drop the only setting anyone uses.
    """
    httpserver.expect_request("/v1/chat/completions", method="POST").respond_with_json(
        {"choices": [{"message": {"content": "{}"}}], "usage": {}}
    )

    await _backend(httpserver).complete(replace(_request(), temperature=0.0, top_p=0.9))

    body = httpserver.log[0][0].get_json()
    assert body["temperature"] == 0.0
    assert body["top_p"] == 0.9


@pytest.mark.unit
async def test_non_json_content_yields_no_parsed_output(httpserver: HTTPServer) -> None:
    """A server that could not honor the schema returns prose; parsed is None so
    LocalLLM raises LLMSchemaValidationError."""
    httpserver.expect_request("/v1/chat/completions", method="POST").respond_with_json(
        {"choices": [{"message": {"content": "I could not produce JSON."}}], "usage": {}}
    )

    completion = await _backend(httpserver).complete(_request())

    assert completion.parsed is None


@pytest.mark.unit
async def test_malformed_success_body_translates_to_llm_server_error(
    httpserver: HTTPServer,
) -> None:
    """A 200 whose body is not JSON must surface as an LLM error, not a raw decode error."""
    httpserver.expect_request("/v1/chat/completions", method="POST").respond_with_data(
        "not json at all", status=200
    )
    with pytest.raises(LLMServerError):
        await _backend(httpserver).complete(_request())


@pytest.mark.unit
async def test_server_error_translates_to_llm_server_error(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/v1/chat/completions", method="POST").respond_with_data(
        "internal error", status=500
    )
    with pytest.raises(LLMServerError):
        await _backend(httpserver).complete(_request())


@pytest.mark.unit
async def test_rate_limit_translates_to_llm_rate_limit_error(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/v1/chat/completions", method="POST").respond_with_data(
        "slow down", status=429
    )
    with pytest.raises(LLMRateLimitError):
        await _backend(httpserver).complete(_request())


@pytest.mark.unit
async def test_bad_request_translates_to_llm_invalid_request_error(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/v1/chat/completions", method="POST").respond_with_data(
        "no such model", status=404
    )
    with pytest.raises(LLMInvalidRequestError):
        await _backend(httpserver).complete(_request())
