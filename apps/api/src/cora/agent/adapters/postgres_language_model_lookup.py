"""PostgresLanguageModelLookup: the catalog identity lookup over the projection.

The agent BC ships the production adapter because it owns the fact:
`proj_agent_language_model_summary` is this BC's read model of its own
aggregate. The lookup answers the GATE's question, the newest APPROVED
entry for the identity, so an unapproved or deprecated newer entry can
never shadow an older Approved one into refusing agent registration,
and deprecating a mistaken duplicate restores the previous Approved
entry. The `language_model_id DESC` tiebreak makes equal-created_at
rows deterministic.
"""

from __future__ import annotations

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from typing import TYPE_CHECKING

from cora.infrastructure.ports.language_model_lookup import LanguageModelLookupResult

if TYPE_CHECKING:
    import asyncpg

_FIND_SQL = """
SELECT language_model_id, status, data_tier, archivability, snapshot_pin
FROM proj_agent_language_model_summary
WHERE provider = $1 AND model = $2 AND status = 'Approved'
ORDER BY created_at DESC, language_model_id DESC
LIMIT 1
"""


class PostgresLanguageModelLookup:
    """`LanguageModelLookup` over `proj_agent_language_model_summary`."""

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
