"""AssetSummaryProjection: folds the Asset aggregate's lifecycle +
hierarchy + condition events into the `proj_equipment_asset_summary`
read model that backs `GET /assets`.

Subscribed events:
  - AssetRegistered            -> INSERT (lifecycle=Commissioned,
                                  condition=Nominal; level + parent_id
                                  from payload)
  - AssetActivated             -> UPDATE lifecycle=Active
  - AssetDecommissioned        -> UPDATE lifecycle=Decommissioned
  - AssetMaintenanceEntered    -> UPDATE lifecycle=Maintenance
  - AssetMaintenanceExited     -> UPDATE lifecycle=Active
  - AssetRelocated             -> UPDATE parent_id=to_parent_id
  - AssetDegraded              -> UPDATE condition=Degraded
  - AssetFaulted               -> UPDATE condition=Faulted
  - AssetRestored              -> UPDATE condition=Nominal

NOT subscribed:
  - AssetFamilyAdded / AssetFamilyRemoved: these describe
    the Asset<->Family join, not the Asset's own state. They
    feed the sibling `AssetFamilyMembershipProjection`
    (`proj_equipment_asset_family_membership`).

All branches idempotent (INSERT uses ON CONFLICT DO NOTHING; UPDATEs
write fixed values per event type so re-application is a no-op).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    import asyncpg

    from cora.infrastructure.ports.event_store import StoredEvent
    from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_ASSET_SQL = """
INSERT INTO proj_equipment_asset_summary
    (asset_id, name, level, lifecycle, condition, parent_id,
     drawing_system, drawing_number, drawing_revision, model_id,
     created_at)
VALUES ($1, $2, $3, 'Commissioned', 'Nominal', $4, $5, $6, $7, $8, $9)
ON CONFLICT (asset_id) DO NOTHING
"""

_UPDATE_LIFECYCLE_SQL = """
UPDATE proj_equipment_asset_summary
SET lifecycle = $2, updated_at = now()
WHERE asset_id = $1
"""

_UPDATE_PARENT_SQL = """
UPDATE proj_equipment_asset_summary
SET parent_id = $2, updated_at = now()
WHERE asset_id = $1
"""

_UPDATE_CONDITION_SQL = """
UPDATE proj_equipment_asset_summary
SET condition = $2, updated_at = now()
WHERE asset_id = $1
"""


class AssetSummaryProjection:
    """Maintains the `proj_equipment_asset_summary` read model."""

    name = "proj_equipment_asset_summary"
    subscribed_event_types = frozenset(
        {
            "AssetRegistered",
            "AssetActivated",
            "AssetDecommissioned",
            "AssetMaintenanceEntered",
            "AssetMaintenanceExited",
            "AssetRelocated",
            "AssetDegraded",
            "AssetFaulted",
            "AssetRestored",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        """Dispatch on event_type. The `case _: pass` is for pyright
        exhaustiveness (the SQL filter guarantees apply() never sees
        unsubscribed types in production)."""
        match event.event_type:
            case "AssetRegistered":
                parent_id_raw = event.payload.get("parent_id")
                parent_id = UUID(parent_id_raw) if parent_id_raw else None
                drawing = event.payload.get("drawing")
                drawing_system = drawing["system"] if drawing is not None else None
                drawing_number = drawing["number"] if drawing is not None else None
                drawing_revision = drawing.get("revision") if drawing is not None else None
                model_id_raw = event.payload.get("model_id")
                model_id = UUID(model_id_raw) if model_id_raw else None
                await conn.execute(
                    _INSERT_ASSET_SQL,
                    UUID(event.payload["asset_id"]),
                    event.payload["name"],
                    event.payload["level"],
                    parent_id,
                    drawing_system,
                    drawing_number,
                    drawing_revision,
                    model_id,
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "AssetActivated" | "AssetMaintenanceExited":
                await self._update_lifecycle(event, conn, "Active")
            case "AssetDecommissioned":
                await self._update_lifecycle(event, conn, "Decommissioned")
            case "AssetMaintenanceEntered":
                await self._update_lifecycle(event, conn, "Maintenance")
            case "AssetRelocated":
                await conn.execute(
                    _UPDATE_PARENT_SQL,
                    UUID(event.payload["asset_id"]),
                    UUID(event.payload["to_parent_id"]),
                )
            case "AssetDegraded":
                await self._update_condition(event, conn, "Degraded")
            case "AssetFaulted":
                await self._update_condition(event, conn, "Faulted")
            case "AssetRestored":
                await self._update_condition(event, conn, "Nominal")
            case _:
                pass

    async def _update_lifecycle(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
        new_lifecycle: str,
    ) -> None:
        await conn.execute(
            _UPDATE_LIFECYCLE_SQL,
            UUID(event.payload["asset_id"]),
            new_lifecycle,
        )

    async def _update_condition(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
        new_condition: str,
    ) -> None:
        await conn.execute(
            _UPDATE_CONDITION_SQL,
            UUID(event.payload["asset_id"]),
            new_condition,
        )


_SELECT_ASSET_LIFECYCLE_SQL = """
SELECT lifecycle
FROM proj_equipment_asset_summary
WHERE asset_id = $1
"""


async def load_asset_lifecycle(
    pool: asyncpg.Pool,
    asset_id: UUID,
) -> str | None:
    """Return the Asset's current lifecycle string, or None when no row.

    Used by the install_asset handler as a projection precondition:
    None -> AssetNotFoundForMountError; non-Active lifecycle ->
    AssetNotInstallableError; only Active lets the install proceed.
    The "any row counts" semantics that load_asset_exists previously
    enforced let Decommissioned / Commissioned / Maintenance Assets
    occupy live equipment slots invisibly; carrying the lifecycle
    discriminator closes that gap.

    Reuses the existing proj_equipment_asset_summary table: no
    separate asset_lookup / asset_status projection needed.
    """
    row = await pool.fetchrow(_SELECT_ASSET_LIFECYCLE_SQL, asset_id)
    if row is None:
        return None
    return row["lifecycle"]


__all__ = ["AssetSummaryProjection", "load_asset_lifecycle"]
