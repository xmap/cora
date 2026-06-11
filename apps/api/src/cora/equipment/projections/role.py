"""RoleSummaryProjection: folds the Role aggregate's RoleDefined event
into the `proj_equipment_role_summary` read model.

3A subscribes only to `RoleDefined` (genesis). When Lock 14 versioning
lands, future `RoleAffordancesUpdated` / `RoleSignalsUpdated` events
gain UPDATE arms here (TEXT[] columns for required_affordances /
optional_affordances / produces / consumes are already in place at
this slice so the next migration is an UPDATE rule add, not a column
add).

Idempotent INSERT via `ON CONFLICT (role_id) DO NOTHING`. The TEXT[]
columns receive the sorted-string lists per the event payload
serialization convention.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike


def _id(payload: dict[str, object]) -> UUID:
    return UUID(str(payload["role_id"]))


_INSERT_ROLE_SQL = """
INSERT INTO proj_equipment_role_summary
    (role_id, name, docstring,
     required_affordances, optional_affordances,
     produces, consumes,
     created_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (role_id) DO NOTHING
"""


class RoleSummaryProjection:
    """Maintains the `proj_equipment_role_summary` read model."""

    name = "proj_equipment_role_summary"
    subscribed_event_types = frozenset({"RoleDefined"})

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "RoleDefined":
                payload = event.payload
                await conn.execute(
                    _INSERT_ROLE_SQL,
                    _id(payload),
                    payload["name"],
                    payload["docstring"],
                    list(payload.get("required_affordances", [])),
                    list(payload.get("optional_affordances", [])),
                    list(payload.get("produces", [])),
                    list(payload.get("consumes", [])),
                    datetime.fromisoformat(str(payload["occurred_at"])),
                )
            case _:
                pass


__all__ = ["RoleSummaryProjection"]
