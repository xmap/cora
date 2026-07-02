"""asyncpg-backed `RunActorInvolvementLookup` over `proj_run_actor_involvement`.

Reads the actor -> in-flight-runs index the kill-switch consults. Rides
the `proj_run_actor_involvement_actor_inflight_idx` partial index
(actor_id WHERE status IN Running|Held), so the query touches only
in-flight rows. DISTINCT collapses the two involvement kinds (a run the
actor both started and supervises returns once).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress at module level for the adapter.

from uuid import UUID

import asyncpg

_INFLIGHT_RUN_IDS_SQL = """
SELECT DISTINCT run_id
FROM proj_run_actor_involvement
WHERE actor_id = $1 AND status IN ('Running', 'Held')
"""


class PostgresRunActorInvolvementLookup:
    """Production `RunActorInvolvementLookup`; reads the involvement projection."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_inflight_run_ids(self, actor_id: UUID) -> frozenset[UUID]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_INFLIGHT_RUN_IDS_SQL, actor_id)
        return frozenset(row["run_id"] for row in rows)


__all__ = ["PostgresRunActorInvolvementLookup"]
