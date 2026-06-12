"""Postgres adapter implementing `ClearanceLookup` over `proj_safety_clearance_summary`.

Consumed by Run BC's `start_run` handler via the
`Kernel.clearance_lookup` port. Reads the projection's UUID[] +
status columns; returns every clearance whose bindings reference
the Run's scope `(run_id, subject_id, asset_ids)`.

## Why query the projection (not the event store)

Per modern DDD guidance (Khononov 2021, Herberto Graça 2017,
Dudycz 2024): cross-BC integration at command time should go
through a replicated read model, NOT a synchronous call to the
upstream aggregate. CORA's `proj_safety_clearance_summary` is
exactly that: a denormalized cross-stream view maintained by the
projection worker. The lookup adapter reads it directly via the
shared asyncpg pool.

## Query shape

Single SELECT with a three-way OR over the indexed UUID[] columns
(GIN-indexed in the projection migration):

```sql
WHERE $1 = ANY(run_binding_ids)
   OR ($2::uuid IS NOT NULL AND $2 = ANY(subject_binding_ids))
   OR $3 && asset_binding_ids
```

`subject_id` is nullable (calibration / dark-field runs); the IS
NOT NULL guard skips the subject_binding_ids match when subject_id
is None. `asset_ids` may be empty (rare but valid); the `&&`
overlap operator handles empty arrays correctly.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Any
from uuid import UUID

import asyncpg

from cora.infrastructure.ports.clearance_lookup import ClearanceLookupResult

_FIND_REFERENCING_RUN_SQL = """
SELECT clearance_id, status, template_id, template_code, facility_code
FROM proj_safety_clearance_summary
WHERE $1 = ANY(run_binding_ids)
   OR ($2::uuid IS NOT NULL AND $2 = ANY(subject_binding_ids))
   OR $3::uuid[] && asset_binding_ids
ORDER BY registered_at, clearance_id
"""


class PostgresClearanceLookup:
    """asyncpg-backed `ClearanceLookup` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_referencing_run(
        self,
        *,
        run_id: UUID,
        subject_id: UUID | None,
        asset_ids: frozenset[UUID],
    ) -> list[ClearanceLookupResult]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _FIND_REFERENCING_RUN_SQL,
                run_id,
                subject_id,
                # sorted for deterministic query plan; ARRAY casts via
                # asyncpg are zero-copy for native UUID[] columns
                sorted(asset_ids, key=str),
            )
        return [_row_to_reference(row) for row in rows]


def _row_to_reference(row: Any) -> ClearanceLookupResult:
    return ClearanceLookupResult(
        clearance_id=row["clearance_id"],
        status=str(row["status"]),
        template_id=row["template_id"],
        template_code=str(row["template_code"]),
        facility_code=str(row["facility_code"]),
    )
