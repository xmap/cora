"""Unit tests for `BudgetSpendGuard`, the Agent BC's pre-estimate adapter.

Drives the guard against `InMemoryEventStore` seeds + `FakeSpendLookup`
so every refusal branch (lifecycle, monthly USD, daily tokens) and every
permissive branch (no agent, no budget, headroom, exact-cap landing) is
pinned, along with the calendar windows the lookup is asked for.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.adapters import BudgetSpendGuard
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from tests.unit.agent._helpers import (
    FakeSpendLookup,
    seed_defined_agent,
    seed_suspended_agent,
    seed_versioned_agent,
)

_NOW = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000099001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000009900a")


async def _versioned_agent(
    store: InMemoryEventStore,
    agent_id: UUID,
    *,
    monthly_usd_cap: float | None = None,
    daily_token_cap: int | None = None,
) -> None:
    await seed_versioned_agent(
        store,
        agent_id=agent_id,
        genesis_event_id=uuid4(),
        version_event_id=uuid4(),
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_NOW,
        versioned_at=_NOW,
        monthly_usd_cap=monthly_usd_cap,
        daily_token_cap=daily_token_cap,
    )


def _guard(store: InMemoryEventStore, lookup: FakeSpendLookup) -> BudgetSpendGuard:
    return BudgetSpendGuard(event_store=store, spend_lookup=lookup)


@pytest.mark.unit
async def test_missing_agent_stream_grants() -> None:
    """Declaration is opt-in: no Agent aggregate must never block."""
    guard = _guard(InMemoryEventStore(), FakeSpendLookup())

    reason = await guard.refusal_reason(
        agent_id=uuid4(), estimated_cost_usd=1.0, estimated_tokens=100, as_of=_NOW
    )

    assert reason is None


@pytest.mark.unit
async def test_suspended_agent_refuses_before_any_lookup() -> None:
    """Suspend means stop on every path; the pre-call check is the
    earliest place the steering brain can be stopped."""
    store = InMemoryEventStore()
    agent_id = uuid4()
    await seed_suspended_agent(
        store,
        agent_id=agent_id,
        genesis_event_id=uuid4(),
        version_event_id=uuid4(),
        suspend_event_id=uuid4(),
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_NOW,
        versioned_at=_NOW,
        suspended_at=_NOW,
    )
    lookup = FakeSpendLookup()
    guard = _guard(store, lookup)

    reason = await guard.refusal_reason(
        agent_id=agent_id, estimated_cost_usd=0.01, estimated_tokens=10, as_of=_NOW
    )

    assert reason is not None
    assert "not Versioned" in reason
    assert lookup.windows == []


@pytest.mark.unit
async def test_versioned_agent_with_no_budget_grants() -> None:
    store = InMemoryEventStore()
    agent_id = uuid4()
    await _versioned_agent(store, agent_id)
    guard = _guard(store, FakeSpendLookup())

    reason = await guard.refusal_reason(
        agent_id=agent_id, estimated_cost_usd=10_000.0, estimated_tokens=1, as_of=_NOW
    )

    assert reason is None


@pytest.mark.unit
async def test_projected_monthly_breach_refuses_with_window_pinned() -> None:
    store = InMemoryEventStore()
    agent_id = uuid4()
    await _versioned_agent(store, agent_id, monthly_usd_cap=100.0)
    lookup = FakeSpendLookup(usd_spent=99.5)
    guard = _guard(store, lookup)

    reason = await guard.refusal_reason(
        agent_id=agent_id, estimated_cost_usd=0.6, estimated_tokens=100, as_of=_NOW
    )

    assert reason is not None
    assert "monthly_usd_cap" in reason
    assert lookup.windows == [
        (agent_id, datetime(2026, 5, 1, tzinfo=UTC), datetime(2026, 6, 1, tzinfo=UTC))
    ]


@pytest.mark.unit
async def test_projection_landing_exactly_on_the_cap_grants() -> None:
    """The cap is an amount the envelope affords, not a fence before it:
    spent + ceiling == cap is the last permitted call."""
    store = InMemoryEventStore()
    agent_id = uuid4()
    await _versioned_agent(store, agent_id, monthly_usd_cap=100.0)
    guard = _guard(store, FakeSpendLookup(usd_spent=99.5))

    reason = await guard.refusal_reason(
        agent_id=agent_id, estimated_cost_usd=0.5, estimated_tokens=100, as_of=_NOW
    )

    assert reason is None


@pytest.mark.unit
async def test_projected_daily_token_breach_refuses_with_window_pinned() -> None:
    store = InMemoryEventStore()
    agent_id = uuid4()
    await _versioned_agent(store, agent_id, daily_token_cap=50_000)
    lookup = FakeSpendLookup(tokens_spent=49_000)
    guard = _guard(store, lookup)

    reason = await guard.refusal_reason(
        agent_id=agent_id, estimated_cost_usd=0.01, estimated_tokens=1_500, as_of=_NOW
    )

    assert reason is not None
    assert "daily_token_cap" in reason
    assert lookup.windows == [
        (agent_id, datetime(2026, 5, 17, tzinfo=UTC), datetime(2026, 5, 18, tzinfo=UTC))
    ]


@pytest.mark.unit
async def test_headroom_on_both_caps_grants_after_both_lookups() -> None:
    store = InMemoryEventStore()
    agent_id = uuid4()
    await _versioned_agent(store, agent_id, monthly_usd_cap=100.0, daily_token_cap=50_000)
    lookup = FakeSpendLookup(usd_spent=1.0, tokens_spent=100)
    guard = _guard(store, lookup)

    reason = await guard.refusal_reason(
        agent_id=agent_id, estimated_cost_usd=0.5, estimated_tokens=2_000, as_of=_NOW
    )

    assert reason is None
    assert len(lookup.windows) == 2


@pytest.mark.unit
async def test_both_caps_breached_refuses_on_monthly_after_one_lookup() -> None:
    """Cap order matches the post-hoc gate: monthly USD first, and the
    daily lookup is never made once monthly refuses."""
    store = InMemoryEventStore()
    agent_id = uuid4()
    await _versioned_agent(store, agent_id, monthly_usd_cap=100.0, daily_token_cap=1_000)
    lookup = FakeSpendLookup(usd_spent=100.0, tokens_spent=1_000)
    guard = _guard(store, lookup)

    reason = await guard.refusal_reason(
        agent_id=agent_id, estimated_cost_usd=0.5, estimated_tokens=100, as_of=_NOW
    )

    assert reason is not None
    assert "monthly_usd_cap" in reason
    assert len(lookup.windows) == 1


@pytest.mark.unit
async def test_defined_seeded_agent_is_refused_until_versioned() -> None:
    """The production seed leaves fleet agents Defined, and Defined means
    not ready for invocation: with the real guard bound, steering is
    refused until the operator runs version_agent, the same
    bootstrap-then-promote ceremony the LLM subscribers follow."""
    store = InMemoryEventStore()
    agent_id = uuid4()
    await seed_defined_agent(
        store,
        agent_id=agent_id,
        genesis_event_id=uuid4(),
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        occurred_at=_NOW,
    )
    guard = _guard(store, FakeSpendLookup())

    reason = await guard.refusal_reason(
        agent_id=agent_id, estimated_cost_usd=0.01, estimated_tokens=10, as_of=_NOW
    )

    assert reason is not None
    assert "Defined" in reason
