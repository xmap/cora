"""Postgres adapter implementing `ClearanceTemplateLookup`.

Reads `proj_safety_clearance_template_summary`.

Consumed by Safety BC's `version_clearance_template` handler via the
`Kernel.clearance_template_lookup` port to resolve the parent
template referenced by `supersedes_template_id` so the decider can
enforce the same-facility chain rule (L5) and the parent-exists
precondition.

## Why query the projection (not the event store)

Per modern DDD guidance (Khononov 2021, Herberto Graca 2017,
Dudycz 2024): cross-aggregate integration at command time should
go through a replicated read model, NOT a synchronous replay of
the upstream aggregate. `proj_safety_clearance_template_summary`
is exactly that: a denormalized cross-stream view maintained by
the ClearanceTemplate projection writer. The lookup adapter reads
it directly via the shared asyncpg pool.

## Query shape

Single SELECT keyed by the `template_id` primary key (LIMIT 1),
returning `None` when no row matches. Templates in every
lifecycle status are returned; the consumer decider partitions on
`status` if needed.

## Enum coercion

`status` is stored as `TEXT` and typed as `str` on the port's
`ClearanceTemplateLookupResult` (to keep
`cora.infrastructure.ports.clearance_template_lookup` import-free
of Safety BC types). The adapter still constructs
`ClearanceTemplateStatus(row["status"])` as a validation step: a
corrupted row whose `status` is not a known enum value surfaces
as `ValueError` from the adapter rather than as a silent wrong
status downstream. The validated `StrEnum` value IS-A `str`, so
the assignment into the dataclass's `str`-typed field is exact.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Any
from uuid import UUID

import asyncpg

from cora.infrastructure.ports.clearance_template_lookup import ClearanceTemplateLookupResult
from cora.safety.aggregates.clearance_template import ClearanceTemplateStatus
from cora.shared.facility_code import FacilityCode

_LOOKUP_SQL = """
SELECT template_id, facility_code, code, status, version
FROM proj_safety_clearance_template_summary
WHERE template_id = $1
LIMIT 1
"""


class PostgresClearanceTemplateLookup:
    """asyncpg-backed `ClearanceTemplateLookup` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def lookup(self, template_id: UUID) -> ClearanceTemplateLookupResult | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_LOOKUP_SQL, template_id)
        if row is None:
            return None
        return _row_to_result(row)


def _row_to_result(row: Any) -> ClearanceTemplateLookupResult:
    return ClearanceTemplateLookupResult(
        id=row["template_id"],
        facility_code=FacilityCode(row["facility_code"]).value,
        code=str(row["code"]),
        status=ClearanceTemplateStatus(row["status"]).value,
        version=int(row["version"]),
    )


__all__ = ["PostgresClearanceTemplateLookup"]
