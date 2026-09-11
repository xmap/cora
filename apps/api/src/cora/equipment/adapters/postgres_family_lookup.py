"""Postgres adapter implementing `FamilyLookup` over `proj_equipment_family_summary`.

Consumed by Layer-3 cross-aggregate consumers via the
`Kernel.family_lookup` port. The 3B slice ships this adapter; 3D
wires its `bind_plan_role` handler against it for the role_kind
satisfaction-check path (Lock 17 ANY-single-family disjunction).

## Enum coercion

`status` is stored as a `TEXT` column and typed as a `Literal` alias
on the port's `FamilyLookupResult` (to keep
`cora.infrastructure.ports.family_lookup` import-free of Equipment
BC types). The adapter constructs `FamilyStatus(row["status"])` as a
validation step: a corrupted row whose `status` is not a known enum
value surfaces as `ValueError` from the adapter rather than as a
silent wrong-status match downstream. `.value` on the validated
member narrows to exactly the port's alias, so no cast is needed.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Any
from uuid import UUID

import asyncpg

from cora.equipment.aggregates.family import FamilyStatus
from cora.infrastructure.ports.family_lookup import FamilyLookupResult

_LOOKUP_SQL = """
SELECT family_id, name, status, affordances, presents_as
FROM proj_equipment_family_summary
WHERE family_id = $1
LIMIT 1
"""


class PostgresFamilyLookup:
    """asyncpg-backed `FamilyLookup` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def lookup(self, family_id: UUID) -> FamilyLookupResult | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_LOOKUP_SQL, family_id)
        if row is None:
            return None
        return _row_to_result(row)


def _row_to_result(row: Any) -> FamilyLookupResult:
    return FamilyLookupResult(
        id=row["family_id"],
        name=str(row["name"]),
        status=FamilyStatus(row["status"]).value,
        affordances=frozenset(row["affordances"] or ()),
        presents_as=frozenset(row["presents_as"] or ()),
    )


__all__ = ["PostgresFamilyLookup"]
