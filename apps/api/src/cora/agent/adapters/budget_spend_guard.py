"""BudgetSpendGuard: the Agent BC's production `SpendGuard` adapter.

The pre-estimate tier's policy lives here because the Agent BC owns both
facts the check needs: the caller's declared `AgentBudget` caps (on the
Agent aggregate) and the lifecycle state that says whether the agent may
act at all. Recorded spend comes through the same `SpendLookup` the
coarse post-hoc gate sums, over the same UTC calendar windows, so the
two tiers can never disagree about what has been spent.

## Refusal policy

  - Agent stream missing: the per-agent checks permit. Declaration is
    opt-in; absence of an Agent aggregate must never block (mirrors
    `find_budget_breach`). The envelope check below still runs.
  - Agent not Versioned: refuse. Suspend means stop on every path, and
    the pre-call check is the earliest place the steering brain can be
    stopped (the post-hoc record path only notices AFTER spend).
  - No declared budget: the per-agent checks permit.
  - Projected breach: refuse when recorded spend plus the estimated
    ceiling would exceed a cap (strictly greater: a call that lands
    exactly on the cap is the last one the envelope affords). Monthly
    USD is checked first, then daily tokens, one lookup per declared
    cap, matching the post-hoc gate's order.
  - Envelope breach: after the per-agent caps, the instrument-wide
    allocation envelope is consulted with `pending = estimated_cost_usd`
    (the caller already folds its in-conduct actuals into that
    estimate). Instance-total spend plus the estimate strictly over
    the Active ceiling refuses. Runs even when the agent has no
    declared budget or no Agent stream: the envelope is armed by
    declaring an allocation, not by per-agent ceremony.

A lookup ERROR propagates, per the port's fail-closed stance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.agent._budget_gate import (
    calendar_day_window,
    calendar_month_window,
    find_allocation_breach,
)
from cora.agent.aggregates.agent import AgentStatus, load_agent
from cora.infrastructure.ports import NoActiveAllocationLookup

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from cora.agent.aggregates.agent import AgentBudget
    from cora.infrastructure.ports.allocation_lookup import AllocationLookup
    from cora.infrastructure.ports.event_store import EventStore
    from cora.infrastructure.ports.spend_lookup import SpendLookup


class BudgetSpendGuard:
    """`SpendGuard` over the Agent aggregate's caps and the spend ledger."""

    def __init__(
        self,
        *,
        event_store: EventStore,
        spend_lookup: SpendLookup,
        allocation_lookup: AllocationLookup | None = None,
    ) -> None:
        self._event_store = event_store
        self._spend_lookup = spend_lookup
        # Defaults to no Active envelope so direct test construction stays
        # cap-only; production wiring passes the Kernel's allocation_lookup.
        self._allocation_lookup = allocation_lookup or NoActiveAllocationLookup()

    async def refusal_reason(
        self,
        *,
        agent_id: UUID,
        estimated_cost_usd: float,
        estimated_tokens: int,
        as_of: datetime,
    ) -> str | None:
        agent = await load_agent(self._event_store, agent_id)
        if agent is not None:
            if agent.status is not AgentStatus.VERSIONED:
                return f"agent is {agent.status.value}, not Versioned; calls are stopped"
            per_agent_reason = await self._per_agent_cap_refusal(
                agent_budget=agent.budget,
                agent_id=agent_id,
                estimated_cost_usd=estimated_cost_usd,
                estimated_tokens=estimated_tokens,
                as_of=as_of,
            )
            if per_agent_reason is not None:
                return per_agent_reason

        envelope_breach = await find_allocation_breach(
            allocation_lookup=self._allocation_lookup,
            spend_lookup=self._spend_lookup,
            as_of=as_of,
            pending_usd=estimated_cost_usd,
        )
        if envelope_breach is not None:
            return (
                f"allocation envelope {envelope_breach.allocation_id} ceiling of "
                f"{envelope_breach.ceiling_usd:g} USD would be breached: "
                f"{envelope_breach.spent_usd:g} instance-total spend since "
                f"{envelope_breach.window_start.isoformat()} plus an estimated "
                f"{estimated_cost_usd:g} ceiling for this call"
            )

        return None

    async def _per_agent_cap_refusal(
        self,
        *,
        agent_budget: AgentBudget | None,
        agent_id: UUID,
        estimated_cost_usd: float,
        estimated_tokens: int,
        as_of: datetime,
    ) -> str | None:
        """Check the declared per-agent caps (monthly USD, then daily tokens)."""
        if agent_budget is None:
            return None
        budget = agent_budget

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
