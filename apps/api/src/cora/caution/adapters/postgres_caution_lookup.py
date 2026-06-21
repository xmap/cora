"""Postgres adapter implementing `CautionLookup` over `proj_caution_summary`.

Consumed by Run BC's `start_run` handler via the
`Kernel.caution_lookup` port. Reads the projection's
`(target_kind, target_id, status, severity)` columns; returns every
Active caution whose target references the Run's scope
`(asset_ids, procedure_ids)` at or above `min_severity`.

## Why query the projection (not the event store)

Per modern DDD guidance (Khononov 2021, Herberto Graça 2017,
Dudycz 2024): cross-BC integration at command time should go
through a replicated read model, NOT a synchronous call to the
upstream aggregate. CORA's `proj_caution_summary` is exactly that:
a denormalized cross-stream view maintained by the projection
worker. The lookup adapter reads it directly via the shared
asyncpg pool.

## Query shape

Single SELECT with three filters: target match (Asset OR Procedure),
status=Active, and a severity-ordinal threshold computed Python-side
from `min_severity` (Notice->0 / Caution->1 / Warning->2). The
projection's `proj_caution_summary_target_active_idx` partial index
on `(target_kind, target_id) WHERE status = 'Active'` covers the hot
path.

Empty `asset_ids` and `procedure_ids` arrays are handled cleanly by
`ANY($N::uuid[])`: an empty array yields no matches, which is the
correct semantic (a Run with no Asset/Procedure scope can't surface
any cautions).

## Severity ordering

The result is sorted severity-descending (Warning first, then
Caution, then Notice when the threshold permits it) so the most
urgent items lead the snapshot. Tiebreak on `registered_at` then
`caution_id` for deterministic output across replays.

## Hierarchy propagation is NOT walked here

`propagate_to_children` is stored as-is on the projection row but
the adapter does NOT walk `Asset.parent_id` chains. Watch item #8
in the Caution design memo defers the propagation projection denorm
until a concrete need surfaces. Today the adapter returns only
directly-targeted cautions.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Any
from uuid import UUID

import asyncpg

from cora.infrastructure.ports.caution_lookup import CautionLookupResult, MinSeverity

_FIND_ACTIVE_FOR_RUN_SQL = """
SELECT caution_id,
       target_kind,
       target_id,
       category,
       severity,
       LEFT(text, 200)       AS text_excerpt,
       LEFT(workaround, 200) AS workaround_excerpt
FROM proj_caution_summary
WHERE status = 'Active'
  AND (
    (target_kind = 'Asset'     AND target_id = ANY($1::uuid[]))
    OR (target_kind = 'Procedure' AND target_id = ANY($2::uuid[]))
  )
  AND (CASE severity
         WHEN 'Notice'  THEN 0
         WHEN 'Caution' THEN 1
         WHEN 'Warning' THEN 2
       END) >= $3
ORDER BY
  CASE severity
    WHEN 'Warning' THEN 0
    WHEN 'Caution' THEN 1
    WHEN 'Notice'  THEN 2
  END,
  registered_at,
  caution_id
"""

_SEVERITY_ORDINAL: dict[str, int] = {
    "Notice": 0,
    "Caution": 1,
    "Warning": 2,
}

# CautionPromoter retirement-memory guard (Lock 5). Cold read: filtered on
# status='Retired' (not covered by the Active partial index), but the promoter
# runs it only for an otherwise-promotable proposal (rare), so a small
# proj_caution_summary scan is acceptable at pilot scale; no new index until a
# consumer needs retired-by-target at a hotter cadence.
_FIND_RETIRED_FOR_TARGET_SQL = """
SELECT caution_id,
       target_kind,
       target_id,
       category,
       severity,
       LEFT(text, 200)       AS text_excerpt,
       LEFT(workaround, 200) AS workaround_excerpt
FROM proj_caution_summary
WHERE status = 'Retired'
  AND target_kind = $1
  AND target_id = $2
  AND category = $3
  AND authored_by = $4
ORDER BY registered_at, caution_id
"""


class PostgresCautionLookup:
    """asyncpg-backed `CautionLookup` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_active_for_run(
        self,
        *,
        asset_ids: frozenset[UUID],
        procedure_ids: frozenset[UUID],
        min_severity: MinSeverity = "Caution",
    ) -> list[CautionLookupResult]:
        # Resolve the severity threshold to an ordinal Python-side so
        # the SQL stays a single SELECT with a CASE-on-severity in the
        # WHERE clause. Direct indexing fails loud on an unknown value;
        # the port's `MinSeverity` Literal constrains callers at type
        # time, so a KeyError here means the caller bypassed typing.
        threshold = _SEVERITY_ORDINAL[min_severity]
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _FIND_ACTIVE_FOR_RUN_SQL,
                # sorted for deterministic query plan; ARRAY casts via
                # asyncpg are zero-copy for native UUID[] columns
                sorted(asset_ids, key=str),
                sorted(procedure_ids, key=str),
                threshold,
            )
        return [_row_to_reference(row) for row in rows]

    async def find_retired_for_target(
        self,
        *,
        target_kind: str,
        target_id: UUID,
        category: str,
        authored_by: UUID,
    ) -> list[CautionLookupResult]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _FIND_RETIRED_FOR_TARGET_SQL,
                target_kind,
                target_id,
                category,
                authored_by,
            )
        return [_row_to_reference(row) for row in rows]


def _row_to_reference(row: Any) -> CautionLookupResult:
    return CautionLookupResult(
        caution_id=row["caution_id"],
        target_kind=str(row["target_kind"]),
        target_id=row["target_id"],
        category=str(row["category"]),
        severity=str(row["severity"]),
        text_excerpt=str(row["text_excerpt"]),
        workaround_excerpt=str(row["workaround_excerpt"]),
    )
