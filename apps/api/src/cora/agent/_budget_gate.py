"""Coarse post-hoc budget gate for LLM-backed agents.

The enforcement seam that turns a declared `AgentBudget` into a real
control at the coarse tier of the enforcement ladder: debit after each
call (the recorded `cost_usd` on the inference entry) and refuse the
NEXT call once a cap is exhausted. Overspend is bounded to about one
in-flight call per caller, adequate for the cheap, serialized
subscriber agents (RunDebriefer, CautionDrafter). Autonomous or
expensive-long-context callers need the per-call pre-estimate tier
before this gate alone is safe (one call can exhaust a balance before
a post-hoc gate fires).

## Windows

`monthly_usd_cap` is summed over the UTC calendar month containing
`as_of`; `daily_token_cap` over the UTC calendar day. `as_of` is the
triggering event's `occurred_at`, NOT wall clock, so a replayed work
item gates identically (the non-determinism rule: subscribers decide
from event facts, not ambient time).

`find_allocation_breach` is the instrument-wide arm above the per-agent
caps: when the deployment has an Active Allocation envelope (budget
BC), instance-total spend over the envelope's own lifecycle window
must stay inside its ceiling. Absent or sealed envelope means no
constraint (opt-in, like cap declaration).

## Failure direction

The spend sums undercount (NULL-cost legacy rows, unrecorded cache
tokens; see the SpendLookup port docstring), so the gate errs
PERMISSIVE. A cap of exactly zero refuses every call: the `AgentBudget`
value object already documents zero as recorded no-spend intent, and
the gate is what makes that intent real.

A SpendLookup ERROR, by contrast, propagates: the subscriber's apply
raises, the projection worker's retry loop with backoff is the failure
handler, and the bookmark does not advance. The gate never fails OPEN
on a lookup error; wrapping it in a permissive except would let a
database outage disable enforcement silently.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from cora.agent.aggregates.agent import Agent
    from cora.infrastructure.ports.allocation_lookup import AllocationLookup
    from cora.infrastructure.ports.spend_lookup import SpendLookup


@dataclass(frozen=True)
class BudgetBreach:
    """One exhausted cap: which, by how much, over which window."""

    cap_kind: str  # "monthly_usd_cap" | "daily_token_cap"
    cap_value: float
    spent: float
    window_start: datetime
    window_end: datetime

    def describe(self) -> str:
        """One human-readable sentence for a deferred Decision's reasoning."""
        return (
            f"{self.cap_kind} of {self.cap_value:g} reached "
            f"(spent {self.spent:g} in the window starting "
            f"{self.window_start.isoformat()})"
        )


def calendar_month_window(as_of: datetime) -> tuple[datetime, datetime]:
    """Half-open UTC calendar month `[first, first-of-next)` containing `as_of`."""
    at = as_of.astimezone(UTC)
    start = datetime(at.year, at.month, 1, tzinfo=UTC)
    if at.month == 12:
        end = datetime(at.year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(at.year, at.month + 1, 1, tzinfo=UTC)
    return start, end


def calendar_day_window(as_of: datetime) -> tuple[datetime, datetime]:
    """Half-open UTC calendar day `[midnight, next-midnight)` containing `as_of`."""
    at = as_of.astimezone(UTC)
    start = datetime(at.year, at.month, at.day, tzinfo=UTC)
    return start, start + timedelta(days=1)


async def find_budget_breach(
    *,
    agent: "Agent | None",
    spend_lookup: "SpendLookup",
    as_of: datetime,
) -> BudgetBreach | None:
    """Return the first exhausted cap for this agent, or None to permit.

    An agent with no declared budget (or no Agent stream at all) is
    unlimited: declaration is opt-in, so absence of caps must never
    block. Caps are checked in declaration order (monthly USD, then
    daily tokens); the first breach wins, one SpendLookup SUM per
    declared cap.
    """
    if agent is None or agent.budget is None:
        return None
    budget = agent.budget

    if budget.monthly_usd_cap is not None:
        window_start, window_end = calendar_month_window(as_of)
        spend = await spend_lookup.find_agent_spend(
            agent_id=agent.id,
            window_start=window_start,
            window_end=window_end,
        )
        if spend.usd_spent >= budget.monthly_usd_cap:
            return BudgetBreach(
                cap_kind="monthly_usd_cap",
                cap_value=budget.monthly_usd_cap,
                spent=spend.usd_spent,
                window_start=window_start,
                window_end=window_end,
            )

    if budget.daily_token_cap is not None:
        window_start, window_end = calendar_day_window(as_of)
        spend = await spend_lookup.find_agent_spend(
            agent_id=agent.id,
            window_start=window_start,
            window_end=window_end,
        )
        if spend.tokens_spent >= budget.daily_token_cap:
            return BudgetBreach(
                cap_kind="daily_token_cap",
                cap_value=float(budget.daily_token_cap),
                spent=float(spend.tokens_spent),
                window_start=window_start,
                window_end=window_end,
            )

    return None


@dataclass(frozen=True)
class AllocationBreach:
    """The Active allocation envelope cannot afford the next call."""

    allocation_id: UUID
    ceiling_usd: float
    spent_usd: float
    window_start: datetime

    def describe(self) -> str:
        """One human-readable sentence for a deferred Decision's reasoning."""
        return (
            f"allocation {self.allocation_id} ceiling of {self.ceiling_usd:g} USD "
            f"reached (instance-total spend {self.spent_usd:g} since "
            f"{self.window_start.isoformat()})"
        )


async def find_allocation_breach(
    *,
    allocation_lookup: "AllocationLookup",
    spend_lookup: "SpendLookup",
    as_of: datetime,
    pending_usd: float = 0.0,
) -> AllocationBreach | None:
    """Return the Active envelope's breach, or None to permit.

    The instrument-wide arm above the per-agent caps: with an Active
    allocation, instance-total spend is summed over the envelope's
    own window `[activated_at, as_of)` (the lifecycle IS the window;
    no calendar arithmetic) across ALL costed rows, agent-attributed
    and operator-attributed alike. No Active envelope means no
    constraint: declaring and activating one is what arms this check,
    so every envelope-less deployment and test stays permissive.

    Two refusal arms because the two caller tiers ask different
    questions, mirroring the per-agent convention split between
    `find_budget_breach` (post-hoc, `>=`) and `BudgetSpendGuard`
    (pre-estimate, strict `>`):

      - `spent + pending > ceiling`: the pre-estimate arm. Callers
        pass `pending_usd` = the next call's estimated ceiling (plus
        any in-conduct actuals they carry), and a projection landing
        exactly ON the ceiling is the last call the envelope affords,
        so only strictly-over refuses.
      - `pending == 0 and spent >= ceiling`: the post-hoc arm.
        Post-hoc callers pass no pending figure, so "exactly
        exhausted" must refuse the NEXT call (`>` alone would let a
        balance sitting exactly at the ceiling keep spending forever).

    `as_of` is the triggering event's `occurred_at`, not wall clock,
    per the subscribers' determinism rule; a replayed event whose
    `occurred_at` predates `activated_at` sums an empty window and
    permits. A lookup ERROR propagates (fail closed), same stance as
    the per-agent gate.
    """
    envelope = await allocation_lookup.find_active()
    if envelope is None:
        return None
    spend = await spend_lookup.find_total_spend(
        window_start=envelope.activated_at,
        window_end=as_of,
    )
    projected_over = spend.usd_spent + pending_usd > envelope.ceiling_usd
    exhausted_post_hoc = pending_usd == 0.0 and spend.usd_spent >= envelope.ceiling_usd
    if projected_over or exhausted_post_hoc:
        return AllocationBreach(
            allocation_id=envelope.allocation_id,
            ceiling_usd=envelope.ceiling_usd,
            spent_usd=spend.usd_spent,
            window_start=envelope.activated_at,
        )
    return None


__all__ = [
    "AllocationBreach",
    "BudgetBreach",
    "calendar_day_window",
    "calendar_month_window",
    "find_allocation_breach",
    "find_budget_breach",
]
