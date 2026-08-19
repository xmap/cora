"""End-to-end serving test: the wired Argo path against a fake gateway.

The sibling `test_argo_llm.py` injects a fake SDK client, which proves
the adapter's own logic but skips the one thing composing the vendor
SDK with a foreign `base_url` actually risks: that the SDK builds the
request the gateway expects. A live curl to `/argoapi/v1/messages`
already showed the gateway answers that path (2026-08-18); what was
never shown is that `AsyncAnthropic(base_url=...)` composes the same
one, rather than swallowing the `/argoapi` prefix or rooting the path
at the host.

So this runs the FULL path against a pytest-httpserver standing in for
the gateway: `build_llm` -> `ArgoLLM` -> `AnthropicLLM` -> the real SDK
-> a real HTTP round-trip -> response parsing. The served payload is
shaped from a response the live gateway actually returned, including
its Vertex-flavored identifiers and the `cache_creation` breakdown.

(Marked `unit` because pytest-httpserver runs in-process, following
`test_local_serving_end_to_end.py`.)
"""

from typing import Any

import pytest
from pydantic import SecretStr
from pytest_httpserver import HTTPServer

from cora.agent.build_llm import build_llm
from cora.infrastructure.config import Settings
from cora.infrastructure.ports.llm import (
    LLMChatRequest,
    LLMContentBlock,
    LLMSystemPrompt,
    ModelRef,
)

_GATEWAY_PREFIX = "/argoapi"
_USERNAME = "svcbeamline"


def _request() -> LLMChatRequest:
    return LLMChatRequest(
        system=LLMSystemPrompt(blocks=(LLMContentBlock(text="you are a helper"),)),
        user_message=LLMContentBlock(text="summarize the run"),
        structured_output_schema={"type": "object"},
        model_ref=ModelRef(provider="argo", model="claude-haiku-4-5"),
    )


def _served_response() -> dict[str, Any]:
    """The shape the live gateway returned for a forced tool-use call."""
    return {
        "id": "msg_vrtx_011CeBFHm78HH9QZX4nmuXsB",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-4-5-20251001",
        "stop_reason": "tool_use",
        "stop_sequence": None,
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_vrtx_019bu9WhX9BVPD7q6qjeRNZr",
                "name": "cora_structured_output",
                "input": {"verdict": "nominal", "confidence": 0.95},
            }
        ],
        "usage": {
            "input_tokens": 440,
            "output_tokens": 69,
            "cache_creation_input_tokens": 5990,
            "cache_read_input_tokens": 0,
            "cache_creation": {
                "ephemeral_1h_input_tokens": 5990,
                "ephemeral_5m_input_tokens": 0,
            },
        },
    }


@pytest.mark.unit
async def test_wired_argo_llm_reaches_the_gateway_path_and_parses_the_response(
    httpserver: HTTPServer,
) -> None:
    """The SDK's base_url composition lands on the gateway's own messages path."""
    httpserver.expect_request(f"{_GATEWAY_PREFIX}/v1/messages", method="POST").respond_with_json(
        _served_response()
    )
    settings = Settings(  # type: ignore[call-arg]
        llm_enabled=True,
        llm_provider="argo",
        argo_username=SecretStr(_USERNAME),
        argo_base_url=httpserver.url_for(_GATEWAY_PREFIX),
    )
    llm = build_llm(settings)
    assert llm is not None

    response = await llm.chat(_request())

    assert response.parsed == {"verdict": "nominal", "confidence": 0.95}
    assert response.model_id == "claude-haiku-4-5-20251001"
    assert response.usage.cache_creation_input_tokens == 5990


@pytest.mark.unit
async def test_wired_argo_llm_sends_the_bare_username_as_the_api_key(
    httpserver: HTTPServer,
) -> None:
    """The gateway takes a domain username where a vendor takes an issued key."""
    httpserver.expect_request(f"{_GATEWAY_PREFIX}/v1/messages", method="POST").respond_with_json(
        _served_response()
    )
    settings = Settings(  # type: ignore[call-arg]
        llm_enabled=True,
        llm_provider="argo",
        argo_username=SecretStr(_USERNAME),
        argo_base_url=httpserver.url_for(_GATEWAY_PREFIX),
    )
    llm = build_llm(settings)
    assert llm is not None

    await llm.chat(_request())

    sent = httpserver.log[0][0]
    assert sent.headers["x-api-key"] == _USERNAME
    assert sent.get_json()["model"] == "claudehaiku45"
