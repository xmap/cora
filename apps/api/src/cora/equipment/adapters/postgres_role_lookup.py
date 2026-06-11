"""Postgres adapter implementing `RoleLookup` over `proj_equipment_role_summary`.

Consumed by Layer-3 cross-aggregate consumers via the
`Kernel.role_lookup` port. The 3A slice ships this adapter;
3B/3C/3D/3E wire their handlers against it.

## Why query the projection (not the event store)

Per modern DDD guidance (Khononov 2021, Herberto Graca 2017):
cross-aggregate integration at command time should go through a
replicated read model, NOT a synchronous replay of the upstream
aggregate. `proj_equipment_role_summary` is exactly that, maintained
by `RoleSummaryProjection`. The lookup adapter reads it directly via
the shared asyncpg pool.

## Query shape

Single SELECT keyed by the `role_id` primary key (LIMIT 1), returning
`None` when no row matches. Roles do not have a lifecycle FSM at 3A
(see [[project-role-aggregate-design]] Q1: deferred until Lock 14
versioning trigger), so the adapter does not filter on a status
column. When versioning lands, an `expand` parameter may select
"latest non-deprecated" semantics.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Any
from uuid import UUID

import asyncpg

from cora.infrastructure.ports.role_lookup import RoleLookupResult

_LOOKUP_SQL = """
SELECT role_id, name, required_affordances, optional_affordances
FROM proj_equipment_role_summary
WHERE role_id = $1
LIMIT 1
"""


class PostgresRoleLookup:
    """asyncpg-backed `RoleLookup` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def lookup(self, role_id: UUID) -> RoleLookupResult | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_LOOKUP_SQL, role_id)
        if row is None:
            return None
        return _row_to_result(row)


def _row_to_result(row: Any) -> RoleLookupResult:
    return RoleLookupResult(
        id=row["role_id"],
        name=str(row["name"]),
        required_affordances=frozenset(row["required_affordances"] or ()),
        optional_affordances=frozenset(row["optional_affordances"] or ()),
    )


__all__ = ["PostgresRoleLookup"]
