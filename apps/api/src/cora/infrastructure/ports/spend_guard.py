"""SpendGuard port: pre-call budget permission for an agent's next LLM call.

The per-call pre-estimate tier of the enforcement ladder in
[[project_budget_bc_research]]: BEFORE an autonomous caller invokes a
model, the guard is asked whether the projected spend (the ledger
baseline, plus the caller's own not-yet-posted in-conduct actuals, plus
the next call's estimated ceiling) would breach the agent's declared
caps, and a refusal stops the call before any tokens are bought. The
coarse post-hoc gate (`cora.agent._budget_gate`) bounds overspend to one
in-flight call per caller; this tier tightens the bound to one call's
estimate error plus whatever concurrent conducts race in (the leak-free
reserve tier owns that residual). This is the minimum for an autonomous
caller whose single call could exhaust a balance.

## Convention

Same neutral-port shape as `SpendLookup`: a consumer-shaped Protocol +
an always-pass test stub living in `cora.infrastructure.ports`, with the
production adapter shipped by the BC that owns the policy fact (the Agent
BC's `BudgetSpendGuard`, which reads the caller's `AgentBudget` caps and
sums recorded spend through `SpendLookup`). The Operation BC's steering
brain consults the guard without importing the Agent BC.

## Failure direction

A `refusal_reason` of None permits. The guard REFUSES when the projected
spend would exceed a declared cap, so its error is one-sided when the
estimate is a true ceiling: it may refuse a call the balance could just
barely afford, never permit one it cannot. An unpriced model yields no
ceiling, but the caller still consults the guard with zero estimates, so
the lifecycle stop and the already-over-cap refusal never depend on
pricing coverage. A guard ERROR propagates out of the conduct invocation
entirely (only Decide-family faults are folded into deferred decisions),
which is the fail-closed direction: wrapping the guard in a permissive
except would let a database outage disable enforcement silently.
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID


class SpendGuard(Protocol):
    """Pre-call check: may this agent spend up to the estimated ceiling now?"""

    async def refusal_reason(
        self,
        *,
        agent_id: UUID,
        estimated_cost_usd: float,
        estimated_tokens: int,
        as_of: datetime,
    ) -> str | None:
        """Return None to permit, or one human-readable refusal sentence.

        The reason lands on the caller's deferred-decision record, so it
        should say which cap would be breached and by roughly how much.
        """
        ...


class AlwaysGrantedSpendGuard:
    """Test-default stub: every call is permitted.

    Mirrors `AlwaysZeroSpendLookup`: tests that don't exercise the
    pre-estimate tier get this from the kernel defaults, so a declared
    cap never blocks them. The composition root binds the real
    `BudgetSpendGuard` in production.
    """

    async def refusal_reason(
        self,
        *,
        agent_id: UUID,
        estimated_cost_usd: float,
        estimated_tokens: int,
        as_of: datetime,
    ) -> str | None:
        return None


__all__ = [
    "AlwaysGrantedSpendGuard",
    "SpendGuard",
]
