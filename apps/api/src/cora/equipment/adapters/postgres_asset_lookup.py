"""Postgres adapter implementing `AssetLookup` over `proj_equipment_asset_summary`.

Consumed by cross-BC handlers via the `Kernel.asset_lookup` port to
validate cross-aggregate Asset references at command time. First
consumer is Supply BC's `register_supply` handler (Session 5 Slice
7B): it resolves `command.containing_asset_id` to an
`AssetLookupResult` and threads the result into the decider.

## Why query the projection (not the event store)

Per modern DDD guidance (Khononov 2021, Herberto Graca 2017,
Dudycz 2024): cross-aggregate integration at command time should
go through a replicated read model, NOT a synchronous replay of
the upstream aggregate. `proj_equipment_asset_summary` is exactly
that: a denormalized cross-stream view maintained by the Asset
projection worker. The lookup adapter reads it directly via the
shared asyncpg pool.

## Query shape

Single SELECT keyed by the `asset_id` primary key, LEFT JOINing
`proj_equipment_asset_family_membership` and
`proj_equipment_family_summary` so the Asset's Family affordances
aggregate into one set in the same round-trip. `LEFT JOIN` +
`array_agg(... FILTER ...)` keeps an Asset with no Family (or whose
Families declare no affordance) resolvable with an empty affordance
set, rather than returning no row. `GROUP BY` collapses the
one-row-per-Family-membership fan-out back to one row per Asset.

Returns `None` when no Asset row matches. Assets in every lifecycle
(`Commissioned`, `Active`, `Maintenance`, `Decommissioned`) are
returned; consumer deciders partition on `lifecycle` if needed.
Slice 7B Supply consumer does NOT filter on lifecycle (mirrors
slice 6A `FacilityLookup` precedent: bind anyway, the operator
chose to keep the lineage visible).

## Enum coercion

`tier` and `lifecycle` are stored as `TEXT` columns and typed as
`str` on the port's `AssetLookupResult` (to keep
`cora.infrastructure.ports.asset_lookup` import-free of Equipment
BC types). The adapter still constructs `AssetTier(row["tier"])`
/ `AssetLifecycle(row["lifecycle"])` as a validation step: a
corrupted row whose `tier` or `lifecycle` is not a known enum
value surfaces as `ValueError` from the adapter rather than as a
silent wrong-tier match downstream. The validated `StrEnum` value
IS-A `str`, so the assignment into the dataclass's `str`-typed
fields is exact.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Any
from uuid import UUID

import asyncpg

from cora.equipment.aggregates.asset import AssetLifecycle, AssetTier
from cora.infrastructure.ports.asset_lookup import AssetLookupResult

_LOOKUP_SQL = """
SELECT
    a.asset_id,
    a.name,
    a.tier,
    a.lifecycle,
    COALESCE(
        array_agg(DISTINCT aff.affordance) FILTER (WHERE aff.affordance IS NOT NULL),
        ARRAY[]::text[]
    ) AS family_affordances
FROM proj_equipment_asset_summary a
LEFT JOIN proj_equipment_asset_family_membership m
    ON m.asset_id = a.asset_id
LEFT JOIN proj_equipment_family_summary f
    ON f.family_id = m.family_id
LEFT JOIN LATERAL unnest(f.affordances) AS aff(affordance) ON TRUE
WHERE a.asset_id = $1
GROUP BY a.asset_id, a.name, a.tier, a.lifecycle
"""


class PostgresAssetLookup:
    """asyncpg-backed `AssetLookup` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def lookup(self, asset_id: UUID) -> AssetLookupResult | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_LOOKUP_SQL, asset_id)
        if row is None:
            return None
        return _row_to_result(row)


def _row_to_result(row: Any) -> AssetLookupResult:
    return AssetLookupResult(
        id=row["asset_id"],
        name=str(row["name"]),
        tier=AssetTier(row["tier"]),
        lifecycle=AssetLifecycle(row["lifecycle"]),
        family_affordances=frozenset(str(a) for a in row["family_affordances"]),
    )


__all__ = ["PostgresAssetLookup"]
