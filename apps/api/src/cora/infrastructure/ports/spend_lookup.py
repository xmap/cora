"""SpendLookup port: cross-BC query for an agent's recorded LLM spend.

Consumed by the Agent BC's LLM subscribers (RunDebriefer,
CautionDrafter) to gate an LLM call on the caller's declared
`AgentBudget` caps: the gate sums what the agent has already spent in
the cap's window and refuses the next call once a cap is breached
(coarse post-hoc enforcement per the tier ladder in
[[project_budget_bc_research]]). Planned consumers, not wired today:
the operator-triggered regenerate slice, and the Operation BC steering
brain at the per-call pre-estimate tier.

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

## Trust boundary (known limitation, follow-up owed)

The ledger trusts every AppendInferences-authorized producer: entry
rows carry a producer-supplied `agent_id` that is NOT bound to the
calling principal, so a hostile or buggy authorized producer could
inflate another agent's recorded spend and deny it service (inflation
only; overspend cannot be manufactured this way). Under a real Trust
policy the AppendInferences grant is the control. Binding `agent_id`
to the calling principal (or persisting the envelope principal on the
row and summing self-reported rows only) is the recorded follow-up.

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


class SpendLookup(Protocol):
    """Cross-BC port: sum an agent's recorded LLM spend in a window."""

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


__all__ = [
    "AlwaysZeroSpendLookup",
    "SpendLookup",
    "SpendLookupResult",
]
