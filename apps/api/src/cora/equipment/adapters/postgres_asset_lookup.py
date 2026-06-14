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
from cora.infrastructure.ports.asset_lookup import (
    ANCESTOR_WALK_DEPTH_CAP,
    AncestorWalkDepthExceededError,
    AssetLookupResult,
)

_LOOKUP_SQL = """
SELECT
    a.asset_id,
    a.name,
    a.tier,
    a.lifecycle,
    a.located_in_enclosure_id,
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
GROUP BY a.asset_id, a.name, a.tier, a.lifecycle, a.located_in_enclosure_id
"""

# Inclusive ancestor closure via a `parent_id` recursive walk.
#
# The recursive CTE seeds at the input ids (depth 0) and climbs each
# row's `parent_id` to its parent. The SQL-standard `CYCLE` clause is
# the LOAD-BEARING cycle terminator: it stops recursion the moment an
# `asset_id` repeats on its own path and marks `is_cycle` on the
# offending row. The `WHERE anc.depth < $2` belt-and-braces ceiling
# bounds a pathological-but-acyclic chain; a surviving row at the cap
# depth whose `parent_id IS NOT NULL` means the real chain runs past
# the cap (an overrun). `flags` lifts both conditions to scalars plus
# `max_depth` (the deepest walked level, which the raise reports as the
# observed depth so an operator can tell a small-depth cycle from a
# cap-deep tree); the adapter raises `AncestorWalkDepthExceededError`
# on either condition rather than returning a wrong partial closure.
# The final SELECT re-joins the
# closure to the summary + family tables, reusing the same
# affordance-aggregation shape as `_LOOKUP_SQL` so the rows are
# identical to a per-id `lookup`. `$1` = input asset ids, `$2` = depth
# cap.
_ANCESTORS_SQL = """
WITH RECURSIVE ancestors AS (
    SELECT asset_id, parent_id, 0 AS depth
    FROM proj_equipment_asset_summary
    WHERE asset_id = ANY($1::uuid[])
  UNION ALL
    SELECT a.asset_id, a.parent_id, anc.depth + 1
    FROM proj_equipment_asset_summary a
    JOIN ancestors anc ON a.asset_id = anc.parent_id
    WHERE anc.depth < $2
) CYCLE asset_id SET is_cycle USING path,
flags AS (
    SELECT
        bool_or(is_cycle) AS any_cycle,
        bool_or(depth >= $2 AND parent_id IS NOT NULL) AS any_overrun,
        max(depth) AS max_depth
    FROM ancestors
),
closure AS (
    SELECT DISTINCT asset_id FROM ancestors
)
SELECT
    a.asset_id,
    a.name,
    a.tier,
    a.lifecycle,
    a.located_in_enclosure_id,
    COALESCE(
        array_agg(DISTINCT aff.affordance) FILTER (WHERE aff.affordance IS NOT NULL),
        ARRAY[]::text[]
    ) AS family_affordances,
    (SELECT any_cycle FROM flags) AS any_cycle,
    (SELECT any_overrun FROM flags) AS any_overrun,
    (SELECT max_depth FROM flags) AS max_depth
FROM closure c
JOIN proj_equipment_asset_summary a
    ON a.asset_id = c.asset_id
LEFT JOIN proj_equipment_asset_family_membership m
    ON m.asset_id = a.asset_id
LEFT JOIN proj_equipment_family_summary f
    ON f.family_id = m.family_id
LEFT JOIN LATERAL unnest(f.affordances) AS aff(affordance) ON TRUE
GROUP BY a.asset_id, a.name, a.tier, a.lifecycle, a.located_in_enclosure_id
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

    async def ancestors_of(self, asset_ids: frozenset[UUID]) -> frozenset[AssetLookupResult]:
        """Inclusive `parent_id` ancestor closure via a recursive CTE.

        Walks each input Asset's `parent_id` chain to its facility-rooted
        root (the row with `parent_id IS NULL`), returning the union of
        the inputs and every ancestor as `AssetLookupResult` rows (same
        shape `lookup` returns). The SQL-standard `CYCLE` clause is the
        load-bearing cycle terminator; `ANCESTOR_WALK_DEPTH_CAP` is the
        belt-and-braces ceiling. A detected cycle OR a depth overrun
        raises `AncestorWalkDepthExceededError` rather than returning a
        wrong partial closure (which would under-scope the enclosure
        pre-flight gate). Empty input short-circuits without a round
        trip. The walk reads only `proj_equipment_asset_summary` (+ the
        family tables for affordances); it never touches the Federation
        Facility aggregate.
        """
        if not asset_ids:
            return frozenset()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_ANCESTORS_SQL, list(asset_ids), ANCESTOR_WALK_DEPTH_CAP)
        if not rows:
            return frozenset()
        if rows[0]["any_cycle"] or rows[0]["any_overrun"]:
            raise AncestorWalkDepthExceededError(
                observed_depth=rows[0]["max_depth"], cap=ANCESTOR_WALK_DEPTH_CAP
            )
        return frozenset(_row_to_result(row) for row in rows)


def _row_to_result(row: Any) -> AssetLookupResult:
    return AssetLookupResult(
        id=row["asset_id"],
        name=str(row["name"]),
        tier=AssetTier(row["tier"]),
        lifecycle=AssetLifecycle(row["lifecycle"]),
        family_affordances=frozenset(str(a) for a in row["family_affordances"]),
        located_in_enclosure_id=row["located_in_enclosure_id"],
    )


__all__ = ["PostgresAssetLookup"]
