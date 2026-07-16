"""Unit tests for the Inference entry + InferenceStore.

Mirrors `test_conduit_traversal_entries.py` shape from the prior
precedent: the dataclass round-trips, the in-memory store dedups
on event_id, batch and single-element appends both work, empty
list is a no-op.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.decision.aggregates.decision import (
    DECISION_REASONING_OPERATION_CHAT,
    DECISION_REASONING_OPERATION_CREATE_AGENT,
    DECISION_REASONING_OPERATION_EMBEDDINGS,
    DECISION_REASONING_OPERATION_EXECUTE_TOOL,
    DECISION_REASONING_OPERATION_INVOKE_AGENT,
    DECISION_REASONING_OPERATION_TEXT_COMPLETION,
    Inference,
    InMemoryInferenceStore,
)

_NOW = datetime(2026, 5, 12, 12, 0, 0, tzinfo=UTC)


def _row(**overrides: object) -> Inference:
    base: dict[str, object] = {
        "event_id": uuid4(),
        "decision_id": uuid4(),
        "logbook_id": uuid4(),
        "correlation_id": uuid4(),
        "causation_id": None,
        "occurred_at": _NOW,
        "duration": None,
        "operation_name": DECISION_REASONING_OPERATION_CHAT,
        "provider_name": "anthropic",
        "request_model": "claude-opus-4-7",
        "response_id": None,
        "response_model": None,
        "request_temperature": None,
        "request_top_p": None,
        "request_max_tokens": None,
        "output_type": None,
        "finish_reasons": (),
        "input_tokens": None,
        "output_tokens": None,
        "cost_usd": None,
        "agent_id": None,
        "agent_name": None,
        "agent_description": None,
        "conversation_id": None,
        "tool_name": None,
        "tool_call_id": None,
        "tool_type": None,
        "messages": None,
    }
    base.update(overrides)
    return Inference(**base)  # type: ignore[arg-type]


# ---------- Inference dataclass shape ----------


@pytest.mark.unit
def test_decision_reasoning_required_discriminator_fields() -> None:
    """provider_name + operation_name + request_model are
    NOT NULL discriminators per the OTel gen_ai.* survey."""
    row = _row()
    assert row.provider_name == "anthropic"
    assert row.operation_name == DECISION_REASONING_OPERATION_CHAT
    assert row.request_model == "claude-opus-4-7"


@pytest.mark.unit
def test_decision_reasoning_optional_fields_default_none() -> None:
    row = _row()
    assert row.response_id is None
    assert row.response_model is None
    assert row.input_tokens is None
    assert row.output_tokens is None
    assert row.tool_name is None
    assert row.agent_id is None
    assert row.messages is None


@pytest.mark.unit
def test_decision_reasoning_finish_reasons_default_empty_tuple() -> None:
    """OTel finish_reasons is a string array (multiple stops
    possible in one call); default is empty tuple, not None."""
    assert _row().finish_reasons == ()


@pytest.mark.unit
def test_decision_reasoning_with_tool_call_fields() -> None:
    """tool_name / tool_call_id / tool_type populated only for
    `execute_tool` operations per OTel convention."""
    row = _row(
        operation_name=DECISION_REASONING_OPERATION_EXECUTE_TOOL,
        tool_name="get_dataset",
        tool_call_id="toolu_abc123",
        tool_type="Function",
    )
    assert row.operation_name == DECISION_REASONING_OPERATION_EXECUTE_TOOL
    assert row.tool_name == "get_dataset"
    assert row.tool_call_id == "toolu_abc123"
    assert row.tool_type == "Function"


@pytest.mark.unit
def test_decision_reasoning_with_agent_fields() -> None:
    """agent_id / agent_name populate for invoke_agent ops + carry
    OTel multi-agent correlation."""
    row = _row(
        operation_name=DECISION_REASONING_OPERATION_INVOKE_AGENT,
        agent_id="agent-7e",
        agent_name="ApprovalAgent",
        agent_description="Reviews recipe-approval decisions",
        conversation_id="conv-abc",
    )
    assert row.agent_id == "agent-7e"
    assert row.conversation_id == "conv-abc"


@pytest.mark.unit
def test_decision_reasoning_op_constants_locked_to_otel_semconv_values() -> None:
    """Lock the OTel gen_ai.operation.name string values against
    drift; downstream consumers (Datadog / Langfuse / Phoenix) read
    them by string match."""
    assert DECISION_REASONING_OPERATION_CHAT == "chat"
    assert DECISION_REASONING_OPERATION_TEXT_COMPLETION == "text_completion"
    assert DECISION_REASONING_OPERATION_EMBEDDINGS == "embeddings"
    assert DECISION_REASONING_OPERATION_EXECUTE_TOOL == "execute_tool"
    assert DECISION_REASONING_OPERATION_INVOKE_AGENT == "invoke_agent"
    assert DECISION_REASONING_OPERATION_CREATE_AGENT == "create_agent"


@pytest.mark.unit
@pytest.mark.parametrize(
    "operation",
    [
        DECISION_REASONING_OPERATION_TEXT_COMPLETION,
        DECISION_REASONING_OPERATION_EMBEDDINGS,
        DECISION_REASONING_OPERATION_CREATE_AGENT,
    ],
)
def test_decision_reasoning_accepts_remaining_well_known_op_values(operation: str) -> None:
    """Round out coverage for the three op constants not exercised
    by the chat / execute_tool / invoke_agent path tests above. The
    BC accepts any open-string value; well-known constants are a
    discoverability surface."""
    row = _row(operation_name=operation)
    assert row.operation_name == operation


@pytest.mark.unit
def test_decision_reasoning_messages_for_pii_gated_payloads() -> None:
    """Message bodies (prompt + completion) live in messages;
    typed columns hold the high-signal attributes only."""
    row = _row(
        messages={
            "prompt": [{"role": "user", "content": "Approve this recipe?"}],
            "completion": [{"role": "assistant", "content": "Approved."}],
        }
    )
    assert row.messages is not None
    assert "prompt" in row.messages


# ---------- InMemoryInferenceStore ----------


@pytest.mark.unit
async def test_in_memory_store_appends_single_row() -> None:
    store = InMemoryInferenceStore()
    row = _row()
    await store.append([row])
    assert store.all() == [row]


@pytest.mark.unit
async def test_in_memory_store_appends_batch() -> None:
    """Producers commonly batch; multi-row append works."""
    store = InMemoryInferenceStore()
    rows = [_row(), _row(), _row()]
    await store.append(rows)
    assert len(store.all()) == 3


@pytest.mark.unit
async def test_in_memory_store_empty_list_is_noop() -> None:
    store = InMemoryInferenceStore()
    await store.append([])
    assert store.all() == []


@pytest.mark.unit
async def test_in_memory_store_dedups_on_event_id() -> None:
    """At-least-once semantics: retrying with the same event_id
    must not produce two stored rows. First write wins (matches
    Postgres ON CONFLICT (event_id) DO NOTHING shape)."""
    store = InMemoryInferenceStore()
    event_id = uuid4()
    first = _row(event_id=event_id, request_model="claude-opus-4-7")
    second = _row(event_id=event_id, request_model="claude-sonnet-4-6")
    await store.append([first])
    await store.append([second])
    assert store.all() == [first]
    assert store.all()[0].request_model == "claude-opus-4-7"


@pytest.mark.unit
async def test_in_memory_store_preserves_insertion_order_across_calls() -> None:
    """all() returns rows in insertion order for predictable test
    assertions."""
    store = InMemoryInferenceStore()
    a = _row()
    b = _row()
    c = _row()
    await store.append([a])
    await store.append([b, c])
    assert store.all() == [a, b, c]
