"""Postgres adapter implementing `CapabilityLookup` over `proj_recipe_capability_summary`.

Consumed by Equipment BC's `get_asset_integration_view` handler via
the `Kernel.capability_lookup` port. Reads the projection's
`(capability_id, code, name, status, required_affordances)` columns;
returns every non-Deprecated Capability whose required_affordances are
covered by the passed affordance set.

## Query shape

Single SELECT with two filters: text[] subset containment via the `<@`
operator (the projection's `required_affordances` must be a subset of
the affordance set the caller passes), plus status in
`{Defined, Versioned}`. Sorted by `code` ascending for deterministic
downstream serialization.

Empty `affordances` is correct semantically: only Capabilities with
empty `required_affordances` match. asyncpg materializes the empty
frozenset as `'{}'::text[]`, which `<@` accepts cleanly.

## Why query the projection (not the event store)

Per modern DDD guidance: cross-BC integration at command time should
go through a replicated read model, not a synchronous call to the
upstream aggregate. `proj_recipe_capability_summary` is exactly that:
a denormalized view maintained by Recipe's projection worker. The
lookup adapter reads it directly via the shared asyncpg pool.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Any

import asyncpg

from cora.infrastructure.ports.capability_lookup import CapabilityLookupResult

_FIND_APPLICABLE_BY_AFFORDANCES_SQL = """
SELECT capability_id, code, name, status
FROM proj_recipe_capability_summary
WHERE required_affordances <@ $1::text[]
  AND status IN ('Defined', 'Versioned')
ORDER BY code ASC
"""


class PostgresCapabilityLookup:
    """asyncpg-backed `CapabilityLookup` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_applicable_by_affordances(
        self,
        affordances: frozenset[str],
    ) -> list[CapabilityLookupResult]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _FIND_APPLICABLE_BY_AFFORDANCES_SQL,
                sorted(affordances),
            )
        return [_row_to_reference(row) for row in rows]


def _row_to_reference(row: Any) -> CapabilityLookupResult:
    return CapabilityLookupResult(
        capability_id=row["capability_id"],
        code=str(row["code"]),
        name=str(row["name"]),
        status=str(row["status"]),
    )
