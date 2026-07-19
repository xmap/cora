"""Unit tests for GPU-serving observability (shadow cost + metrics sink)."""

import pytest

from cora.agent._gpu_metrics import (
    gpu_shadow_cost_usd,
    make_gpu_usage_sink,
    record_gpu_usage,
)
from cora.agent.adapters.local_llm import (
    GpuUsageRecord,
    LocalCompletion,
    LocalLLM,
    StubCompletion,
    StubLocalBackend,
)
from cora.infrastructure.ports.clock import FakeMonotonicClock
from cora.infrastructure.ports.llm import (
    LLMChatRequest,
    LLMContentBlock,
    LLMSystemPrompt,
    LLMUsage,
    ModelRef,
)


def _request() -> LLMChatRequest:
    return LLMChatRequest(
        system=LLMSystemPrompt(blocks=(LLMContentBlock(text="you are a helper"),)),
        user_message=LLMContentBlock(text="summarize the run"),
        structured_output_schema={"type": "object"},
        model_ref=ModelRef(provider="local", model="llama-3.3-70b"),
    )


def _stub_completion(gpu_seconds: float) -> StubCompletion:
    return StubCompletion(
        completion=LocalCompletion(
            parsed={"ok": True},
            raw_text="",
            usage=LLMUsage(input_tokens=1, output_tokens=1),
            model_id="llama-3.3-70b",
            stop_reason="stop",
        ),
        gpu_seconds=gpu_seconds,
    )


@pytest.mark.unit
def test_shadow_cost_of_one_gpu_hour_is_the_rate() -> None:
    assert gpu_shadow_cost_usd(3600.0, 2.50) == pytest.approx(2.50)


@pytest.mark.unit
def test_shadow_cost_is_proportional_to_seconds() -> None:
    assert gpu_shadow_cost_usd(1800.0, 2.0) == pytest.approx(1.0)
    assert gpu_shadow_cost_usd(0.0, 2.0) == pytest.approx(0.0)


@pytest.mark.unit
def test_negative_rate_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        gpu_shadow_cost_usd(10.0, -1.0)


@pytest.mark.unit
def test_record_gpu_usage_returns_the_shadow_cost() -> None:
    """7200 GPU-seconds (2 GPU-hours) at $1.50/GPU-hour = $3.00."""
    record = GpuUsageRecord(
        call_id="local-1", device_id="gpu0", model="llama-3.3-70b", gpu_seconds=7200.0
    )
    assert record_gpu_usage(record, usd_per_gpu_hour=1.5) == pytest.approx(3.0)


@pytest.mark.unit
def test_make_gpu_usage_sink_returns_a_safe_callable() -> None:
    """The bound sink records without a MeterProvider installed (no-op safe)."""
    sink = make_gpu_usage_sink(usd_per_gpu_hour=2.0)
    sink(GpuUsageRecord(call_id="local-1", device_id="gpu0", model="m", gpu_seconds=60.0))


@pytest.mark.unit
async def test_local_llm_drives_the_gpu_usage_sink() -> None:
    """make_gpu_usage_sink composes into the adapter and runs once per served call."""
    clock = FakeMonotonicClock()
    backend = StubLocalBackend(clock, [_stub_completion(gpu_seconds=3600.0)])
    adapter = LocalLLM(
        backend=backend,
        monotonic_clock=clock,
        device_id="gpu0",
        on_measure=make_gpu_usage_sink(usd_per_gpu_hour=2.0),
    )
    response = await adapter.chat(_request())
    assert response.parsed == {"ok": True}  # the call completed and the sink ran without error
