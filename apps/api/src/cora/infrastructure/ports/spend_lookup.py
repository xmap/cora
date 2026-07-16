"""SpendLookup port: cross-BC query for an agent's recorded LLM spend.

Consumed by the Agent BC's LLM subscribers (RunDebriefer,
CautionDrafter) to gate an LLM call on the caller's declared
`AgentBudget` caps: the gate sums what the agent has already spent in
the cap's window and refuses the next call once a cap is breached
(coarse post-hoc enforcement per the tier ladder in
[[project_budget_bc_research]]), and by the Agent BC's
`BudgetSpendGuard`, the pre-call half that gates the Operation BC
steering brain at the per-call pre-estimate tier. The
operator-triggered regenerate slice stays deliberately ungated (an
accountable human asked; the call is still metered and debited).

## Convention

Same shape as the `start_run` lookup family (`ClearanceLookup`,
`SupplyLookup`, ...): a consumer-shaped Protocol + frozen result VO +
an always-pass test stub, living in `cora.infrastructure.ports` for
neutral access. The Decision BC ships the production adapter
(`cora.decision.adapters.PostgresSpendLookup`) because it owns the
durable spend fact: `entries_decision_inferences`, where each LLM
call's provenance row carries `agent_id`, `occurred_at`, token counts,
and `cost_usd`.

## Window semantics

The port is window-agnostic: the CONSUMER computes `[window_start,
window_end)` (half-open) for the cap it enforces, calendar month (UTC)
for `monthly_usd_cap`, calendar day (UTC) for `daily_token_cap`, and
the adapter just sums inside the bounds. Keeping window policy out of
the adapter means a future award-window allocation (activation and
expiry bound to run lifecycle events rather than the calendar) is a
consumer-side change only.

## Trust boundary

Agent-attributed rows are principal-bound at the write path: the
`append_inferences` handler rejects any entry whose `agent_id`
differs from the calling principal (`InferenceAgentMismatchError`,
403), so a producer can record spend against itself only, never
inflate another agent's balance. All internal recorders (both LLM
subscribers and the regenerate slice, via
`DelegatingInferenceRecorder`) self-report with the agent's own
actor id as principal. Residual trust surface: `agent_name` /
`agent_description` remain unverified display strings, and a future
on-behalf-of recorder (the Tier 1.5 steering-spend design) needs an
explicit delegation mechanism rather than a relaxation of the
binding.

## Known undercount (accepted for the coarse tier)

Rows with `cost_usd IS NULL` (pre-migration history) sum as $0, and
cache-read/cache-write tokens are not persisted on the entry, so
`tokens_spent` counts input + output only. Both make the gate slightly
PERMISSIVE, never spuriously blocking, which is the right failure
direction for a coarse post-hoc tier. The leak-free reserve-post-void
tier owns exactness (deferred; see [[project_budget_bc_research]]).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class SpendLookupResult:
    """Summed spend for one agent inside one window.

    `usd_spent` sums `cost_usd` (NULLs as $0); `tokens_spent` sums
    input + output tokens; `call_count` counts inference rows. The
    echoed window bounds make gate log lines self-describing.
    """

    agent_id: UUID
    window_start: datetime
    window_end: datetime
    usd_spent: float
    tokens_spent: int
    call_count: int


@dataclass(frozen=True)
class TotalSpendResult:
    """The deployment's instance-total spend inside one window.

    No agent axis: the sum covers EVERY costed inference row,
    agent-attributed and operator-attributed alike, because the
    allocation envelope covers the whole instrument's LLM spend (one
    balance per beamline). The echoed window bounds make gate and
    seal log lines self-describing.
    """

    window_start: datetime
    window_end: datetime
    usd_spent: float
    call_count: int


class SpendLookup(Protocol):
    """Cross-BC port: sum recorded LLM spend in a window (per agent or instance-total)."""

    async def find_agent_spend(
        self,
        *,
        agent_id: UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> SpendLookupResult:
        """Return the agent's summed spend for `[window_start, window_end)`.

        An agent with no recorded calls in the window returns a zero
        row (never None): "no spend" and "unknown agent" are the same
        answer to a budget gate.
        """
        ...

    async def find_total_spend(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> TotalSpendResult:
        """Return the instance-total spend for `[window_start, window_end)`.

        Sums ALL rows regardless of `agent_id` (including agentless,
        operator-attributed rows): the allocation envelope's one
        balance covers the whole instrument. A window with no
        recorded calls returns a zero row (never None), matching the
        per-agent contract.
        """
        ...


class AlwaysZeroSpendLookup:
    """Test-default stub: every agent has spent nothing.

    Mirrors `AlwaysCoveredClearanceLookup`'s role: tests that don't
    exercise budget gating get this stub from the kernel defaults, so
    a declared cap never blocks them. Tests that exercise the gate
    override with the real adapter (`PostgresSpendLookup`) or an
    in-test fake returning a chosen spend.
    """

    async def find_agent_spend(
        self,
        *,
        agent_id: UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> SpendLookupResult:
        return SpendLookupResult(
            agent_id=agent_id,
            window_start=window_start,
            window_end=window_end,
            usd_spent=0.0,
            tokens_spent=0,
            call_count=0,
        )

    async def find_total_spend(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> TotalSpendResult:
        return TotalSpendResult(
            window_start=window_start,
            window_end=window_end,
            usd_spent=0.0,
            call_count=0,
        )


__all__ = [
    "AlwaysZeroSpendLookup",
    "SpendLookup",
    "SpendLookupResult",
    "TotalSpendResult",
]
