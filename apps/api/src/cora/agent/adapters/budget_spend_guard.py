"""BudgetSpendGuard: the Agent BC's production `SpendGuard` adapter.

The pre-estimate tier's policy lives here because the Agent BC owns both
facts the check needs: the caller's declared `AgentBudget` caps (on the
Agent aggregate) and the lifecycle state that says whether the agent may
act at all. Recorded spend comes through the same `SpendLookup` the
coarse post-hoc gate sums, over the same UTC calendar windows, so the
two tiers can never disagree about what has been spent.

## Refusal policy

  - Agent stream missing: permit. Declaration is opt-in; absence of an
    Agent aggregate must never block (mirrors `find_budget_breach`).
  - Agent not Versioned: refuse. Suspend means stop on every path, and
    the pre-call check is the earliest place the steering brain can be
    stopped (the post-hoc record path only notices AFTER spend).
  - No declared budget: permit.
  - Projected breach: refuse when recorded spend plus the estimated
    ceiling would exceed a cap (strictly greater: a call that lands
    exactly on the cap is the last one the envelope affords). Monthly
    USD is checked first, then daily tokens, one lookup per declared
    cap, matching the post-hoc gate's order.

A lookup ERROR propagates, per the port's fail-closed stance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.agent._budget_gate import calendar_day_window, calendar_month_window
from cora.agent.aggregates.agent import AgentStatus, load_agent

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from cora.infrastructure.ports.event_store import EventStore
    from cora.infrastructure.ports.spend_lookup import SpendLookup


class BudgetSpendGuard:
    """`SpendGuard` over the Agent aggregate's caps and the spend ledger."""

    def __init__(self, *, event_store: EventStore, spend_lookup: SpendLookup) -> None:
        self._event_store = event_store
        self._spend_lookup = spend_lookup

    async def refusal_reason(
        self,
        *,
        agent_id: UUID,
        estimated_cost_usd: float,
        estimated_tokens: int,
        as_of: datetime,
    ) -> str | None:
        agent = await load_agent(self._event_store, agent_id)
        if agent is None:
            return None
        if agent.status is not AgentStatus.VERSIONED:
            return f"agent is {agent.status.value}, not Versioned; calls are stopped"
        if agent.budget is None:
            return None
        budget = agent.budget

        if budget.monthly_usd_cap is not None:
            window_start, window_end = calendar_month_window(as_of)
            spend = await self._spend_lookup.find_agent_spend(
                agent_id=agent_id,
                window_start=window_start,
                window_end=window_end,
            )
            projected = spend.usd_spent + estimated_cost_usd
            if projected > budget.monthly_usd_cap:
                return (
                    f"monthly_usd_cap of {budget.monthly_usd_cap:g} would be breached: "
                    f"{spend.usd_spent:g} spent this month plus an estimated "
                    f"{estimated_cost_usd:g} ceiling for this call"
                )

        if budget.daily_token_cap is not None:
            window_start, window_end = calendar_day_window(as_of)
            spend = await self._spend_lookup.find_agent_spend(
                agent_id=agent_id,
                window_start=window_start,
                window_end=window_end,
            )
            projected_tokens = spend.tokens_spent + estimated_tokens
            if projected_tokens > budget.daily_token_cap:
                return (
                    f"daily_token_cap of {budget.daily_token_cap} would be breached: "
                    f"{spend.tokens_spent} tokens spent today plus an estimated "
                    f"{estimated_tokens} for this call"
                )

        return None


__all__ = ["BudgetSpendGuard"]
