"""The `AppendInferences` command, intent dataclass for this slice.

Batch shape from day one (per gate-review L3 + the 8c-b standards
survey: Langfuse / Phoenix / Datadog / OTLP all batch). Length-1
batches are the degenerate case; same code path either way.

Producer-supplied event_id (UUIDv7) per entry; store dedups via
Postgres PK (`ON CONFLICT (event_id) DO NOTHING`). At-least-once
semantics for free.

## Lazy open-on-first-write

The handler loads the parent Decision, checks for an existing
`reasoning` logbook on `Decision.logbooks`, and emits a
`DecisionLogbookOpened` event if none exists before appending the
batch. `register_decision` stays unchanged, the logbook
attaches lazily when the first reasoning entry arrives. Per
gate-review L1.

## Field shape per entry

Each `ReasoningEntryInput` carries the OpenTelemetry GenAI
semconv v1.38 field set (provider_name + operation_name +
request_model required; rest optional). `messages` is the
opt-in PII-gated payload. Producer-side responsibility for
JSON-roundtrippability of `messages` values; the BC accepts
it as opaque dict.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ReasoningEntryInput:
    """One reasoning entry's input payload from the producer.

    Mirrors `Inference` but omits the CORA-infra fields
    (decision_id / logbook_id / correlation_id / causation_id)
    those are populated by the handler from the URL path + envelope.
    """

    event_id: UUID
    occurred_at: datetime
    operation_name: str
    provider_name: str
    request_model: str
    duration: int | None = None
    response_id: str | None = None
    response_model: str | None = None
    request_temperature: float | None = None
    request_top_p: float | None = None
    request_max_tokens: int | None = None
    output_type: str | None = None
    finish_reasons: tuple[str, ...] = field(default_factory=tuple[str, ...])
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    agent_id: str | None = None
    agent_name: str | None = None
    agent_description: str | None = None
    conversation_id: str | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None
    tool_type: str | None = None
    messages: dict[str, Any] | None = None


@dataclass(frozen=True)
class AppendInferences:
    """Append a batch of reasoning entries to a Decision's logbook."""

    decision_id: UUID
    entries: tuple[ReasoningEntryInput, ...]
