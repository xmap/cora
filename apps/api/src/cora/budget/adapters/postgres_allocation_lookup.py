"""PostgresAllocationLookup: the Active-envelope lookup over the projection.

The budget BC ships the production adapter because it owns the fact:
`proj_budget_allocation_summary` is this BC's read model of its own
aggregate. The lookup answers the GATE's question, the deployment's
single Active envelope. At-most-one-Active is enforced best-effort at
activate time (activate_allocation refuses with
AllocationAlreadyActiveError when another envelope is already Active);
should an overlap slip through that projection-read race, the newest
`activated_at` wins (the most recently opened window is the operator's
current intent) with `allocation_id DESC` making equal-timestamp rows
deterministic, per the port contract.
"""

from __future__ import annotations

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from typing import TYPE_CHECKING

from cora.infrastructure.ports.allocation_lookup import AllocationLookupResult

if TYPE_CHECKING:
    import asyncpg

_FIND_ACTIVE_SQL = """
SELECT allocation_id, ceiling_usd, activated_at, campaign_id
FROM proj_budget_allocation_summary
WHERE status = 'Active'
ORDER BY activated_at DESC, allocation_id DESC
LIMIT 1
"""


class PostgresAllocationLookup:
    """`AllocationLookup` over `proj_budget_allocation_summary`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_active(self) -> AllocationLookupResult | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_FIND_ACTIVE_SQL)
        if row is None:
            return None
        return AllocationLookupResult(
            allocation_id=row["allocation_id"],
            ceiling_usd=row["ceiling_usd"],
            activated_at=row["activated_at"],
            campaign_id=row["campaign_id"],
        )


__all__ = ["PostgresAllocationLookup"]
