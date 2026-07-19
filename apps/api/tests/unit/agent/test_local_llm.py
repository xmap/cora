"""Unit tests for the LocalLLM adapter and its GPU metering."""

import asyncio

import pytest

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
    LLMSchemaValidationError,
    LLMSystemPrompt,
    LLMUsage,
    ModelRef,
)


def _request(user_text: str = "summarize the run", model: str = "llama-3.3-70b") -> LLMChatRequest:
    return LLMChatRequest(
        system=LLMSystemPrompt(blocks=(LLMContentBlock(text="you are a helper"),)),
        user_message=LLMContentBlock(text=user_text),
        structured_output_schema={"type": "object"},
        model_ref=ModelRef(provider="local", model=model),
    )


def _ok_completion() -> LocalCompletion:
    return LocalCompletion(
        parsed={"summary": "ok"},
        raw_text="",
        usage=LLMUsage(input_tokens=10, output_tokens=5),
        model_id="llama-3.3-70b",
        stop_reason="stop",
    )


async def _settle() -> None:
    """Let every ready task run up to its next await."""
    for _ in range(4):
        await asyncio.sleep(0)


@pytest.mark.unit
async def test_solo_call_meters_its_full_duration_and_returns_response() -> None:
    clock = FakeMonotonicClock()
    backend = StubLocalBackend(clock, [StubCompletion(_ok_completion(), gpu_seconds=2.5)])
    measures: list[GpuUsageRecord] = []
    adapter = LocalLLM(
        backend=backend, monotonic_clock=clock, device_id="gpu0", on_measure=measures.append
    )

    response = await adapter.chat(_request())

    assert response.parsed == {"summary": "ok"}
    assert response.model_id == "llama-3.3-70b"
    assert response.usage.output_tokens == 5
    assert len(measures) == 1
    assert measures[0].gpu_seconds == pytest.approx(2.5)
    assert measures[0].device_id == "gpu0"
    assert measures[0].model == "llama-3.3-70b"


@pytest.mark.unit
async def test_missing_structured_output_raises_but_still_meters() -> None:
    clock = FakeMonotonicClock()
    no_output = LocalCompletion(
        parsed=None,
        raw_text="freeform prose, no JSON",
        usage=LLMUsage(input_tokens=1, output_tokens=1),
        model_id="llama-3.3-70b",
        stop_reason="stop",
    )
    backend = StubLocalBackend(clock, [StubCompletion(no_output, gpu_seconds=1.0)])
    measures: list[GpuUsageRecord] = []
    adapter = LocalLLM(backend=backend, monotonic_clock=clock, on_measure=measures.append)

    with pytest.raises(LLMSchemaValidationError):
        await adapter.chat(_request())

    # The meter is still closed and the GPU time still recorded: a failed
    # structured-output call consumed GPU time and must not leak a live call.
    assert len(measures) == 1
    assert measures[0].gpu_seconds == pytest.approx(1.0)


class _GatedBackend:
    """Backend whose completions block on a per-request event.

    Lets a test hold two `chat` calls open at once (both past `meter.open`,
    both awaiting) so their device time genuinely overlaps, then release
    them at controlled instants.
    """

    def __init__(self) -> None:
        self._gates: dict[str, asyncio.Event] = {}
        self._completions: dict[str, LocalCompletion] = {}

    def arm(self, key: str, completion: LocalCompletion) -> asyncio.Event:
        gate = asyncio.Event()
        self._gates[key] = gate
        self._completions[key] = completion
        return gate

    async def complete(self, request: LLMChatRequest) -> LocalCompletion:
        key = request.user_message.text
        await self._gates[key].wait()
        return self._completions[key]


@pytest.mark.unit
async def test_two_overlapping_calls_are_occupancy_shared() -> None:
    clock = FakeMonotonicClock()
    backend = _GatedBackend()
    measures: list[GpuUsageRecord] = []
    adapter = LocalLLM(
        backend=backend, monotonic_clock=clock, device_id="gpu0", on_measure=measures.append
    )

    gate_a = backend.arm("A", _ok_completion())
    gate_b = backend.arm("B", _ok_completion())

    # Both open on the same device at t=0, then park on their gates.
    task_a = asyncio.create_task(adapter.chat(_request(user_text="A")))
    task_b = asyncio.create_task(adapter.chat(_request(user_text="B")))
    await _settle()

    clock.advance(10.0)  # 10s elapse with A and B both live
    gate_a.set()
    await task_a  # A closes at t=10

    clock.advance(10.0)  # a further 10s with only B live
    gate_b.set()
    await task_b  # B closes at t=20

    seconds = sorted(m.gpu_seconds for m in measures)
    # A: [0,10] shared with B -> 5.0 ; B: [0,10] shared (5.0) + [10,20] solo (10.0) -> 15.0
    assert seconds == [pytest.approx(5.0), pytest.approx(15.0)]
    assert sum(seconds) == pytest.approx(20.0)  # == the device's busy wall-time
