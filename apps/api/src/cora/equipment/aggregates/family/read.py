# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

"""Read repositories for the Family aggregate.

`load_family(event_store, family_id) -> Family | None` mirrors
`load_actor` / `load_subject` / `load_zone` / etc.

`load_family_timestamps(pool, family_id) -> FamilyLifecycleTimestamps | None`
reads the projection-row metadata that mirrors the FSM transitions
(Path C). State stays minimal per decider purity
(Chassaing/Pellegrini/Reynhout); lifecycle timestamps live on the
projection per Dudycz pragmatic-redundancy + K8s/GitHub/AIP-142
resource-API precedent. Mirrors `load_method_timestamps` /
`load_plan_timestamps` / `load_practice_timestamps`.

## Two list_*_family_ids helpers

Two read helpers enumerate Family ids from the summary projection;
they differ ONLY in whether Deprecated Families are filtered out.

`list_family_ids` EXCLUDES Deprecated Families. It backs the
operator-facing discovery path: `inspect_plan_binding`'s candidate
enumeration should not offer a Deprecated Family as a source for
new wiring.

`list_all_family_ids` INCLUDES Deprecated Families. It backs the
cross-BC existence-check path: `define_model` and `add_model_family`
verify that every referenced Family id resolves to a real Family
stream, and per the Model aggregate's design memo Family.deprecation
is an authoring signal, NOT a runtime gate. Binding a Model to a
Deprecated Family is permitted (mirrors the Asset-to-Deprecated-Family
posture); using the discovery filter here would surface a misleading
`FamilyNotFoundError` for a Family that genuinely exists.

`_STREAM_TYPE = "Family"`. The stream-type string is the event store's
internal categorization key for this aggregate.
"""

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from cora.equipment.aggregates.family.events import from_stored
from cora.equipment.aggregates.family.evolver import fold
from cora.equipment.aggregates.family.state import Family
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Family"

_SELECT_TIMESTAMPS_SQL = """
SELECT created_at, versioned_at, deprecated_at
FROM proj_equipment_family_summary
WHERE family_id = $1
"""


@dataclass(frozen=True)
class FamilyLifecycleTimestamps:
    """Observed wall-clock timestamps of FSM transitions.

    Sourced from the Family summary projection, not from aggregate state.
    `created_at` is set once on `FamilyDefined`; `versioned_at` is
    overwritten on each `FamilyVersioned` (state-always-holds-latest
    convention mirrored in the projection); `deprecated_at` is set
    once on `FamilyDeprecated` and is terminal.
    """

    created_at: datetime
    versioned_at: datetime | None
    deprecated_at: datetime | None


async def load_family(event_store: EventStore, family_id: UUID) -> Family | None:
    """Load and fold a Family's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, family_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


async def load_family_timestamps(
    pool: asyncpg.Pool,
    family_id: UUID,
) -> FamilyLifecycleTimestamps | None:
    """Read the lifecycle-timestamp triple from the projection.

    Contract: `pool` MUST be a live asyncpg pool — None-check belongs
    to the caller, not this function (mirrors `load_method_timestamps`
    and peers).
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_SELECT_TIMESTAMPS_SQL, family_id)
    if row is None:
        return None
    return FamilyLifecycleTimestamps(
        created_at=row["created_at"],
        versioned_at=row["versioned_at"],
        deprecated_at=row["deprecated_at"],
    )


_SELECT_FAMILY_IDS_SQL = """
SELECT family_id
FROM proj_equipment_family_summary
WHERE deprecated_at IS NULL
ORDER BY family_id::text
"""


async def list_family_ids(pool: asyncpg.Pool | None) -> list[UUID]:
    """Read every non-Deprecated Family id from the summary projection.

    Used by `inspect_plan_binding`'s candidate enumeration and by
    `define_model`'s cross-BC family_lookup precondition. Callers
    iterate every Family, load its aggregate state via `load_family`,
    and filter by `Family.affordances` membership. Deprecated
    Families are excluded at the SQL layer so they're not offered
    as candidate sources (operator can still see Deprecated Families
    when they're directly wired into a Plan; this is discovery-side
    only).

    Returns `[]` when `pool is None` (test / no-database app_env),
    mirroring the `load_asset_lifecycle` / `load_asset_location`
    null-pool short-circuit. Tests that need a populated lookup
    must wire a real pool.

    The summary projection doesn't carry an affordances column today
    (5j deferred it); when the first caller demands affordance-
    filtered queries at scale, ship the column + GIN index here and
    collapse the load-fan-out into a single `WHERE affordances && $1`
    clause. Trigger: facility Family count crosses ~50 OR p95 of
    `inspect_plan_binding` crosses 200ms. Pilot scale (~9 Families)
    keeps the load-all-then-filter approach cheap.
    """
    if pool is None:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch(_SELECT_FAMILY_IDS_SQL)
    return [row["family_id"] for row in rows]


_SELECT_ALL_FAMILY_IDS_SQL = """
SELECT family_id
FROM proj_equipment_family_summary
ORDER BY family_id::text
"""


async def list_all_family_ids(pool: asyncpg.Pool | None) -> list[UUID]:
    """Read every Family id from the summary projection, INCLUDING Deprecated.

    Used by `define_model` and `add_model_family` to verify that every
    declared/added Family id resolves to a real Family stream. Per the
    Model aggregate's design memo, Family.deprecation is an authoring
    signal, NOT a runtime gate: a Model is allowed to declare a
    Deprecated Family. Filtering Deprecated rows out here (as
    `list_family_ids` does for the discovery path) would surface a
    misleading `FamilyNotFoundError` for a Family that genuinely
    exists.

    Returns `[]` when `pool is None` (test / no-database app_env),
    mirroring `list_family_ids`. Tests that need a populated lookup
    must wire a real pool.
    """
    if pool is None:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch(_SELECT_ALL_FAMILY_IDS_SQL)
    return [row["family_id"] for row in rows]


async def find_missing_families_per_id(
    event_store: EventStore,
    family_ids: Iterable[UUID],
) -> frozenset[UUID]:
    """Return the subset of `family_ids` not present as Family streams.

    Per-id event-store strategy: loads each referenced Family stream
    concurrently via `load_family` + `asyncio.gather`. Cheap when the
    caller has a bounded handful of ids to verify (Assembly slot count
    today). Returns the missing set; callers decide whether to raise
    or thread the result through context to a decider.

    Used by `define_assembly` and `version_assembly`, which thread
    the missing set into context so the decider surfaces a richer
    error carrying the full set of missing ids (richer than the
    first-missing pattern that `define_model` / `add_model_family`
    use against the bulk-SQL `list_all_family_ids`).

    The Model side keeps its bulk-SQL lookup inline (~2 lines around
    `list_all_family_ids`) because its 15-test monkeypatch surface
    points at the handler module rather than the read module; the
    helper sees no further callers without that test-shape rework.
    Trigger to revisit: a third per-id caller appears (rule of three),
    OR the Model-side handler tests get migrated to patching at the
    read-module location.
    """
    ids_tuple = tuple(family_ids)
    if not ids_tuple:
        return frozenset()
    loaded = await asyncio.gather(*(load_family(event_store, fid) for fid in ids_tuple))
    return frozenset(fid for fid, family in zip(ids_tuple, loaded, strict=True) if family is None)


_SELECT_ASSET_IDS_BY_FAMILIES_SQL = """
SELECT DISTINCT asset_id
FROM proj_equipment_asset_family_membership
WHERE family_id = ANY($1::uuid[])
"""


async def list_asset_ids_in_families(
    pool: asyncpg.Pool,
    family_ids: Iterable[UUID],
) -> list[UUID]:
    """Read the Assets that are members of any of the given Families.

    Reverse-direction lookup against the membership table; used by
    `inspect_plan_binding`'s candidate enumeration to seed "other
    Assets affording requirement X". Uses the `_by_family_idx`
    secondary index for efficient lookup. SELECT DISTINCT dedupes
    Assets that belong to multiple of the requested Families.

    Returns deterministic ordering (asset_id stringified). Caller is
    responsible for any further filtering (e.g. excluding Assets
    already wired into the candidate Plan).
    """
    fids = list(family_ids)
    if not fids:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch(_SELECT_ASSET_IDS_BY_FAMILIES_SQL, fids)
    return sorted((row["asset_id"] for row in rows), key=str)
