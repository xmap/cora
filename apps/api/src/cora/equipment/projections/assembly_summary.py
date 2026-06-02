"""AssemblySummaryProjection: folds the Assembly aggregate's lifecycle
events into the `proj_equipment_assembly_summary` read model.

v1 ships ONLY the `AssemblyDefined` arm. The `AssemblyVersioned`
and `AssemblyDeprecated` arms land with their respective slices
to keep the slice-per-commit gate-review discipline intact (no
projector arms without a matching emitter slice).

Subscribed events (v1, scaffold):
  - AssemblyDefined -> INSERT (status=Defined, version=NULL on
                       payload absence; content_hash from payload)

All branches idempotent (INSERT uses ON CONFLICT DO NOTHING).
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


class AssemblySummaryProjection:
    """Maintains the `proj_equipment_assembly_summary` read model."""

    name = "proj_equipment_assembly_summary"
    subscribed_event_types = frozenset({"AssemblyDefined"})

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
            case _:
                pass


__all__ = ["AssemblySummaryProjection"]
