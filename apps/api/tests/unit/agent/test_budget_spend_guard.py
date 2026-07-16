"""Unit tests for `BudgetSpendGuard`, the Agent BC's pre-estimate adapter.

Drives the guard against `InMemoryEventStore` seeds + `FakeSpendLookup`
so every refusal branch (lifecycle, monthly USD, daily tokens, the
instrument-wide allocation envelope) and every permissive branch (no
agent, no budget, headroom, exact-cap landing) is pinned, along with
the windows the lookup is asked for.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.adapters import BudgetSpendGuard
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.ports.allocation_lookup import AllocationLookupResult
from tests.unit.agent._helpers import (
    FakeAllocationLookup,
    FakeSpendLookup,
    seed_defined_agent,
    seed_suspended_agent,
    seed_versioned_agent,
)

_NOW = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000099001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000009900a")

_ENVELOPE_ACTIVATED_AT = datetime(2026, 5, 1, 8, 0, 0, tzinfo=UTC)


def _envelope(*, ceiling_usd: float = 100.0) -> AllocationLookupResult:
    return AllocationLookupResult(
        allocation_id=uuid4(),
        ceiling_usd=ceiling_usd,
        activated_at=_ENVELOPE_ACTIVATED_AT,
        campaign_id=None,
    )


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
async def test_daily_token_projection_landing_exactly_on_the_cap_grants() -> None:
    """The daily-token arm's equality edge mirrors the monthly USD arm:
    spent + estimate == cap is the last permitted call, so the strict
    `>` comparison must not refuse it."""
    store = InMemoryEventStore()
    agent_id = uuid4()
    await _versioned_agent(store, agent_id, daily_token_cap=50_000)
    guard = _guard(store, FakeSpendLookup(tokens_spent=49_000))

    reason = await guard.refusal_reason(
        agent_id=agent_id, estimated_cost_usd=0.01, estimated_tokens=1_000, as_of=_NOW
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


@pytest.mark.unit
async def test_envelope_projection_over_ceiling_refuses_naming_the_envelope() -> None:
    """The instrument-wide arm: instance-total spend plus this call's
    estimate strictly over the Active ceiling refuses, over the
    envelope's own lifecycle window."""
    store = InMemoryEventStore()
    agent_id = uuid4()
    await _versioned_agent(store, agent_id)
    envelope = _envelope(ceiling_usd=100.0)
    lookup = FakeSpendLookup(total_usd_spent=99.5)
    guard = BudgetSpendGuard(
        event_store=store,
        spend_lookup=lookup,
        allocation_lookup=FakeAllocationLookup(envelope),
    )

    reason = await guard.refusal_reason(
        agent_id=agent_id, estimated_cost_usd=0.6, estimated_tokens=100, as_of=_NOW
    )

    assert reason is not None
    assert str(envelope.allocation_id) in reason
    assert lookup.total_windows == [(_ENVELOPE_ACTIVATED_AT, _NOW)]


@pytest.mark.unit
async def test_envelope_projection_landing_exactly_on_ceiling_grants() -> None:
    """Strictly-greater, matching the per-agent pre-estimate stance:
    the ceiling is an amount the envelope affords."""
    store = InMemoryEventStore()
    agent_id = uuid4()
    await _versioned_agent(store, agent_id)
    guard = BudgetSpendGuard(
        event_store=store,
        spend_lookup=FakeSpendLookup(total_usd_spent=99.5),
        allocation_lookup=FakeAllocationLookup(_envelope(ceiling_usd=100.0)),
    )

    reason = await guard.refusal_reason(
        agent_id=agent_id, estimated_cost_usd=0.5, estimated_tokens=100, as_of=_NOW
    )

    assert reason is None


@pytest.mark.unit
async def test_envelope_gates_an_agent_with_no_declared_budget() -> None:
    """The envelope is armed by declaring an allocation, not by
    per-agent cap ceremony: an uncapped agent is still stopped when
    the instrument's one balance is exhausted."""
    store = InMemoryEventStore()
    agent_id = uuid4()
    await _versioned_agent(store, agent_id)
    guard = BudgetSpendGuard(
        event_store=store,
        spend_lookup=FakeSpendLookup(total_usd_spent=200.0),
        allocation_lookup=FakeAllocationLookup(_envelope(ceiling_usd=100.0)),
    )

    reason = await guard.refusal_reason(
        agent_id=agent_id, estimated_cost_usd=1.0, estimated_tokens=10, as_of=_NOW
    )

    assert reason is not None
    assert "allocation envelope" in reason


@pytest.mark.unit
async def test_envelope_gates_even_when_the_agent_stream_is_missing() -> None:
    """A caller with no Agent stream skips the per-agent checks but
    not the instrument-wide one."""
    guard = BudgetSpendGuard(
        event_store=InMemoryEventStore(),
        spend_lookup=FakeSpendLookup(total_usd_spent=200.0),
        allocation_lookup=FakeAllocationLookup(_envelope(ceiling_usd=100.0)),
    )

    reason = await guard.refusal_reason(
        agent_id=uuid4(), estimated_cost_usd=1.0, estimated_tokens=10, as_of=_NOW
    )

    assert reason is not None
    assert "allocation envelope" in reason


@pytest.mark.unit
async def test_per_agent_cap_refusal_wins_before_the_envelope_is_consulted() -> None:
    """Cap order: the declared per-agent caps refuse first; the
    envelope lookup is never made once a cap refuses."""
    store = InMemoryEventStore()
    agent_id = uuid4()
    await _versioned_agent(store, agent_id, monthly_usd_cap=1.0)
    allocation_lookup = FakeAllocationLookup(_envelope(ceiling_usd=100.0))
    guard = BudgetSpendGuard(
        event_store=store,
        spend_lookup=FakeSpendLookup(usd_spent=5.0),
        allocation_lookup=allocation_lookup,
    )

    reason = await guard.refusal_reason(
        agent_id=agent_id, estimated_cost_usd=0.5, estimated_tokens=10, as_of=_NOW
    )

    assert reason is not None
    assert "monthly_usd_cap" in reason
    assert allocation_lookup.find_active_calls == 0


@pytest.mark.unit
async def test_no_active_envelope_leaves_the_guard_cap_only() -> None:
    """Default construction (no allocation_lookup) keeps the guard's
    pre-envelope behavior byte-for-byte: headroom on caps grants."""
    store = InMemoryEventStore()
    agent_id = uuid4()
    await _versioned_agent(store, agent_id, monthly_usd_cap=100.0)
    guard = _guard(store, FakeSpendLookup(usd_spent=1.0))

    reason = await guard.refusal_reason(
        agent_id=agent_id, estimated_cost_usd=0.5, estimated_tokens=10, as_of=_NOW
    )

    assert reason is None
