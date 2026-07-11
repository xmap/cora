"""Integration tests for `PostgresSpendLookup` over `entries_decision_inferences`.

Seeds inference rows directly through `PostgresInferenceStore` (the same
write path production uses) and verifies the spend sums respect the
agent filter, the half-open window bounds, and the NULL-cost COALESCE
that keeps pre-migration history from inflating a balance.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.decision.adapters import PostgresSpendLookup
from cora.decision.aggregates.decision import Inference
from cora.decision.aggregates.decision.entries import PostgresInferenceStore

_AGENT_ID = UUID("01900000-0000-7000-8000-0000000a0010")
_OTHER_AGENT_ID = UUID("01900000-0000-7000-8000-0000000a0020")

_WINDOW_START = datetime(2026, 7, 1, tzinfo=UTC)
_WINDOW_END = datetime(2026, 8, 1, tzinfo=UTC)


def _row(
    *,
    agent_id: UUID | None,
    occurred_at: datetime,
    cost_usd: float | None,
    input_tokens: int | None = 100,
    output_tokens: int | None = 50,
) -> Inference:
    return Inference(
        event_id=uuid4(),
        decision_id=uuid4(),
        logbook_id=uuid4(),
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=occurred_at,
        duration=None,
        operation_name="chat",
        provider_name="anthropic",
        request_model="claude-haiku-4-5",
        response_id=None,
        response_model=None,
        request_temperature=None,
        request_top_p=None,
        request_max_tokens=None,
        output_type=None,
        finish_reasons=(),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        agent_id=str(agent_id) if agent_id is not None else None,
        agent_name=None,
        agent_description=None,
        conversation_id=None,
        tool_name=None,
        tool_call_id=None,
        tool_type=None,
        messages=None,
    )


@pytest.mark.integration
async def test_sums_only_the_agents_rows_inside_the_window(db_pool: asyncpg.Pool) -> None:
    """usd/tokens/count sum the target agent's in-window rows; another
    agent's rows, agentless rows, and out-of-window rows are excluded;
    the window is half-open (a row exactly at window_start counts, a
    row exactly at window_end does not)."""
    store = PostgresInferenceStore(db_pool)
    in_window = datetime(2026, 7, 10, tzinfo=UTC)
    await store.append(
        [
            _row(agent_id=_AGENT_ID, occurred_at=in_window, cost_usd=0.002),
            _row(agent_id=_AGENT_ID, occurred_at=in_window, cost_usd=0.003),
            _row(agent_id=_AGENT_ID, occurred_at=_WINDOW_START, cost_usd=0.001),
            # Excluded: other agent, agentless (operator-attributed row),
            # before start, exactly at end (half-open).
            _row(agent_id=_OTHER_AGENT_ID, occurred_at=in_window, cost_usd=5.0),
            _row(agent_id=None, occurred_at=in_window, cost_usd=3.0),
            _row(agent_id=_AGENT_ID, occurred_at=datetime(2026, 6, 30, tzinfo=UTC), cost_usd=7.0),
            _row(agent_id=_AGENT_ID, occurred_at=_WINDOW_END, cost_usd=9.0),
        ]
    )

    result = await PostgresSpendLookup(db_pool).find_agent_spend(
        agent_id=_AGENT_ID,
        window_start=_WINDOW_START,
        window_end=_WINDOW_END,
    )

    assert result.agent_id == _AGENT_ID
    assert result.usd_spent == pytest.approx(0.006)
    assert result.tokens_spent == 450  # 3 rows x (100 in + 50 out)
    assert result.call_count == 3


@pytest.mark.integration
async def test_null_costs_and_tokens_sum_as_zero_not_poison(db_pool: asyncpg.Pool) -> None:
    """Pre-migration rows (cost_usd IS NULL) and rows with NULL token
    counts still COUNT as calls but contribute $0 / 0 tokens, keeping
    the gate permissive rather than blocking on unknowable history."""
    store = PostgresInferenceStore(db_pool)
    agent_id = uuid4()
    in_window = datetime(2026, 7, 15, tzinfo=UTC)
    await store.append(
        [
            _row(agent_id=agent_id, occurred_at=in_window, cost_usd=None),
            _row(
                agent_id=agent_id,
                occurred_at=in_window,
                cost_usd=0.01,
                input_tokens=None,
                output_tokens=None,
            ),
        ]
    )

    result = await PostgresSpendLookup(db_pool).find_agent_spend(
        agent_id=agent_id,
        window_start=_WINDOW_START,
        window_end=_WINDOW_END,
    )

    assert result.usd_spent == pytest.approx(0.01)
    assert result.tokens_spent == 150  # only the NULL-cost row carried tokens
    assert result.call_count == 2


@pytest.mark.integration
async def test_agent_with_no_rows_returns_a_zero_row(db_pool: asyncpg.Pool) -> None:
    """'No spend' and 'unknown agent' are the same answer to a gate."""
    result = await PostgresSpendLookup(db_pool).find_agent_spend(
        agent_id=uuid4(),
        window_start=_WINDOW_START,
        window_end=_WINDOW_END,
    )

    assert result.usd_spent == 0.0
    assert result.tokens_spent == 0
    assert result.call_count == 0
