"""Postgres adapter implementing `AssemblyLookup` over `proj_equipment_assembly_summary`.

Consumed by Layer-3 cross-aggregate consumers via the
`Kernel.assembly_lookup` port. Wired by 3D's `bind_plan_role`
handler so the role_kind satisfaction check ORs-in the Assembly
path on top of the Family disjunction (see [[project-role-aggregate-design]]
sub-slice 3C/3D for the worked Microscope-Assembly example).

## Enum coercion

`status` is stored as a `TEXT` column and typed as a `Literal` alias
on the port's `AssemblyLookupResult` (to keep
`cora.infrastructure.ports.assembly_lookup` import-free of Equipment
BC types). The adapter constructs `AssemblyStatus(row["status"])` as
a validation step: a corrupted row whose `status` is not a known
enum value surfaces as `ValueError` from the adapter rather than as
a silent wrong-status match downstream. `.value` on the validated
member narrows to exactly the port's alias, so no cast is needed.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Any
from uuid import UUID

import asyncpg

from cora.equipment.aggregates.assembly import AssemblyStatus
from cora.infrastructure.ports.assembly_lookup import AssemblyLookupResult

_LOOKUP_SQL = """
SELECT assembly_id, name, status, presents_as
FROM proj_equipment_assembly_summary
WHERE assembly_id = $1
LIMIT 1
"""


class PostgresAssemblyLookup:
    """asyncpg-backed `AssemblyLookup` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def lookup(self, assembly_id: UUID) -> AssemblyLookupResult | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_LOOKUP_SQL, assembly_id)
        if row is None:
            return None
        return _row_to_result(row)


def _row_to_result(row: Any) -> AssemblyLookupResult:
    return AssemblyLookupResult(
        id=row["assembly_id"],
        name=str(row["name"]),
        status=AssemblyStatus(row["status"]).value,
        presents_as=frozenset(row["presents_as"] or ()),
    )


__all__ = ["PostgresAssemblyLookup"]
