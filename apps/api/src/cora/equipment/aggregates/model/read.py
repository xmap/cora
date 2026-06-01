# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

"""Read repositories for the Model aggregate.

`load_model(event_store, model_id) -> Model | None` mirrors
`load_family` / `load_actor` / `load_subject` / etc.

`list_model_ids(pool) -> list[UUID]` reads every non-Deprecated Model
id from the summary projection. Mirrors `list_family_ids`; intended
for `inspect_plan_binding`-style candidate enumeration and for
cross-BC catalog-lookup preconditions in future slices.

The Model summary projection (`proj_equipment_model_summary`) does
NOT carry per-FSM-transition timestamps (versioned_at, deprecated_at)
the way `proj_equipment_family_summary` does; the projection's
`created_at` is the only lifecycle timestamp materialized today.
Consumers that need transition timestamps would either fold the
event stream directly or trigger a future projection-schema
addition. No `load_model_timestamps` ships in this slice as a result.

`_STREAM_TYPE = "Model"`. The stream-type string is the event store's
internal categorization key for this aggregate.
"""

from uuid import UUID

import asyncpg

from cora.equipment.aggregates.model.events import from_stored
from cora.equipment.aggregates.model.evolver import fold
from cora.equipment.aggregates.model.state import Model
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Model"


async def load_model(event_store: EventStore, model_id: UUID) -> Model | None:
    """Load and fold a Model's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, model_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


_SELECT_MODEL_IDS_SQL = """
SELECT model_id
FROM proj_equipment_model_summary
WHERE status <> 'Deprecated'
ORDER BY model_id::text
"""


async def list_model_ids(pool: asyncpg.Pool | None) -> list[UUID]:
    """Read every non-Deprecated Model id from the summary projection.

    Mirrors `list_family_ids`: returns `[]` when `pool is None`
    (test / no-database app_env), so callers do not need a defensive
    None-check at every site. Tests that need a populated lookup
    must wire a real pool.

    Deprecated Models are excluded at the SQL layer so they are not
    offered as candidate sources in future cross-BC lookups; operators
    can still inspect Deprecated Models directly via `get_model`.
    """
    if pool is None:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch(_SELECT_MODEL_IDS_SQL)
    return [row["model_id"] for row in rows]
