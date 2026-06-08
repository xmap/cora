"""DecisionReasoning entry: per-AI-trace observation row.

The Decision BC's first concrete entry type. Mirrors the Conduit
BC's `ConduitTraversal` precedent and the per-category writer
pattern locked there.

Each entry captures one OpenTelemetry GenAI semantic-convention
event: an LLM call, a tool invocation, or an agent span. The
field set is taken directly from OTel `gen_ai.*` semconv v1.38
(2026), so traces are interoperable with Datadog / Langfuse /
Phoenix / OpenInference downstream tooling without translation.

## Why this lives here, not in `cora.infrastructure.postgres`

The dataclass + Protocol describe Decision BC's domain shape
(operation_name / provider_name / agent_id are domain vocabulary,
not infrastructure primitives). The Postgres adapter that knows
the SQL also lives here because the SQL knows the column shape;
splitting them across infra and domain modules would require
either a generic SQL builder or duplicate column lists. Same
trade-off `events.py` per-aggregate modules made.

## Why writes batch from day one

`append(rows: list[DecisionReasoning])` always takes a list. AI
producers commonly batch (a whole conversation turn arrives as
multiple events at once); single-element lists work for the
"one trace at a time" case. Locked at gate-review G4 for the
entry-store pattern. Empty lists are a no-op.

## Why `messages` is the only jsonb column

OTel itself models prompt / completion message bodies as a
separate **event** payload (gated for PII), not span attributes.
Following that split: typed columns hold the high-signal
attributes (one row = one client/agent span); a single optional
`messages` carries the variable-shape message-body
payload when the producer opts in (PII / large prompts are
opt-in, not always-on).

## Why no read shape today

The `range` query for retrieval lands when a real consumer asks
for it (gate-review G2 deferral). Today the table is write-only
from the application's perspective; ad-hoc SQL covers any
operator queries.

## Survey-locked field set (OTel gen_ai.* semconv v1.38, Dec 2026)

  - `provider_name` and `operation_name` are NOT NULL (together
    discriminate row shape: chat vs execute_tool vs invoke_agent).
  - `gen_ai.system` is **deprecated**; we use `provider_name`
    (mapped from `gen_ai.provider.name`).
  - `prompt_tokens` / `completion_tokens` are **deprecated**;
    we use `input_tokens` / `output_tokens`.
  - `gen_ai.prompt` / `gen_ai.completion` span attrs are
    **deprecated**; message bodies go in `messages`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID

import asyncpg

from cora.shared.logbook import LogbookFieldSpec, LogbookSchema

# OTel gen_ai.tool.type enum (Stable values per v1.38 semconv).
# Open string at the storage layer so future OTel additions don't
# require a schema bump; well-known values documented here.
DecisionReasoningToolType = Literal["Extension", "Function", "Datastore"]

# OTel gen_ai.operation.name well-known values per v1.38. Open
# string at the storage layer; new operation names from future OTel
# spec versions arrive without schema changes.
DECISION_REASONING_OPERATION_CHAT = "chat"
DECISION_REASONING_OPERATION_TEXT_COMPLETION = "text_completion"
DECISION_REASONING_OPERATION_EMBEDDINGS = "embeddings"
DECISION_REASONING_OPERATION_EXECUTE_TOOL = "execute_tool"
DECISION_REASONING_OPERATION_INVOKE_AGENT = "invoke_agent"
DECISION_REASONING_OPERATION_CREATE_AGENT = "create_agent"


@dataclass(frozen=True)
class DecisionReasoning:
    """One row in the per-Decision AI-reasoning audit logbook.

    Captures one OTel GenAI client/agent span (or one tool call) plus
    optional message-body event payload. Required fields are the
    discriminator pair (provider_name + operation_name) plus the
    invocation context (request_model). Optional fields cover the
    response, usage, agent context, and tool-call context.

    `event_id` is the producer-assigned UUIDv7 identity (matches
    cross-BC convention; UNIQUE at the table level for at-least-once
    dedup). `correlation_id` and `causation_id` thread through from
    the originating command's envelope for full audit traceability
    (gate-review G7 lock).
    """

    # --- CORA infra (entry envelope) ---
    event_id: UUID
    decision_id: UUID
    logbook_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    occurred_at: datetime
    duration: int | None
    # --- OTel gen_ai.* required discriminators ---
    operation_name: str  # gen_ai.operation.name
    provider_name: str  # gen_ai.provider.name (NOT deprecated gen_ai.system)
    request_model: str  # gen_ai.request.model
    # --- OTel gen_ai.* response identity / hyperparameters ---
    response_id: str | None  # gen_ai.response.id
    response_model: str | None  # gen_ai.response.model (may differ from requested)
    request_temperature: float | None  # gen_ai.request.temperature
    request_top_p: float | None  # gen_ai.request.top_p
    request_max_tokens: int | None  # gen_ai.request.max_tokens
    output_type: str | None  # gen_ai.output.type (modality of response)
    finish_reasons: tuple[str, ...]  # gen_ai.response.finish_reasons (multi)
    # --- OTel gen_ai.* token usage (NOT deprecated prompt/completion_tokens) ---
    input_tokens: int | None  # gen_ai.usage.input_tokens
    output_tokens: int | None  # gen_ai.usage.output_tokens
    # --- OTel gen_ai.* agent context ---
    agent_id: str | None  # gen_ai.agent.id
    agent_name: str | None  # gen_ai.agent.name
    agent_description: str | None  # gen_ai.agent.description
    conversation_id: str | None  # gen_ai.conversation.id
    # --- OTel gen_ai.* tool-call context (only for execute_tool ops) ---
    tool_name: str | None  # gen_ai.tool.name
    tool_call_id: str | None  # gen_ai.tool.call.id
    tool_type: str | None  # gen_ai.tool.type
    # --- OTel event payload (PII-gated; opt-in by producer) ---
    messages: dict[str, Any] | None


# Schema declared on DecisionLogbookOpened payloads when a
# reasoning logbook is opened. Documentation-grade per the 6f-5a
# pattern (schema lives on the open event so projections read it
# uniformly without per-BC adapters).
REASONING_LOGBOOK_SCHEMA: LogbookSchema = LogbookSchema(
    fields={
        "operation_name": LogbookFieldSpec(
            type="string",
            description="OTel gen_ai.operation.name (chat / execute_tool / invoke_agent / etc.)",
        ),
        "provider_name": LogbookFieldSpec(
            type="string",
            description="OTel gen_ai.provider.name (replaces deprecated gen_ai.system)",
        ),
        "request_model": LogbookFieldSpec(type="string", description="OTel gen_ai.request.model"),
        "response_model": LogbookFieldSpec(
            type="string", description="OTel gen_ai.response.model (may differ)"
        ),
        "response_id": LogbookFieldSpec(type="string", description="OTel gen_ai.response.id"),
        "request_temperature": LogbookFieldSpec(
            type="float", description="OTel gen_ai.request.temperature"
        ),
        "request_top_p": LogbookFieldSpec(type="float", description="OTel gen_ai.request.top_p"),
        "request_max_tokens": LogbookFieldSpec(
            type="int", description="OTel gen_ai.request.max_tokens"
        ),
        "output_type": LogbookFieldSpec(type="string", description="OTel gen_ai.output.type"),
        "input_tokens": LogbookFieldSpec(type="int", description="OTel gen_ai.usage.input_tokens"),
        "output_tokens": LogbookFieldSpec(
            type="int", description="OTel gen_ai.usage.output_tokens"
        ),
        "agent_id": LogbookFieldSpec(type="string", description="OTel gen_ai.agent.id"),
        "agent_name": LogbookFieldSpec(type="string", description="OTel gen_ai.agent.name"),
        "agent_description": LogbookFieldSpec(
            type="string", description="OTel gen_ai.agent.description"
        ),
        "conversation_id": LogbookFieldSpec(
            type="string", description="OTel gen_ai.conversation.id"
        ),
        "tool_name": LogbookFieldSpec(type="string", description="OTel gen_ai.tool.name"),
        "tool_call_id": LogbookFieldSpec(type="string", description="OTel gen_ai.tool.call.id"),
        "tool_type": LogbookFieldSpec(
            type="string",
            description="OTel gen_ai.tool.type (Extension / Function / Datastore)",
        ),
        "duration": LogbookFieldSpec(
            type="int", units="ms", description="span end_time - start_time"
        ),
    },
    description=(
        "AI-decider reasoning trace per OpenTelemetry GenAI semantic conventions "
        "v1.38 (gen_ai.* attribute family). One entry = one LLM client span / "
        "agent span / tool invocation. Message bodies (prompt + completion) are "
        "gated to an optional messages event-payload column for PII control."
    ),
)


class ReasoningStore(Protocol):
    """Per-category port for DecisionReasoning entry writes.

    Mirrors `TraversalStore` from the Conduit BC's entries
    module. Two implementations: `PostgresReasoningStore`
    (production) and `InMemoryReasoningStore`
    (tests / `app_env=test`). Both honor at-least-once: callers
    may retry the same `event_id`, the store dedups via the
    table's PK constraint (Postgres) or the in-memory dict
    (InMemory).
    """

    async def append(self, rows: list[DecisionReasoning]) -> None:
        """Persist reasoning entries; empty list is a no-op."""
        ...


_APPEND_SQL = """
INSERT INTO entries_decision_reasonings (
    event_id, decision_id, logbook_id, correlation_id, causation_id,
    occurred_at, duration,
    operation_name, provider_name, request_model,
    response_id, response_model,
    request_temperature, request_top_p, request_max_tokens,
    output_type, finish_reasons,
    input_tokens, output_tokens,
    agent_id, agent_name, agent_description, conversation_id,
    tool_name, tool_call_id, tool_type,
    messages
) VALUES (
    $1, $2, $3, $4, $5,
    $6, $7,
    $8, $9, $10,
    $11, $12,
    $13, $14, $15,
    $16, $17,
    $18, $19,
    $20, $21, $22, $23,
    $24, $25, $26,
    $27
)
ON CONFLICT (event_id) DO NOTHING
"""


class PostgresReasoningStore:
    """asyncpg-backed `ReasoningStore` implementation.

    Uses `ON CONFLICT (event_id) DO NOTHING` for idempotent retries:
    a producer that re-issues the same `event_id` (after a transient
    network failure) is a silent no-op rather than a constraint
    violation. Mirrors `PostgresTraversalStore` exactly.

    Uses `executemany` for batch insert (one statement per entry,
    client-side loop). For MVP-scale batches (up to 100 entries
    per the route's cap) this is fine; if p95 ingest latency
    degrades on large batches, refactor to a single multi-row
    `INSERT ... VALUES (...), (...)` statement.
    Deferred-with-trigger.

    `messages` is pre-encoded to a JSON string via
    `json.dumps(...)` rather than relying on asyncpg's auto
    dict -> jsonb codec. Defensive: asyncpg's codec registration
    varies across versions; explicit pre-encoding is version-
    independent and matches the rest of the codebase's "explicit
    serialization" posture.

    Per-entry status (newly inserted vs deduped) is NOT returned
    today; the slice ships 200 OK with a summary count. Per-entry
    status is deferred-with-trigger (first consumer demanding the
    distinction).
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append(self, rows: list[DecisionReasoning]) -> None:
        if not rows:  # pragma: no cover  # callers pre-filter empty batches; defensive early-out
            return
        # asyncpg encodes Python list -> Postgres array natively;
        # finish_reasons is text[] (matches the column type).
        # messages gets json.dumps()-encoded by the connection
        # via a registered codec or by passing as JSON-encoded string.
        # We pre-encode to be explicit and avoid asyncpg-version drift.
        import json

        async with self._pool.acquire() as conn:
            await conn.executemany(
                _APPEND_SQL,
                [
                    (
                        row.event_id,
                        row.decision_id,
                        row.logbook_id,
                        row.correlation_id,
                        row.causation_id,
                        row.occurred_at,
                        row.duration,
                        row.operation_name,
                        row.provider_name,
                        row.request_model,
                        row.response_id,
                        row.response_model,
                        row.request_temperature,
                        row.request_top_p,
                        row.request_max_tokens,
                        row.output_type,
                        list(row.finish_reasons),
                        row.input_tokens,
                        row.output_tokens,
                        row.agent_id,
                        row.agent_name,
                        row.agent_description,
                        row.conversation_id,
                        row.tool_name,
                        row.tool_call_id,
                        row.tool_type,
                        json.dumps(row.messages) if row.messages is not None else None,
                    )
                    for row in rows
                ],
            )


class InMemoryReasoningStore:
    """Test / `app_env=test` adapter for ReasoningStore.

    Dict-keyed by `event_id` for at-least-once dedup. Provides an
    `all()` accessor for tests inspecting written rows. Mirrors
    `InMemoryTraversalStore` (plain class with explicit __init__,
    not dataclass; matches the per-category writer pattern locked
    at gate-review L8).
    """

    def __init__(self) -> None:
        self._rows: dict[UUID, DecisionReasoning] = {}

    async def append(self, rows: list[DecisionReasoning]) -> None:
        for row in rows:
            self._rows.setdefault(row.event_id, row)

    def all(self) -> list[DecisionReasoning]:
        """Return every stored row in insertion order (test helper)."""
        return list(self._rows.values())


__all__ = [
    "DECISION_REASONING_OPERATION_CHAT",
    "DECISION_REASONING_OPERATION_CREATE_AGENT",
    "DECISION_REASONING_OPERATION_EMBEDDINGS",
    "DECISION_REASONING_OPERATION_EXECUTE_TOOL",
    "DECISION_REASONING_OPERATION_INVOKE_AGENT",
    "DECISION_REASONING_OPERATION_TEXT_COMPLETION",
    "REASONING_LOGBOOK_SCHEMA",
    "DecisionReasoning",
    "DecisionReasoningToolType",
    "InMemoryReasoningStore",
    "PostgresReasoningStore",
    "ReasoningStore",
]
