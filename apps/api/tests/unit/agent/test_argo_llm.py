"""Unit tests for `ArgoLLM`.

The gateway speaks the Anthropic Messages protocol verbatim, so the
request assembly, cache wiring, and error translation are covered once
in `test_anthropic_llm.py` and are not re-tested here. What IS tested
is everything the gateway does differently: the model-identifier map,
the refusal of a snapshot pin it cannot honor, and the guard that stops
a gateway-served call from being priced as a direct-vendor purchase.

A `_FakeAsyncAnthropic` is injected through the `client` kwarg, so no
test reaches the gateway. The recorded facts these fakes stand in for
were measured against the live endpoint on 2026-08-18 and are cited in
the adapter's module docstring.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportPrivateUsage=false

from typing import Any

import pytest
from anthropic.types import Message, ToolUseBlock, Usage

from cora.agent.adapters.argo_llm import (
    ARGO_PROVIDER_NAME,
    ArgoLLM,
    resolve_argo_model_id,
)
from cora.infrastructure.observability.gen_ai import PRICING
from cora.infrastructure.ports.llm import (
    LLMChatRequest,
    LLMContentBlock,
    LLMInvalidRequestError,
    LLMSystemPrompt,
    ModelRef,
)


class _FakeMessages:
    def __init__(self, response: Message) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Message:
        self.calls.append(kwargs)
        return self._response


class _FakeAsyncAnthropic:
    def __init__(self, response: Message) -> None:
        self.messages = _FakeMessages(response)


def _served_message(*, model: str = "claude-haiku-4-5-20251001") -> Message:
    """A gateway response, shaped as the live endpoint actually returns one.

    `model` defaults to the dated snapshot the gateway reported when a
    bare `claudehaiku45` was requested, which is the fact the
    served-snapshot test depends on.
    """
    return Message(
        id="msg_vrtx_test_01",
        type="message",
        role="assistant",
        content=[
            ToolUseBlock(
                type="tool_use",
                id="toolu_vrtx_test_01",
                name="cora_structured_output",
                input={"choice": "NominalCompletion"},
            )
        ],
        model=model,
        stop_reason="tool_use",
        stop_sequence=None,
        usage=Usage(
            input_tokens=703,
            output_tokens=69,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
            cache_creation=None,
            server_tool_use=None,
            service_tier=None,
        ),
    )


def _request(
    *,
    provider: str = ARGO_PROVIDER_NAME,
    model: str = "claude-haiku-4-5",
    snapshot_pin: str | None = None,
) -> LLMChatRequest:
    return LLMChatRequest(
        system=LLMSystemPrompt(blocks=(LLMContentBlock(text="You are CORA."),)),
        user_message=LLMContentBlock(text="Debrief this Run."),
        structured_output_schema={"type": "object"},
        model_ref=ModelRef(provider=provider, model=model, snapshot_pin=snapshot_pin),
    )


@pytest.mark.unit
def test_model_id_maps_an_upstream_name_to_the_gateway_handle() -> None:
    resolved = resolve_argo_model_id(
        ModelRef(provider=ARGO_PROVIDER_NAME, model="claude-haiku-4-5")
    )
    assert resolved == "claudehaiku45"


@pytest.mark.unit
def test_model_id_rejects_a_snapshot_pin_the_gateway_cannot_honor() -> None:
    """A pin the gateway ignores must fail loudly, not read as reproducible."""
    model_ref = ModelRef(
        provider=ARGO_PROVIDER_NAME, model="claude-haiku-4-5", snapshot_pin="20251001"
    )
    with pytest.raises(LLMInvalidRequestError) as excinfo:
        resolve_argo_model_id(model_ref)
    assert "cannot pin snapshot" in str(excinfo.value)


@pytest.mark.unit
def test_model_id_rejects_an_unmapped_model_and_names_the_known_ones() -> None:
    """The gateway's catalog is not the vendor's, so the error must say what is there."""
    with pytest.raises(LLMInvalidRequestError) as excinfo:
        resolve_argo_model_id(ModelRef(provider=ARGO_PROVIDER_NAME, model="claude-fable-5"))
    message = str(excinfo.value)
    assert "claude-fable-5" in message
    assert "claudehaiku45" not in message
    assert "claude-haiku-4-5" in message


@pytest.mark.unit
def test_every_statically_priced_anthropic_model_has_a_gateway_handle() -> None:
    """A model CORA can price must also be one it can reach through the gateway.

    The two sides come from different places (the pricing table is
    maintained against vendor list prices, the map against the
    gateway's `/v1/models`), so this catches the drift where a newly
    priced model is selectable but unroutable.
    """
    priced = {model for provider, model in PRICING if provider == "anthropic"}
    unroutable = {
        model
        for model in priced
        if _resolution_failed(ModelRef(provider=ARGO_PROVIDER_NAME, model=model))
    }
    assert unroutable == set()


def _resolution_failed(model_ref: ModelRef) -> bool:
    try:
        resolve_argo_model_id(model_ref)
    except LLMInvalidRequestError:
        return True
    return False


@pytest.mark.unit
async def test_chat_sends_the_gateway_handle_rather_than_the_upstream_name() -> None:
    client = _FakeAsyncAnthropic(_served_message())
    adapter = ArgoLLM(username="svcbeamline", client=client)  # type: ignore[arg-type]

    await adapter.chat(_request(model="claude-haiku-4-5"))

    assert client.messages.calls[0]["model"] == "claudehaiku45"


@pytest.mark.unit
async def test_chat_reports_the_snapshot_the_gateway_actually_served() -> None:
    """The pin cannot be requested, but the served snapshot still reaches the record."""
    client = _FakeAsyncAnthropic(_served_message(model="claude-haiku-4-5-20251001"))
    adapter = ArgoLLM(username="svcbeamline", client=client)  # type: ignore[arg-type]

    response = await adapter.chat(_request())

    assert response.model_id == "claude-haiku-4-5-20251001"


@pytest.mark.unit
async def test_chat_rejects_a_model_ref_priced_as_a_direct_vendor_purchase() -> None:
    """Cost resolves from `ModelRef.provider`, so a mismatch would misprice the call.

    Serving through the gateway while pricing the entry as `anthropic`
    bills a facility-funded call at the deployment's own list rate. The
    two identities have to agree or the buy-vs-build comparison is
    measuring the wrong thing.
    """
    client = _FakeAsyncAnthropic(_served_message())
    adapter = ArgoLLM(username="svcbeamline", client=client)  # type: ignore[arg-type]

    with pytest.raises(LLMInvalidRequestError) as excinfo:
        await adapter.chat(_request(provider="anthropic"))

    assert "anthropic" in str(excinfo.value)
    assert client.messages.calls == []
