"""Local (facility-hosted) implementation of `LLM`.

Serves an open model over an OpenAI-compatible endpoint (vLLM, Ollama,
llama.cpp) as the paper's "build" path, and meters the GPU time each
call consumes so a facility has visibility into shadow cost and
capacity. Lives under `cora.agent.adapters` per the cross-BC
adapter-ownership convention, beside `AnthropicLLM`, and fills the
local-model slot the `LLM` port anticipates.

## Instrument first, model later

The adapter talks to a `LocalCompletionBackend`, not directly to an
engine, so the serving-and-metering seam is built and tested against a
deterministic `StubLocalBackend` before a real engine is wired in, which
the design deliberately sequences last. Any OpenAI-compatible engine
becomes one more backend; the adapter and its meter integration do not
change.

## Metering

Every `chat` opens the shared `OccupancyShareMeter` on the call's device
before the backend runs and closes it after, so concurrent calls sharing
one GPU are attributed their occupancy share, not their full wall-clock
each (see `cora.infrastructure.observability.gpu_accounting`). The
measured GPU-seconds are handed to an optional `on_measure` sink for
observability; they never touch the budget gate. In the locked design
in-house serving is metered-free by default, so this is visibility, not
a debit. Elapsed time is read from an injected `MonotonicClock`, never
wall-clock, so a duration is never corrupted by an NTP correction and
tests reproduce exactly.

## Structured output

Consumers require a schema-valid `parsed` Decision. A capable local
server produces it via guided decoding / JSON-schema mode; the backend
returns `parsed=None` when it could not, and the adapter raises
`LLMSchemaValidationError` (the outer retry layer then defers), the same
contract `AnthropicLLM` presents from forced tool-use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from cora.infrastructure.observability.gpu_accounting import OccupancyShareMeter
from cora.infrastructure.ports.llm import (
    LLMResponse,
    LLMSchemaValidationError,
    LLMServerError,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from typing import Any

    from cora.infrastructure.ports.clock import FakeMonotonicClock, MonotonicClock
    from cora.infrastructure.ports.llm import LLMChatRequest, LLMUsage


@dataclass(frozen=True)
class LocalCompletion:
    """One backend result the adapter maps onto `LLMResponse`.

    `parsed` is the schema-valid structured Decision, or `None` when the
    server could not produce one (the adapter then raises
    `LLMSchemaValidationError`). `usage` reports the token counts the
    server returned; open models report input and output tokens, and the
    cache fields default to 0.
    """

    parsed: Mapping[str, Any] | None
    raw_text: str
    usage: LLMUsage
    model_id: str
    stop_reason: str


class LocalCompletionBackend(Protocol):
    """The serving engine behind `LocalLLM`: a stub, or a real client."""

    async def complete(self, request: LLMChatRequest) -> LocalCompletion: ...


@dataclass(frozen=True)
class GpuUsageRecord:
    """One call's measured GPU occupancy, for the observability sink.

    `gpu_seconds` is the call's occupancy share of its device, not its
    full wall-clock when it ran alongside others. It is visibility only
    and never debits the budget.
    """

    call_id: str
    device_id: str
    model: str
    gpu_seconds: float


class LocalLLM:
    """`LLM` adapter for a facility-hosted open model, with GPU metering.

    Holds one `OccupancyShareMeter` shared across concurrent `chat` calls
    so their overlapping device time is divided honestly. `device_id`
    names the served model's device (one model on one device for now;
    multi-device assignment is a later slice). `on_measure`, if given,
    receives each call's `GpuUsageRecord` for observability.
    """

    def __init__(
        self,
        *,
        backend: LocalCompletionBackend,
        monotonic_clock: MonotonicClock,
        meter: OccupancyShareMeter | None = None,
        device_id: str = "gpu0",
        on_measure: Callable[[GpuUsageRecord], None] | None = None,
    ) -> None:
        self._backend = backend
        self._clock = monotonic_clock
        self._meter = meter if meter is not None else OccupancyShareMeter()
        self._device_id = device_id
        self._on_measure = on_measure
        self._call_seq = 0

    async def chat(self, request: LLMChatRequest) -> LLMResponse:
        self._call_seq += 1
        call_id = f"local-{self._call_seq}"
        model = request.model_ref.model
        self._meter.open(call_id, device_id=self._device_id, at_s=self._clock.now())
        try:
            completion = await self._backend.complete(request)
            if completion.parsed is None:
                msg = (
                    f"local server returned no schema-valid structured output "
                    f"for model {model!r}"
                )
                raise LLMSchemaValidationError(msg)
            return LLMResponse(
                parsed=completion.parsed,
                raw_text=completion.raw_text,
                usage=completion.usage,
                stop_reason=completion.stop_reason,
                model_id=completion.model_id,
            )
        finally:
            gpu_seconds = self._meter.close(call_id, at_s=self._clock.now())
            if self._on_measure is not None:
                self._on_measure(
                    GpuUsageRecord(
                        call_id=call_id,
                        device_id=self._device_id,
                        model=model,
                        gpu_seconds=gpu_seconds,
                    )
                )


@dataclass(frozen=True)
class StubCompletion:
    """One canned backend result plus the GPU time it should consume."""

    completion: LocalCompletion
    gpu_seconds: float


class StubLocalBackend:
    """Deterministic backend: canned completions that consume set GPU time.

    Each `complete` pops the next `StubCompletion` and advances the
    injected `FakeMonotonicClock` by its `gpu_seconds`, so a solo call is
    measured at exactly that duration. It lets the whole serving path run
    without a real GPU (the instrument-first slice). Overlapping-call
    concurrency is exercised with a gated backend in tests, not here.
    """

    def __init__(
        self, clock: FakeMonotonicClock, completions: list[StubCompletion]
    ) -> None:
        self._clock = clock
        self._queue = list(completions)

    async def complete(self, request: LLMChatRequest) -> LocalCompletion:
        if not self._queue:
            msg = "StubLocalBackend queue exhausted; enqueue more completions"
            raise LLMServerError(msg)
        head = self._queue.pop(0)
        self._clock.advance(head.gpu_seconds)
        return head.completion


__all__ = [
    "GpuUsageRecord",
    "LocalCompletion",
    "LocalCompletionBackend",
    "LocalLLM",
    "StubCompletion",
    "StubLocalBackend",
]
