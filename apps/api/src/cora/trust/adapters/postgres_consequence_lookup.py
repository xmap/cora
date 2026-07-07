"""Postgres adapter implementing `ConsequenceLookup` over
`proj_trust_ratification_coverage`.

Consumed by Run BC's `stop_run` handler via the `Kernel.consequence_lookup` port.
Answers "is there a GRANTED Ratification covering (target_action_id,
command_name)?" so the consequence gate admits a co-signed action and refuses (+
holds) an un-co-signed one.

## Why query the projection (not the event store)

Same modern-DDD guidance as ClearanceLookup: cross-BC integration at command time
reads a replicated read model, not the upstream aggregate. The coverage
projection is a denormalized cross-stream view maintained by the projection
worker; the adapter reads it directly through the shared asyncpg pool.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from uuid import UUID

import asyncpg

_GRANTED_COVERAGE_EXISTS_SQL = """
SELECT EXISTS (
    SELECT 1
    FROM proj_trust_ratification_coverage
    WHERE target_action_id = $1
      AND command_name = $2
      AND status = 'Granted'
)
"""


class PostgresConsequenceLookup:
    """asyncpg-backed `ConsequenceLookup` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def granted_coverage_exists(
        self,
        *,
        run_id: UUID,
        command_name: str,
    ) -> bool:
        async with self._pool.acquire() as conn:
            # SELECT EXISTS(...) never yields NULL, but wrap in bool() so the
            # `-> bool` contract is honest (fetchval is typed Any) rather than
            # leaning on the file-level pyright suppression.
            return bool(await conn.fetchval(_GRANTED_COVERAGE_EXISTS_SQL, run_id, command_name))


__all__ = ["PostgresConsequenceLookup"]
