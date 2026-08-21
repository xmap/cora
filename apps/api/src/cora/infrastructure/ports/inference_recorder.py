"""InferenceRecorder: best-effort capture of an agent's LLM-call provenance.

When an LLM-backed agent (RunDebriefer, CautionDrafter, the on-demand
regenerate-debrief slice) writes a Decision, the model identity, resolved
snapshot, and token usage that produced it are reproducibility-grade audit
data. The Decision BC already owns the home for them: the Inference logbook
(`cora.decision.aggregates.decision.Inference` + the `append_inferences`
slice), built to the OpenTelemetry `gen_ai.*` semantic conventions. A design
lock keeps those traces OFF the `DecisionRegistered` event and IN that logbook
(see `cora.decision.aggregates.decision.state` module docstring).

## Why a port

Two constraints make a direct call impossible from the producers:

  - Agent subscribers live in `cora.agent` and may not import a sibling BC's
    `features.*` (the cross-BC rule), so they cannot call the
    `append_inferences` handler directly.
  - The Decision BC's `InferenceStore` is deliberately BC-internal and is NOT
    on the `Kernel` (see `cora.infrastructure.kernel` docstring), so producers
    cannot reach the store either.

`InferenceRecorder` is the cross-BC capability port that bridges the gap: the
producer depends on this port (a `Kernel` field, mirroring `llm` / `authorize`
/ `logbook_mirror`), and the composition root (`cora.api`) wires a concrete
implementor that delegates to the `append_inferences` handler. The store stays
BC-internal; only a capability port crosses the boundary.

## Call shape

`record(trace, ...)` is fire-and-forget from the producer's perspective: the
Decision aggregate write is the audit-grade source of truth, and inference
capture is supplementary, so a recorder failure (including an authorization
denial under a real Trust policy) MUST NOT propagate to the producer's
Decision-emission path. Implementors handle their own error logging. The
`NullInferenceRecorder` default keeps unwired kernels and unit tests inert.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class AgentInferenceTrace:
    """Provenance for one LLM call an agent made while reaching a Decision.

    A neutral, provider-agnostic shape carrying only what an LLM producer
    legitimately knows, in OpenTelemetry `gen_ai.*` vocabulary. It deliberately
    omits the Inference envelope fields (logbook_id / correlation_id /
    causation_id) the recorder implementor populates, so producers never need
    to import the Decision BC's `features.*` command types.

    `event_id` is the producer-derived dedup key (a deterministic UUIDv5 so a
    subscriber retry re-records the same id and the store no-ops on conflict).
    `request_model` is what was sent (the agent's configured model); when the
    provider resolves a dated snapshot, `response_model` carries the exact
    model that answered (the load-bearing reproducibility field).

    `cost_usd` is the call's actual dollar cost, computed by the producer from
    usage tokens and pricing (`compute_cost_usd`), the same math behind the
    `cora.agent.llm.cost.usd` histogram. Persisting it here is what turns the
    ephemeral meter into a durable ledger fact a spend lookup can sum.

    `response_id` is the provider's own message id, taken from `LLMResponse`.
    `tool_call_id` / `tool_name` are likewise taken from `LLMResponse` and are
    `None` on any adapter that reaches structured output without tool-use.
    `tool_type` is derived by the producer from whether a tool mediated the
    call (`"function"` when `tool_call_id` is set, `None` otherwise), not a
    blind constant: a call served through direct JSON mode used no tool, and
    saying otherwise would misrepresent what happened. `output_type` is a
    producer-known constant (`"json"`): every call this DTO exists for asks
    for structured output, regardless of the mechanism. `duration` is
    milliseconds, measured by the producer around its own `LLM.chat()` call
    with a monotonic clock, because the producer owns the span, not the
    response.

    There is no `conversation_id` field, and that omission is deliberate, not
    an oversight: every producer here makes single-shot calls with no
    multi-turn conversation, so no value would be honest. Mirrors how
    `messages` is deliberately never populated (PII gating) rather than being
    a column nobody got around to.

    `cache_creation_input_tokens` / `cache_read_input_tokens` come straight off
    `LLMResponse.usage`, which already carries both (defaulting to 0 there for
    a provider that never reports cache stats). Here they stay `None` when the
    producer has no value, matching every other optional column on this row:
    `LLMUsage`'s 0-default is an in-memory convenience for arithmetic, not a
    claim that zero cache tokens were used.

    `gpu_seconds` comes straight off `LLMResponse.gpu_seconds`, populated
    only when the call was served by `LocalLLM`. In-house serving prices at
    $0/token by design, which is correct, but leaves nothing on the row
    showing the call was not free to run; this is that primitive. It is
    deliberately the raw seconds, not a dollar figure: the facility's
    GPU-hour rate is a configuration value that can change, and pricing at
    write time would make a historical row lie about what it cost when it
    ran. A reader recomputes shadow cost from this column when needed.
    """

    decision_id: UUID
    event_id: UUID
    occurred_at: datetime
    operation_name: str
    provider_name: str
    request_model: str
    response_id: str | None = None
    response_model: str | None = None
    finish_reasons: tuple[str, ...] = field(default_factory=tuple[str, ...])
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    cost_usd: float | None = None
    request_max_tokens: int | None = None
    request_temperature: float | None = None
    request_top_p: float | None = None
    agent_id: str | None = None
    agent_name: str | None = None
    output_type: str | None = None
    duration: int | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_type: str | None = None
    gpu_seconds: float | None = None


class InferenceRecorder(Protocol):
    """Records an agent's LLM-call provenance against a Decision.

    Single implementor per deployment, wired at the composition root. Producers
    call `record` AFTER the Decision append commits (the implementor's lazy
    logbook-open loads the Decision and would fail on a not-yet-written one).
    """

    async def record(
        self,
        trace: AgentInferenceTrace,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        """Persist one inference trace; best-effort, MUST NOT raise.

        `principal_id` is the agent's Actor id (the recorded author and the
        principal an authorization check runs against). Errors, including an
        authorization denial, are the implementor's responsibility to log; they
        must not propagate to the caller's Decision-emission path.
        """
        ...


class NullInferenceRecorder:
    """No-op recorder: the `Kernel` default when no implementor is wired.

    Keeps `app_env=test` kernels and the bulk of unit tests inert, exactly as
    they were before inference capture existed. The composition root replaces
    it with a delegating implementor once the Decision handlers are wired.
    """

    async def record(
        self,
        trace: AgentInferenceTrace,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        return None


__all__ = [
    "AgentInferenceTrace",
    "InferenceRecorder",
    "NullInferenceRecorder",
]
