"""Postgres adapter implementing `EnclosureLookup` over `proj_enclosure_summary`.

Consumed by cross-BC callers (Run / Procedure pre-flight, future
interlock gates) via the `Kernel.enclosure_lookup` port to ask "is
this enclosure permitted?" without binding to the Enclosure BC's
internal types. Reads the projection's primary-key row for the
single-id arm and filters by `containing_asset_id` for the
set-returning arm; returns bare `str` / bare `UUID` shapes per the
port's `cora.infrastructure.ports` `depends_on=[]` posture.

## Why query the projection (not the event store)

Per modern DDD guidance (Khononov 2021, Herberto Graca 2017,
Dudycz 2024): cross-aggregate integration at command time should go
through a replicated read model, NOT a synchronous replay of the
upstream aggregate. `proj_enclosure_summary` is exactly that: a
denormalized cross-stream view maintained by the projection worker.
The lookup adapter reads it directly via the shared asyncpg pool.

## Query shape

`lookup` issues a single SELECT keyed by the `enclosure_id` primary
key (LIMIT 1), returning `None` when no row matches. Enclosures in
every `lifecycle` (`Active`, `Decommissioned`) and every
`permit_status` are returned; the consumer partitions on both axes.
`find_for_assets` issues a SELECT filtered by
`containing_asset_id = ANY($1) AND lifecycle = 'Active'` (hitting the
`proj_enclosure_summary_containing_asset_idx` partial index
exactly) so tombstoned enclosures do not gate runs; empty input
short-circuits to `[]` without touching the pool.

## Enum coercion

`permit_status` and `lifecycle` are stored as `TEXT` columns and are
typed as `str` on the port's `EnclosureLookupResult` (to keep
`cora.infrastructure.ports.enclosure_lookup` import-free of
Enclosure BC types). The adapter still constructs
`EnclosurePermitStatus(row["permit_status"])` and
`EnclosureLifecycle(row["lifecycle"])` as a validation step: a
corrupted row whose value is not a known enum surfaces as
`ValueError` from the adapter rather than as a silent wrong-status
match downstream. Both validated `StrEnum` values are `IS-A str`,
so assignment into the dataclass's `str`-typed fields is exact.

## Timestamp coercion

`last_observed_at` is stored as `TIMESTAMPTZ` and is typed as
`str | None` on the port surface (ISO 8601 string when present,
`None` when no observation has landed). The adapter formats the
asyncpg `datetime` via `.isoformat()` so consumers receive a
parse-stable string without importing `datetime` through the port.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Any
from uuid import UUID

import asyncpg

from cora.enclosure.aggregates.enclosure.state import (
    EnclosureLifecycle,
    EnclosurePermitStatus,
)
from cora.infrastructure.ports.enclosure_lookup import EnclosureLookupResult

_LOOKUP_SQL = """
SELECT enclosure_id, name, containing_asset_id, permit_status, lifecycle,
       last_observed_at, last_source_kind, last_source_id
FROM proj_enclosure_summary
WHERE enclosure_id = $1
LIMIT 1
"""

_FIND_FOR_ASSETS_SQL = """
SELECT enclosure_id, name, containing_asset_id, permit_status, lifecycle,
       last_observed_at, last_source_kind, last_source_id
FROM proj_enclosure_summary
WHERE containing_asset_id = ANY($1)
  AND lifecycle = 'Active'
"""


class PostgresEnclosureLookup:
    """asyncpg-backed `EnclosureLookup` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def lookup(self, enclosure_id: UUID) -> EnclosureLookupResult | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_LOOKUP_SQL, enclosure_id)
        if row is None:
            return None
        return _row_to_reference(row)

    async def find_for_assets(self, *, asset_ids: frozenset[UUID]) -> list[EnclosureLookupResult]:
        if not asset_ids:
            return []
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_FIND_FOR_ASSETS_SQL, sorted(asset_ids))
        return [_row_to_reference(r) for r in rows]


def _format_observed_at(raw: Any) -> str | None:
    if raw is None:
        return None
    return raw.isoformat()


def _row_to_reference(row: Any) -> EnclosureLookupResult:
    return EnclosureLookupResult(
        enclosure_id=row["enclosure_id"],
        name=str(row["name"]),
        containing_asset_id=row["containing_asset_id"],
        permit_status=EnclosurePermitStatus(row["permit_status"]),
        lifecycle=EnclosureLifecycle(row["lifecycle"]),
        observed_at=_format_observed_at(row["last_observed_at"]),
        source_kind=row["last_source_kind"],
        source_id=row["last_source_id"],
    )


__all__ = ["PostgresEnclosureLookup"]
