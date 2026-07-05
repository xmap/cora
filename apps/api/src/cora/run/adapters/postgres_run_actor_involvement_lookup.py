"""Postgres adapter implementing `RunActorInvolvementLookup`.

Reads `proj_run_actor_involvement` for the in-flight runs a principal drives.
Consumed by the authority-revocation holder subscriber (K3) via the
`Kernel.run_actor_involvement_lookup` port. Reads the replicated projection
directly through the shared asyncpg pool, per the same cross-BC-read guidance
the ClearanceLookup adapter follows.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from uuid import UUID

import asyncpg

_RUNS_DRIVEN_BY_SQL = """
SELECT run_id
FROM proj_run_actor_involvement
WHERE principal_id = $1
  AND status IN ('Running', 'Held')
ORDER BY created_at, run_id
"""


class PostgresRunActorInvolvementLookup:
    """asyncpg-backed `RunActorInvolvementLookup` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def runs_driven_by(self, principal_id: UUID) -> list[UUID]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_RUNS_DRIVEN_BY_SQL, principal_id)
        return [row["run_id"] for row in rows]


__all__ = ["PostgresRunActorInvolvementLookup"]
