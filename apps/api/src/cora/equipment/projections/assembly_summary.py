"""AssemblySummaryProjection: folds the Assembly aggregate's lifecycle
events into the `proj_equipment_assembly_summary` read model.

Subscribed events (per slice):
  - AssemblyDefined  -> INSERT (status=Defined, version + content_hash
                                from payload). Shipped with B.0
                                scaffold.
  - AssemblyVersioned -> UPDATE status=Versioned + name +
                                presents_as_family_id + version +
                                content_hash. Replace-on-version
                                semantic mirrors the aggregate state.
                                Shipped with version_assembly slice.
  - AssemblyDeprecated -> UPDATE status=Deprecated (added with
                                deprecate_assembly slice).

All branches idempotent (INSERT uses ON CONFLICT DO NOTHING; UPDATEs
write fixed values per event type so re-application is a no-op).
Mirrors FamilySummaryProjection's shape.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike


def _id(payload: dict[str, object]) -> UUID:
    return UUID(str(payload["assembly_id"]))


_INSERT_ASSEMBLY_SQL = """
INSERT INTO proj_equipment_assembly_summary
    (assembly_id, name, presents_as_family_id, status, version,
     content_hash, created_at)
VALUES ($1, $2, $3, 'Defined', $4, $5, $6)
ON CONFLICT (assembly_id) DO NOTHING
"""

_UPDATE_VERSIONED_SQL = """
UPDATE proj_equipment_assembly_summary
SET status = 'Versioned',
    name = $2,
    presents_as_family_id = $3,
    version = $4,
    content_hash = $5,
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
                    UUID(str(payload["presents_as_family_id"])),
                    payload.get("version"),
                    payload["content_hash"],
                    datetime.fromisoformat(str(payload["occurred_at"])),
                )
            case "AssemblyVersioned":
                payload = event.payload
                await conn.execute(
                    _UPDATE_VERSIONED_SQL,
                    _id(payload),
                    payload["name"],
                    UUID(str(payload["presents_as_family_id"])),
                    payload.get("version"),
                    payload["content_hash"],
                )
            case _:
                pass


__all__ = ["AssemblySummaryProjection"]
