"""End-to-end integration test: append_reasoning_entries against real Postgres.

8c-b's first concrete user of the entries_decision_reasonings
table + PostgresReasoningStore. Stress-tests the full lazy
open-on-first-write + batch-append + jsonb round-trip path
against actual Postgres jsonb / text[] / nullable column semantics.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.access.features.register_actor import RegisterActor
from cora.access.features.register_actor import bind as bind_register_actor
from cora.decision.aggregates.decision import (
    DECISION_REASONING_OPERATION_CHAT,
    DECISION_REASONING_OPERATION_EXECUTE_TOOL,
    LOGBOOK_KIND_REASONING,
    PostgresReasoningStore,
    load_decision,
)
from cora.decision.features.append_reasoning_entries import (
    AppendReasoningEntries,
    ReasoningEntryInput,
)
from cora.decision.features.append_reasoning_entries import (
    bind as bind_append,
)
from cora.decision.features.register_decision import RegisterDecision
from cora.decision.features.register_decision import bind as bind_register_decision
from cora.infrastructure.kernel import Kernel
from cora.shared.identity import ActorId
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store

_NOW = datetime(2026, 5, 12, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _read_entries_for_decision(
    db_pool: asyncpg.Pool, decision_id: UUID
) -> list[asyncpg.Record]:
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT
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
            FROM entries_decision_reasonings
            WHERE decision_id = $1
            ORDER BY occurred_at, event_id
            """,
            decision_id,
        )


@pytest.mark.integration
async def test_append_reasoning_entries_full_lazy_open_and_jsonb_round_trip(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end: register Actor + Decision, then append a 2-entry
    batch. Verify lazy DecisionLogbookOpened landed on the Decision
    stream, both rows landed in entries_decision_reasonings with
    typed columns + jsonb intact, and a follow-up append on the
    same Decision skips the open + appends to the same logbook."""
    actor_id = ActorId(UUID("01900000-0000-7000-8000-000000088a01"))
    actor_event_id = UUID("01900000-0000-7000-8000-000000088a02")
    decision_id = UUID("01900000-0000-7000-8000-000000088b01")
    decision_event_id = UUID("01900000-0000-7000-8000-000000088b02")
    logbook_id = UUID("01900000-0000-7000-8000-000000088b03")
    open_event_id = UUID("01900000-0000-7000-8000-000000088b04")
    entry_a_id = UUID("01900000-0000-7000-8000-000000088c01")
    entry_b_id = UUID("01900000-0000-7000-8000-000000088c02")

    deps = _build_deps(
        db_pool,
        [
            actor_id,
            actor_event_id,
            decision_id,
            decision_event_id,
            logbook_id,
            open_event_id,
        ],
    )
    reasoning_store = PostgresReasoningStore(db_pool)

    # Seed Actor.
    await bind_register_actor(deps, profile_store=make_pg_profile_store(db_pool))(
        RegisterActor(name="AI Reviewer"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Seed Decision.
    returned_decision_id = await bind_register_decision(deps)(
        RegisterDecision(
            decided_by=actor_id,
            context="RecipeApproval",
            choice="Approved",
            parent_id=None,
            override_kind=None,
            rule=None,
            reasoning=None,
            confidence=0.92,
            confidence_source=None,
            alternatives=(),
            inputs=None,
            reasoning_signature=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_decision_id == decision_id

    # First append: lazy open emits DecisionLogbookOpened + 2 entries land.
    entry_a = ReasoningEntryInput(
        event_id=entry_a_id,
        occurred_at=_NOW,
        operation_name=DECISION_REASONING_OPERATION_CHAT,
        provider_name="anthropic",
        request_model="claude-opus-4-7",
        duration=1234,
        response_id="msg_abc",
        response_model="claude-opus-4-7",
        request_temperature=0.7,
        request_top_p=0.95,
        request_max_tokens=4096,
        output_type="text",
        finish_reasons=("end_turn",),
        input_tokens=512,
        output_tokens=256,
        agent_id="agent-7e",
        agent_name="ApprovalAgent",
        conversation_id="conv-abc",
        messages={
            "prompt": [{"role": "user", "content": "Approve this recipe?"}],
            "completion": [{"role": "assistant", "content": "Approved."}],
        },
    )
    entry_b = ReasoningEntryInput(
        event_id=entry_b_id,
        occurred_at=_NOW,
        operation_name=DECISION_REASONING_OPERATION_EXECUTE_TOOL,
        provider_name="anthropic",
        request_model="claude-opus-4-7",
        tool_name="get_dataset",
        tool_call_id="toolu_xyz",
        tool_type="Function",
    )
    count = await bind_append(deps, reasoning_store=reasoning_store)(
        AppendReasoningEntries(decision_id=decision_id, entries=(entry_a, entry_b)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 2

    # Verify Decision stream now carries DecisionLogbookOpened.
    state = await load_decision(deps.event_store, decision_id)
    assert state is not None
    assert state.logbooks == {LOGBOOK_KIND_REASONING: logbook_id}

    # Read rows from entries_decision_reasonings.
    rows = await _read_entries_for_decision(db_pool, decision_id)
    assert len(rows) == 2

    row_a = next(r for r in rows if r["event_id"] == entry_a_id)
    row_b = next(r for r in rows if r["event_id"] == entry_b_id)

    # Typed columns survived jsonb-free round-trip.
    assert row_a["decision_id"] == decision_id
    assert row_a["logbook_id"] == logbook_id
    assert row_a["correlation_id"] == _CORRELATION_ID
    assert row_a["operation_name"] == "chat"
    assert row_a["provider_name"] == "anthropic"
    assert row_a["request_model"] == "claude-opus-4-7"
    assert row_a["request_temperature"] == 0.7
    assert row_a["input_tokens"] == 512
    assert row_a["output_tokens"] == 256
    assert row_a["finish_reasons"] == ["end_turn"]
    assert row_a["agent_name"] == "ApprovalAgent"
    assert row_a["conversation_id"] == "conv-abc"

    # messages came back as a parsed dict (asyncpg jsonb codec).
    # The store JSON-encodes on write; Postgres returns the structured value
    # OR a string depending on registered codec, accept either.
    msg_payload = row_a["messages"]
    if isinstance(msg_payload, str):
        import json

        msg_payload = json.loads(msg_payload)
    assert "prompt" in msg_payload
    assert msg_payload["prompt"][0]["role"] == "user"

    # Tool entry has the tool_* fields populated, others null.
    assert row_b["operation_name"] == "execute_tool"
    assert row_b["tool_name"] == "get_dataset"
    assert row_b["tool_call_id"] == "toolu_xyz"
    assert row_b["tool_type"] == "Function"
    assert row_b["request_temperature"] is None
    assert row_b["input_tokens"] is None

    # Second append on the same Decision skips the open (logbook already
    # open) and adds entries to the same logbook.
    deps_second = _build_deps(
        db_pool,
        [
            UUID("01900000-0000-7000-8000-000000088d01"),  # unused id-gen pulls
        ],
    )
    entry_c_id = UUID("01900000-0000-7000-8000-000000088c03")
    entry_c = ReasoningEntryInput(
        event_id=entry_c_id,
        occurred_at=_NOW,
        operation_name=DECISION_REASONING_OPERATION_CHAT,
        provider_name="anthropic",
        request_model="claude-opus-4-7",
    )
    await bind_append(deps_second, reasoning_store=reasoning_store)(
        AppendReasoningEntries(decision_id=decision_id, entries=(entry_c,)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Decision stream still has DecisionRegistered + ONE
    # DecisionLogbookOpened (no second open emitted).
    state_after = await load_decision(deps_second.event_store, decision_id)
    assert state_after is not None
    assert state_after.logbooks == {LOGBOOK_KIND_REASONING: logbook_id}

    rows_after = await _read_entries_for_decision(db_pool, decision_id)
    assert len(rows_after) == 3
    # The new entry joined the same logbook.
    new_row = next(r for r in rows_after if r["event_id"] == entry_c_id)
    assert new_row["logbook_id"] == logbook_id


@pytest.mark.integration
async def test_postgres_reasoning_store_dedups_on_event_id(
    db_pool: asyncpg.Pool,
) -> None:
    """ON CONFLICT (event_id) DO NOTHING: producer retry is no-op."""
    actor_id = ActorId(UUID("01900000-0000-7000-8000-000000089a01"))
    actor_event_id = UUID("01900000-0000-7000-8000-000000089a02")
    decision_id = UUID("01900000-0000-7000-8000-000000089b01")
    decision_event_id = UUID("01900000-0000-7000-8000-000000089b02")
    logbook_id = UUID("01900000-0000-7000-8000-000000089b03")

    deps = _build_deps(db_pool, [actor_id, actor_event_id, decision_id, decision_event_id])

    await bind_register_actor(deps, profile_store=make_pg_profile_store(db_pool))(
        RegisterActor(name="Dedup Tester"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_register_decision(deps)(
        RegisterDecision(
            decided_by=actor_id,
            context="RecipeApproval",
            choice="Approved",
            parent_id=None,
            override_kind=None,
            rule=None,
            reasoning=None,
            confidence=None,
            confidence_source=None,
            alternatives=(),
            inputs=None,
            reasoning_signature=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    store = PostgresReasoningStore(db_pool)
    shared_event_id = UUID("01900000-0000-7000-8000-000000089c01")

    from cora.decision.aggregates.decision import DecisionReasoning

    first_row = DecisionReasoning(
        event_id=shared_event_id,
        decision_id=decision_id,
        logbook_id=logbook_id,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        duration=None,
        operation_name="chat",
        provider_name="anthropic",
        request_model="claude-opus-4-7",
        response_id=None,
        response_model=None,
        request_temperature=None,
        request_top_p=None,
        request_max_tokens=None,
        output_type=None,
        finish_reasons=(),
        input_tokens=None,
        output_tokens=None,
        agent_id=None,
        agent_name=None,
        agent_description=None,
        conversation_id=None,
        tool_name=None,
        tool_call_id=None,
        tool_type=None,
        messages=None,
    )
    # Different content, same event_id; second write must be silent no-op.
    second_row = DecisionReasoning(
        event_id=shared_event_id,
        decision_id=decision_id,
        logbook_id=logbook_id,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        duration=None,
        operation_name="chat",
        provider_name="anthropic",
        request_model="claude-sonnet-4-6",  # different content
        response_id=None,
        response_model=None,
        request_temperature=None,
        request_top_p=None,
        request_max_tokens=None,
        output_type=None,
        finish_reasons=(),
        input_tokens=None,
        output_tokens=None,
        agent_id=None,
        agent_name=None,
        agent_description=None,
        conversation_id=None,
        tool_name=None,
        tool_call_id=None,
        tool_type=None,
        messages=None,
    )

    await store.append([first_row])
    await store.append([second_row])

    rows = await _read_entries_for_decision(db_pool, decision_id)
    assert len(rows) == 1
    # First write wins.
    assert rows[0]["request_model"] == "claude-opus-4-7"
