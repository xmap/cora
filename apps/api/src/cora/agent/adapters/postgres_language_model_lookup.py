"""PostgresLanguageModelLookup: the catalog identity lookup over the projection.

The agent BC ships the production adapter because it owns the fact:
`proj_language_model_summary` is this BC's read model of its own
aggregate. Latest-entry-wins on identity collisions (a model
re-registered after a deprecation supersedes the dead entry as the
current governance posture), which the `ORDER BY created_at DESC`
encodes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.infrastructure.ports.language_model_lookup import LanguageModelLookupResult

if TYPE_CHECKING:
    import asyncpg

_FIND_SQL = """
SELECT language_model_id, status, data_tier, archivability, snapshot_pin
FROM proj_language_model_summary
WHERE provider = $1 AND model = $2
ORDER BY created_at DESC
LIMIT 1
"""


class PostgresLanguageModelLookup:
    """`LanguageModelLookup` over `proj_language_model_summary`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_by_model(
        self,
        *,
        provider: str,
        model: str,
    ) -> LanguageModelLookupResult | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_FIND_SQL, provider, model)
        if row is None:
            return None
        return LanguageModelLookupResult(
            language_model_id=row["language_model_id"],
            status=row["status"],
            data_tier=row["data_tier"],
            archivability=row["archivability"],
            snapshot_pin=row["snapshot_pin"],
        )


__all__ = ["PostgresLanguageModelLookup"]
