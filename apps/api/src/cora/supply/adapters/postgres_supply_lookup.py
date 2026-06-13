"""Postgres adapter implementing `SupplyLookup` over `proj_supply_summary`.

Consumed by Run BC's `start_run` handler, Operation BC's
`start_procedure` handler, and Data BC's `register_distribution`
handler via the `Kernel.supply_lookup` port. Reads the projection's
`(supply_id, kind, name, status, facility_code)` columns; returns
Supplies grouped by kind (Run + Operation), or per-supply-id
(Data BC).

## Why query the projection (not the event store)

Same rationale as `PostgresClearanceLookup`: cross-BC integration at
command time should go through a replicated read model, not a
synchronous call to the upstream aggregate. `proj_supply_summary` is
a denormalized cross-stream view maintained by the projection worker.
The lookup adapter reads it directly via the shared asyncpg pool.

## Query shapes

### find_supplies_by_kind (Run + Operation pre-flight gate)

Single SELECT with a single ANY() match over the indexed `kind`
column plus an explicit `Decommissioned` exclusion. The projection
retains Decommissioned rows (the partial UNIQUE INDEX on
`(facility_code, COALESCE(containing_asset_id::text, ''), kind, name)`
per [[project_deregister_supply_design]] excludes Decommissioned from
UNIQUENESS, not from reads); this SELECT excludes them at read time
so tombstoned Supplies do not contribute to gate satisfaction.

```sql
SELECT supply_id, kind, name, status, facility_code
FROM proj_supply_summary
WHERE kind = ANY($1) AND status != 'Decommissioned'
ORDER BY kind, registered_at, supply_id
```

### lookup (Data BC register_distribution)

Single SELECT by `supply_id` returning every status (including
Decommissioned). The consumer's decider partitions on `status` if
it needs to distinguish lifecycle states; register_distribution
intentionally binds against any status so archival-only Supplies
can carry Distributions. Mirrors `PostgresAssetLookup.lookup`
shape.

```sql
SELECT supply_id, kind, name, status, facility_code
FROM proj_supply_summary
WHERE supply_id = $1
LIMIT 1
```

### find_supplies_by_name (Data BC default-storage-supply bootstrap)

Single SELECT by `(name, facility_code, kind)` with the same
`Decommissioned` exclusion as `find_supplies_by_kind`: the Data BC
lifespan bootstrap resolves its default storage Supply by the
operator-readable `name` column scoped to the self-facility and to
`kind = 'Storage'`, and a tombstoned same-name Supply must not
resolve as the default. Returns every matching live row so the
caller can distinguish no-match, ambiguous-match, and not-Available.

```sql
SELECT supply_id, kind, name, status, facility_code
FROM proj_supply_summary
WHERE name = $1 AND facility_code = $2 AND kind = $3
  AND status != 'Decommissioned'
ORDER BY registered_at, supply_id
```
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections.abc import Mapping
from typing import Any
from uuid import UUID

import asyncpg

from cora.infrastructure.ports.supply_lookup import SupplyLookupResult

_FIND_SUPPLIES_BY_KIND_SQL = """
SELECT supply_id, kind, name, status, facility_code
FROM proj_supply_summary
WHERE kind = ANY($1) AND status != 'Decommissioned'
ORDER BY kind, registered_at, supply_id
"""

_LOOKUP_BY_ID_SQL = """
SELECT supply_id, kind, name, status, facility_code
FROM proj_supply_summary
WHERE supply_id = $1
LIMIT 1
"""

_FIND_SUPPLIES_BY_NAME_SQL = """
SELECT supply_id, kind, name, status, facility_code
FROM proj_supply_summary
WHERE name = $1 AND facility_code = $2 AND kind = $3
  AND status != 'Decommissioned'
ORDER BY registered_at, supply_id
"""


class PostgresSupplyLookup:
    """asyncpg-backed `SupplyLookup` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_supplies_by_kind(
        self,
        *,
        kinds: frozenset[str],
    ) -> Mapping[str, list[SupplyLookupResult]]:
        if not kinds:
            return {}
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _FIND_SUPPLIES_BY_KIND_SQL,
                sorted(kinds),
            )
        grouped: dict[str, list[SupplyLookupResult]] = {}
        for row in rows:
            ref = _row_to_reference(row)
            grouped.setdefault(ref.kind, []).append(ref)
        return grouped

    async def lookup(self, supply_id: UUID) -> SupplyLookupResult | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_LOOKUP_BY_ID_SQL, supply_id)
        if row is None:
            return None
        return _row_to_reference(row)

    async def find_supplies_by_name(
        self,
        *,
        name: str,
        facility_code: str,
        kind: str,
    ) -> list[SupplyLookupResult]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_FIND_SUPPLIES_BY_NAME_SQL, name, facility_code, kind)
        return [_row_to_reference(row) for row in rows]


def _row_to_reference(row: Any) -> SupplyLookupResult:
    return SupplyLookupResult(
        supply_id=row["supply_id"],
        kind=str(row["kind"]),
        name=str(row["name"]),
        status=str(row["status"]),
        facility_code=str(row["facility_code"]),
    )
