"""End-to-end serving test: the wired build path against a fake model server.

No real model is needed to test the serving stack. A pytest-httpserver
stands in for an OpenAI-compatible engine (vLLM / Ollama), and the FULL
path runs against it: `build_llm` -> `LocalLLM` -> `OpenAICompatibleBackend`
-> a real HTTP round-trip -> response parsing -> the occupancy-share meter
-> the GPU shadow-cost sink. A real model is only needed to judge output
QUALITY and real GPU numbers, neither of which an integration test checks.

(These are marked `unit` because pytest-httpserver runs in-process, not as
an external service, but they are the build path's serving integration.)
"""

import pytest
from pytest_httpserver import HTTPServer

from cora.agent._gpu_metrics import record_gpu_usage
from cora.agent.adapters.local_llm import GpuUsageRecord, LocalLLM
from cora.agent.adapters.openai_compatible_backend import OpenAICompatibleBackend
from cora.agent.build_llm import build_llm
from cora.infrastructure.config import Settings
from cora.infrastructure.ports.clock import SystemMonotonicClock
from cora.infrastructure.ports.llm import (
    LLMChatRequest,
    LLMContentBlock,
    LLMSystemPrompt,
    ModelRef,
)


def _request() -> LLMChatRequest:
    return LLMChatRequest(
        system=LLMSystemPrompt(blocks=(LLMContentBlock(text="you are a helper"),)),
        user_message=LLMContentBlock(text="summarize the run"),
        structured_output_schema={"type": "object"},
        model_ref=ModelRef(provider="local", model="llama-3.3-70b"),
    )


def _serve_one_completion(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/v1/chat/completions", method="POST").respond_with_json(
        {
            "model": "llama-3.3-70b",
            "choices": [{"message": {"content": '{"summary": "done"}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 5},
        }
    )


@pytest.mark.unit
async def test_wired_local_llm_serves_and_meters_a_call(httpserver: HTTPServer) -> None:
    """The full serving stack runs end to end against a fake engine: the adapter
    serves over real HTTP, and the real round-trip is metered and shadow-costed."""
    _serve_one_completion(httpserver)
    measures: list[GpuUsageRecord] = []
    adapter = LocalLLM(
        backend=OpenAICompatibleBackend(base_url=httpserver.url_for("/"), model="llama-3.3-70b"),
        monotonic_clock=SystemMonotonicClock(),
        device_id="gpu0",
        on_measure=measures.append,
    )

    response = await adapter.chat(_request())

    assert response.parsed == {"summary": "done"}
    assert response.usage.output_tokens == 5
    assert len(measures) == 1
    assert measures[0].gpu_seconds > 0.0  # the real HTTP round-trip was metered
    assert measures[0].device_id == "gpu0"
    # the metered seconds convert to a shadow cost the observability sink reports
    assert record_gpu_usage(measures[0], usd_per_gpu_hour=2.0) > 0.0


@pytest.mark.unit
async def test_build_llm_local_provider_serves_a_call_end_to_end(
    httpserver: HTTPServer,
) -> None:
    """The composition-root wiring (llm_provider=local) drives a real served call."""
    _serve_one_completion(httpserver)
    settings = Settings(  # type: ignore[call-arg]
        llm_enabled=True,
        llm_provider="local",
        local_llm_base_url=httpserver.url_for("/"),
        local_llm_model="llama-3.3-70b",
    )
    llm = build_llm(settings)
    assert llm is not None

    response = await llm.chat(_request())

    assert response.parsed == {"summary": "done"}
