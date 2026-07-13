"""Unit tests for the coarse post-hoc budget gate (`cora.agent._budget_gate`)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.agent._budget_gate import (
    calendar_day_window,
    calendar_month_window,
    find_allocation_breach,
    find_budget_breach,
)
from cora.agent.aggregates.agent import load_agent
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.ports.allocation_lookup import (
    AllocationLookupResult,
    NoActiveAllocationLookup,
)
from tests.unit.agent._helpers import (
    FakeAllocationLookup,
    FakeSpendLookup,
    seed_defined_agent,
)

_NOW = datetime(2026, 7, 11, 15, 30, 0, tzinfo=UTC)
_CORRELATION_ID = uuid4()
_PRINCIPAL_ID = uuid4()

_ACTIVATED_AT = datetime(2026, 7, 1, 8, 0, 0, tzinfo=UTC)


def _envelope(*, ceiling_usd: float = 100.0) -> AllocationLookupResult:
    return AllocationLookupResult(
        allocation_id=uuid4(),
        ceiling_usd=ceiling_usd,
        activated_at=_ACTIVATED_AT,
        campaign_id=None,
    )


async def _agent_with_caps(
    store: InMemoryEventStore,
    *,
    monthly_usd_cap: float | None = None,
    daily_token_cap: int | None = None,
):
    agent_id = uuid4()
    await seed_defined_agent(
        store,
        agent_id=agent_id,
        genesis_event_id=uuid4(),
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        occurred_at=_NOW,
        monthly_usd_cap=monthly_usd_cap,
        daily_token_cap=daily_token_cap,
    )
    return await load_agent(store, agent_id)


# ---------- Window helpers ----------


@pytest.mark.unit
def test_calendar_month_window_mid_month() -> None:
    start, end = calendar_month_window(_NOW)
    assert start == datetime(2026, 7, 1, tzinfo=UTC)
    assert end == datetime(2026, 8, 1, tzinfo=UTC)


@pytest.mark.unit
def test_calendar_month_window_december_rolls_into_next_year() -> None:
    start, end = calendar_month_window(datetime(2026, 12, 31, 23, 59, tzinfo=UTC))
    assert start == datetime(2026, 12, 1, tzinfo=UTC)
    assert end == datetime(2027, 1, 1, tzinfo=UTC)


@pytest.mark.unit
def test_calendar_day_window_brackets_the_utc_day() -> None:
    start, end = calendar_day_window(_NOW)
    assert start == datetime(2026, 7, 11, tzinfo=UTC)
    assert end == datetime(2026, 7, 12, tzinfo=UTC)


# ---------- find_budget_breach ----------


@pytest.mark.unit
async def test_no_agent_stream_permits_without_querying_spend() -> None:
    """Declaration is opt-in: a missing Agent stream never blocks."""
    lookup = FakeSpendLookup(usd_spent=1_000_000.0)

    breach = await find_budget_breach(agent=None, spend_lookup=lookup, as_of=_NOW)

    assert breach is None
    assert lookup.windows == []


@pytest.mark.unit
async def test_no_declared_budget_permits_without_querying_spend() -> None:
    store = InMemoryEventStore()
    agent = await _agent_with_caps(store)
    lookup = FakeSpendLookup(usd_spent=1_000_000.0)

    breach = await find_budget_breach(agent=agent, spend_lookup=lookup, as_of=_NOW)

    assert breach is None
    assert lookup.windows == []


@pytest.mark.unit
async def test_spend_under_both_caps_permits() -> None:
    store = InMemoryEventStore()
    agent = await _agent_with_caps(store, monthly_usd_cap=500.0, daily_token_cap=2_000_000)
    lookup = FakeSpendLookup(usd_spent=499.99, tokens_spent=1_999_999)

    breach = await find_budget_breach(agent=agent, spend_lookup=lookup, as_of=_NOW)

    assert breach is None
    assert len(lookup.windows) == 2  # one SUM per declared cap


@pytest.mark.unit
async def test_monthly_usd_cap_reached_breaches_over_the_month_window() -> None:
    store = InMemoryEventStore()
    agent = await _agent_with_caps(store, monthly_usd_cap=120.0)
    lookup = FakeSpendLookup(usd_spent=121.3)

    breach = await find_budget_breach(agent=agent, spend_lookup=lookup, as_of=_NOW)

    assert breach is not None
    assert breach.cap_kind == "monthly_usd_cap"
    assert breach.cap_value == 120.0
    assert breach.spent == pytest.approx(121.3)
    assert breach.window_start == datetime(2026, 7, 1, tzinfo=UTC)
    assert breach.window_end == datetime(2026, 8, 1, tzinfo=UTC)
    assert agent is not None
    assert lookup.windows == [(agent.id, breach.window_start, breach.window_end)]


@pytest.mark.unit
async def test_daily_token_cap_reached_breaches_over_the_day_window() -> None:
    store = InMemoryEventStore()
    agent = await _agent_with_caps(store, daily_token_cap=1_000_000)
    lookup = FakeSpendLookup(tokens_spent=1_000_000)

    breach = await find_budget_breach(agent=agent, spend_lookup=lookup, as_of=_NOW)

    assert breach is not None
    assert breach.cap_kind == "daily_token_cap"
    assert breach.window_start == datetime(2026, 7, 11, tzinfo=UTC)
    assert breach.window_end == datetime(2026, 7, 12, tzinfo=UTC)


@pytest.mark.unit
async def test_monthly_breach_wins_when_both_caps_are_exhausted() -> None:
    """Caps are checked in declaration order; the first breach is
    reported and the daily SUM is never issued."""
    store = InMemoryEventStore()
    agent = await _agent_with_caps(store, monthly_usd_cap=10.0, daily_token_cap=100)
    lookup = FakeSpendLookup(usd_spent=11.0, tokens_spent=101)

    breach = await find_budget_breach(agent=agent, spend_lookup=lookup, as_of=_NOW)

    assert breach is not None
    assert breach.cap_kind == "monthly_usd_cap"
    assert len(lookup.windows) == 1


@pytest.mark.unit
async def test_daily_breach_detected_when_monthly_cap_has_headroom() -> None:
    """The daily check must run even after a PASSING monthly check;
    an early return after monthly headroom would silently disable
    the token cap."""
    store = InMemoryEventStore()
    agent = await _agent_with_caps(store, monthly_usd_cap=500.0, daily_token_cap=100)
    lookup = FakeSpendLookup(usd_spent=1.0, tokens_spent=101)

    breach = await find_budget_breach(agent=agent, spend_lookup=lookup, as_of=_NOW)

    assert breach is not None
    assert breach.cap_kind == "daily_token_cap"
    assert len(lookup.windows) == 2


@pytest.mark.unit
async def test_zero_cap_refuses_every_call() -> None:
    """AgentBudget documents a zero cap as recorded no-spend intent;
    the gate is what makes that intent real (0 spent >= 0 cap)."""
    store = InMemoryEventStore()
    agent = await _agent_with_caps(store, monthly_usd_cap=0.0)
    lookup = FakeSpendLookup(usd_spent=0.0)

    breach = await find_budget_breach(agent=agent, spend_lookup=lookup, as_of=_NOW)

    assert breach is not None
    assert breach.cap_kind == "monthly_usd_cap"


# ---------- find_allocation_breach ----------


@pytest.mark.unit
async def test_no_active_envelope_permits_without_summing_spend() -> None:
    """No envelope declared means no envelope constraint; the ledger
    SUM is never issued on the disarmed path."""
    spend = FakeSpendLookup(total_usd_spent=1_000_000.0)

    breach = await find_allocation_breach(
        allocation_lookup=NoActiveAllocationLookup(),
        spend_lookup=spend,
        as_of=_NOW,
    )

    assert breach is None
    assert spend.total_windows == []


@pytest.mark.unit
async def test_envelope_spend_below_ceiling_permits_over_the_lifecycle_window() -> None:
    """The window is the envelope's own lifecycle [activated_at,
    as_of), not calendar arithmetic."""
    envelope = _envelope(ceiling_usd=100.0)
    spend = FakeSpendLookup(total_usd_spent=99.99)

    breach = await find_allocation_breach(
        allocation_lookup=FakeAllocationLookup(envelope),
        spend_lookup=spend,
        as_of=_NOW,
    )

    assert breach is None
    assert spend.total_windows == [(_ACTIVATED_AT, _NOW)]


@pytest.mark.unit
async def test_post_hoc_exactly_exhausted_envelope_breaches() -> None:
    """Post-hoc callers pass no pending figure, so spend landing
    exactly on the ceiling refuses the NEXT call (the >= arm)."""
    envelope = _envelope(ceiling_usd=100.0)

    breach = await find_allocation_breach(
        allocation_lookup=FakeAllocationLookup(envelope),
        spend_lookup=FakeSpendLookup(total_usd_spent=100.0),
        as_of=_NOW,
    )

    assert breach is not None
    assert breach.allocation_id == envelope.allocation_id
    assert breach.ceiling_usd == 100.0
    assert breach.spent_usd == pytest.approx(100.0)
    assert breach.window_start == _ACTIVATED_AT


@pytest.mark.unit
async def test_pre_estimate_projection_landing_exactly_on_ceiling_grants() -> None:
    """With a pending estimate the check is strictly-greater: a call
    projected to land exactly ON the ceiling is the last one the
    envelope affords (matches BudgetSpendGuard's per-agent
    convention)."""
    envelope = _envelope(ceiling_usd=100.0)

    breach = await find_allocation_breach(
        allocation_lookup=FakeAllocationLookup(envelope),
        spend_lookup=FakeSpendLookup(total_usd_spent=99.5),
        as_of=_NOW,
        pending_usd=0.5,
    )

    assert breach is None


@pytest.mark.unit
async def test_pre_estimate_projection_over_ceiling_breaches() -> None:
    envelope = _envelope(ceiling_usd=100.0)

    breach = await find_allocation_breach(
        allocation_lookup=FakeAllocationLookup(envelope),
        spend_lookup=FakeSpendLookup(total_usd_spent=99.5),
        as_of=_NOW,
        pending_usd=0.6,
    )

    assert breach is not None
    assert breach.spent_usd == pytest.approx(99.5)


@pytest.mark.unit
async def test_envelope_breach_describe_names_the_allocation() -> None:
    """The describe() sentence lands on deferred Decisions, so it
    must name the envelope and its window start for operators."""
    envelope = _envelope(ceiling_usd=100.0)

    breach = await find_allocation_breach(
        allocation_lookup=FakeAllocationLookup(envelope),
        spend_lookup=FakeSpendLookup(total_usd_spent=250.0),
        as_of=_NOW,
    )

    assert breach is not None
    description = breach.describe()
    assert str(envelope.allocation_id) in description
    assert _ACTIVATED_AT.isoformat() in description
