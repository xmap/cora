"""Unit tests for the LocalLLM adapter and its GPU metering."""

# pyright: reportPrivateUsage=false, reportUnknownMemberType=false

import asyncio

import pytest

from cora.agent.adapters import local_llm
from cora.agent.adapters.local_llm import (
    GpuUsageRecord,
    LocalCompletion,
    LocalLLM,
    StubCompletion,
    StubLocalBackend,
)
from cora.infrastructure.observability import gen_ai
from cora.infrastructure.ports.clock import FakeMonotonicClock
from cora.infrastructure.ports.llm import (
    LLMChatRequest,
    LLMContentBlock,
    LLMInvalidRequestError,
    LLMSchemaValidationError,
    LLMSystemPrompt,
    LLMUsage,
    ModelRef,
)


def _request(
    user_text: str = "summarize the run",
    model: str = "llama-3.3-70b",
    provider: str = "local",
) -> LLMChatRequest:
    return LLMChatRequest(
        system=LLMSystemPrompt(blocks=(LLMContentBlock(text="you are a helper"),)),
        user_message=LLMContentBlock(text=user_text),
        structured_output_schema={"type": "object"},
        model_ref=ModelRef(provider=provider, model=model),
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


# ---------- Provider guard ----------


@pytest.mark.unit
async def test_chat_rejects_a_model_ref_priced_as_another_provider() -> None:
    """Mirrors AnthropicLLM's guard: a request declaring a different
    provider than this adapter serves must be refused before the
    backend, or GPU serving time, is ever touched."""
    clock = FakeMonotonicClock()
    backend = StubLocalBackend(clock, [StubCompletion(_ok_completion(), gpu_seconds=1.0)])
    measures: list[GpuUsageRecord] = []
    adapter = LocalLLM(backend=backend, monotonic_clock=clock, on_measure=measures.append)

    with pytest.raises(LLMInvalidRequestError) as excinfo:
        await adapter.chat(_request(provider="anthropic"))

    assert "anthropic" in str(excinfo.value)
    assert "local" in str(excinfo.value)
    assert measures == []


@pytest.mark.unit
async def test_chat_accepts_a_matching_provider() -> None:
    clock = FakeMonotonicClock()
    backend = StubLocalBackend(clock, [StubCompletion(_ok_completion(), gpu_seconds=1.0)])
    adapter = LocalLLM(backend=backend, monotonic_clock=clock)

    response = await adapter.chat(_request(provider="local"))

    assert response.parsed == {"summary": "ok"}


# ---------- GenAI telemetry ----------


class _SpyCounter:
    """Records every `add`, standing in for the OTel counter."""

    def __init__(self) -> None:
        self.adds: list[tuple[int, dict[str, str] | None]] = []

    def add(self, amount: int, attributes: dict[str, str] | None = None) -> None:
        self.adds.append((amount, attributes))


@pytest.mark.unit
async def test_solo_local_call_is_not_counted_as_concurrent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spy = _SpyCounter()
    monkeypatch.setattr(gen_ai, "_concurrent_call_counter", spy)
    clock = FakeMonotonicClock()
    backend = StubLocalBackend(clock, [StubCompletion(_ok_completion(), gpu_seconds=1.0)])
    adapter = LocalLLM(backend=backend, monotonic_clock=clock)

    await adapter.chat(_request())

    assert spy.adds == []
    assert gen_ai._in_flight_calls == 0


@pytest.mark.unit
async def test_two_overlapping_local_calls_register_as_concurrent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The batching GPU server is the one serving route most likely to run
    calls concurrently, so this is exactly the path the in-flight counter
    exists to watch."""
    spy = _SpyCounter()
    monkeypatch.setattr(gen_ai, "_concurrent_call_counter", spy)
    clock = FakeMonotonicClock()
    backend = _GatedBackend()
    adapter = LocalLLM(backend=backend, monotonic_clock=clock, device_id="gpu0")

    gate_a = backend.arm("A", _ok_completion())
    gate_b = backend.arm("B", _ok_completion())

    task_a = asyncio.create_task(adapter.chat(_request(user_text="A")))
    task_b = asyncio.create_task(adapter.chat(_request(user_text="B")))
    await _settle()

    gate_a.set()
    await task_a
    gate_b.set()
    await task_b

    assert [amount for amount, _ in spy.adds] == [1]
    assert gen_ai._in_flight_calls == 0


@pytest.mark.unit
async def test_chat_records_llm_call_telemetry_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[dict[str, object]] = []

    def _fake_record_llm_call(span: object, **kwargs: object) -> float:
        recorded.append(kwargs)
        return 0.0

    monkeypatch.setattr(local_llm, "record_llm_call", _fake_record_llm_call)
    clock = FakeMonotonicClock()
    backend = StubLocalBackend(clock, [StubCompletion(_ok_completion(), gpu_seconds=1.0)])
    adapter = LocalLLM(backend=backend, monotonic_clock=clock)

    await adapter.chat(_request(model="llama-3.3-70b"))

    assert len(recorded) == 1
    call = recorded[0]
    assert call["provider_name"] == "local"
    assert call["response_model_id"] == "llama-3.3-70b"
    assert call["stop_reason"] == "stop"
    assert call["max_tokens"] == 1024


@pytest.mark.unit
async def test_chat_does_not_record_llm_call_telemetry_on_schema_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[dict[str, object]] = []

    def _fake_record_llm_call(span: object, **kwargs: object) -> float:
        recorded.append(kwargs)
        return 0.0

    monkeypatch.setattr(local_llm, "record_llm_call", _fake_record_llm_call)
    clock = FakeMonotonicClock()
    no_output = LocalCompletion(
        parsed=None,
        raw_text="freeform prose, no JSON",
        usage=LLMUsage(input_tokens=1, output_tokens=1),
        model_id="llama-3.3-70b",
        stop_reason="stop",
    )
    backend = StubLocalBackend(clock, [StubCompletion(no_output, gpu_seconds=1.0)])
    adapter = LocalLLM(backend=backend, monotonic_clock=clock)

    with pytest.raises(LLMSchemaValidationError):
        await adapter.chat(_request())

    assert recorded == []
