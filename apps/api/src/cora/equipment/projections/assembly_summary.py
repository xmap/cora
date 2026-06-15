"""AssemblySummaryProjection: folds the Assembly aggregate's lifecycle
events into the `proj_equipment_assembly_summary` read model.

Subscribed events (per slice):
  - AssemblyDefined  -> INSERT (status=Defined, version + content_hash
                                + required_sub_assemblies from payload,
                                presents_as=[]). Shipped with B.0 scaffold.
  - AssemblyVersioned -> UPDATE status=Versioned + name +
                                presents_as + version +
                                content_hash + required_sub_assemblies.
                                Replace-on-version semantic mirrors the
                                aggregate state.
  - AssemblyDeprecated -> UPDATE status=Deprecated.
  - AssemblyPresentsAsAdded -> UPDATE
                                presents_as = (DISTINCT append).
                                Layer 3 sub-slice 3C.
  - AssemblyPresentsAsRemoved -> UPDATE
                                presents_as = array_remove(...).
                                Layer 3 sub-slice 3C.

All branches idempotent. Mirrors FamilySummaryProjection's shape.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike


def _id(payload: dict[str, object]) -> UUID:
    return UUID(str(payload["assembly_id"]))


_INSERT_ASSEMBLY_SQL = """
INSERT INTO proj_equipment_assembly_summary
    (assembly_id, name, status, version,
     content_hash, created_at, presents_as, required_sub_assemblies)
VALUES ($1, $2, 'Defined', $3, $4, $5, $6::UUID[], $7::jsonb)
ON CONFLICT (assembly_id) DO NOTHING
"""

_UPDATE_VERSIONED_SQL = """
UPDATE proj_equipment_assembly_summary
SET status = 'Versioned',
    name = $2,
    version = $3,
    content_hash = $4,
    presents_as = $5::UUID[],
    required_sub_assemblies = $6::jsonb,
    updated_at = now()
WHERE assembly_id = $1
"""

_UPDATE_DEPRECATED_SQL = """
UPDATE proj_equipment_assembly_summary
SET status = 'Deprecated',
    updated_at = now()
WHERE assembly_id = $1
"""

_UPDATE_PRESENTS_AS_ADDED_SQL = """
UPDATE proj_equipment_assembly_summary
SET presents_as = (
    SELECT ARRAY(
        SELECT DISTINCT unnest(presents_as || ARRAY[$2]::UUID[])
    )
),
    updated_at = now()
WHERE assembly_id = $1
"""

_UPDATE_PRESENTS_AS_REMOVED_SQL = """
UPDATE proj_equipment_assembly_summary
SET presents_as = array_remove(presents_as, $2),
    updated_at = now()
WHERE assembly_id = $1
"""


class AssemblySummaryProjection:
    """Maintains the `proj_equipment_assembly_summary` read model."""

    name = "proj_equipment_assembly_summary"
    subscribed_event_types = frozenset(
        {
            "AssemblyDefined",
            "AssemblyVersioned",
            "AssemblyDeprecated",
            "AssemblyPresentsAsAdded",
            "AssemblyPresentsAsRemoved",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "AssemblyDefined":
                payload = event.payload
                await conn.execute(
                    _INSERT_ASSEMBLY_SQL,
                    _id(payload),
                    payload["name"],
                    payload.get("version"),
                    payload["content_hash"],
                    datetime.fromisoformat(str(payload["occurred_at"])),
                    [UUID(str(r)) for r in payload["presents_as"]],
                    json.dumps(payload.get("required_sub_assemblies", [])),
                )
            case "AssemblyVersioned":
                payload = event.payload
                await conn.execute(
                    _UPDATE_VERSIONED_SQL,
                    _id(payload),
                    payload["name"],
                    payload.get("version"),
                    payload["content_hash"],
                    [UUID(str(r)) for r in payload["presents_as"]],
                    json.dumps(payload.get("required_sub_assemblies", [])),
                )
            case "AssemblyDeprecated":
                await conn.execute(
                    _UPDATE_DEPRECATED_SQL,
                    _id(event.payload),
                )
            case "AssemblyPresentsAsAdded":
                await conn.execute(
                    _UPDATE_PRESENTS_AS_ADDED_SQL,
                    _id(event.payload),
                    UUID(str(event.payload["role_id"])),
                )
            case "AssemblyPresentsAsRemoved":
                await conn.execute(
                    _UPDATE_PRESENTS_AS_REMOVED_SQL,
                    _id(event.payload),
                    UUID(str(event.payload["role_id"])),
                )
            case _:
                pass


__all__ = ["AssemblySummaryProjection"]
