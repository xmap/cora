"""AssetSummaryProjection: folds the Asset aggregate's lifecycle +
hierarchy + condition + alternate-identifier + owner events into the
`proj_equipment_asset_summary` read model that backs `GET /assets`.

Subscribed events:
  - AssetRegistered                   -> INSERT (lifecycle=Commissioned,
                                         condition=Nominal; level + parent_id
                                         + drawing trio + model_id +
                                         alternate_identifiers + owners from
                                         payload)
  - AssetActivated                    -> UPDATE lifecycle=Active
  - AssetDecommissioned               -> UPDATE lifecycle=Decommissioned
  - AssetMaintenanceEntered           -> UPDATE lifecycle=Maintenance
  - AssetMaintenanceExited            -> UPDATE lifecycle=Active
  - AssetRelocated                    -> UPDATE parent_id=to_parent_id
  - AssetDegraded                     -> UPDATE condition=Degraded
  - AssetFaulted                      -> UPDATE condition=Faulted
  - AssetRestored                     -> UPDATE condition=Nominal
  - AssetAlternateIdentifierAdded     -> UPDATE append (kind, value) into
                                         alternate_identifiers JSONB array,
                                         de-duplicated and re-sorted
  - AssetAlternateIdentifierRemoved   -> UPDATE remove (kind, value) from
                                         alternate_identifiers JSONB array
  - AssetOwnerAdded                   -> UPDATE append owner into owners JSONB
                                         array, re-sorted by name ASC
  - AssetOwnerRemoved                 -> UPDATE remove owner matching name
                                         from owners JSONB array

NOT subscribed:
  - AssetFamilyAdded / AssetFamilyRemoved: these describe
    the Asset<->Family join, not the Asset's own state. They
    feed the sibling `AssetFamilyMembershipProjection`
    (`proj_equipment_asset_family_membership`).

All branches idempotent. INSERT uses ON CONFLICT DO NOTHING. UPDATEs
for lifecycle / condition / parent write fixed values per event type so
re-application is a no-op. The alternate-identifier add path dedupes
(uniqueness keyed on the JSONB element identity); the remove path
filters by (kind, value) so re-application is a no-op once the row is
gone.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import asyncpg

    from cora.infrastructure.ports.event_store import StoredEvent
    from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_ASSET_SQL = """
INSERT INTO proj_equipment_asset_summary
    (asset_id, name, level, lifecycle, condition, parent_id,
     drawing_system, drawing_number, drawing_revision, model_id,
     alternate_identifiers, owners, created_at)
VALUES ($1, $2, $3, 'Commissioned', 'Nominal', $4, $5, $6, $7, $8,
        $9, $10, $11)
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

# Append-and-re-sort in a single SQL statement: union the existing
# array with the new singleton, deduplicate on (kind, value), and
# re-aggregate in canonical (kind, value) order so the column stays
# byte-stable across replays. The DISTINCT ON pair matches the
# (kind, value) identity declared by the AlternateIdentifier VO.
_UPDATE_ALTERNATE_IDENTIFIER_ADDED_SQL = """
UPDATE proj_equipment_asset_summary
SET alternate_identifiers = COALESCE(
        (
            SELECT jsonb_agg(elem ORDER BY elem->>'kind', elem->>'value')
            FROM (
                SELECT DISTINCT ON (elem->>'kind', elem->>'value') elem
                FROM jsonb_array_elements(
                    alternate_identifiers || jsonb_build_array(
                        jsonb_build_object('kind', $2::text, 'value', $3::text)
                    )
                ) AS elem
                ORDER BY elem->>'kind', elem->>'value'
            ) AS dedup
        ),
        '[]'::jsonb
    ),
    updated_at = now()
WHERE asset_id = $1
"""

# Filter-out the matching (kind, value) element. Empty result collapses
# to `[]` via COALESCE so the NOT NULL constraint holds.
_UPDATE_ALTERNATE_IDENTIFIER_REMOVED_SQL = """
UPDATE proj_equipment_asset_summary
SET alternate_identifiers = COALESCE(
        (
            SELECT jsonb_agg(elem ORDER BY elem->>'kind', elem->>'value')
            FROM jsonb_array_elements(alternate_identifiers) AS elem
            WHERE NOT (elem->>'kind' = $2::text AND elem->>'value' = $3::text)
        ),
        '[]'::jsonb
    ),
    updated_at = now()
WHERE asset_id = $1
"""

# Append-and-re-sort owners in a single SQL statement. The full owner
# block (name + nullable contact + nullable identifier + nullable
# identifier_type) arrives as a JSON object literal bound on $2. Union
# the existing array with the new singleton, dedupe by name (latest
# event wins via DISTINCT ON), and re-aggregate sorted by name ASC.
_UPDATE_OWNER_ADDED_SQL = """
UPDATE proj_equipment_asset_summary
SET owners = COALESCE(
        (
            SELECT jsonb_agg(elem ORDER BY elem->>'name')
            FROM (
                SELECT DISTINCT ON (elem->>'name') elem
                FROM jsonb_array_elements(
                    owners || jsonb_build_array($2::jsonb)
                ) AS elem
                ORDER BY elem->>'name'
            ) AS dedup
        ),
        '[]'::jsonb
    ),
    updated_at = now()
WHERE asset_id = $1
"""

# Filter-out owner blocks whose `name` matches. Empty result collapses
# to `[]` via COALESCE so the NOT NULL constraint holds. Keyed on the
# JSON `name` text (Lock 5: owner_name is the removal key, not full VO).
_UPDATE_OWNER_REMOVED_SQL = """
UPDATE proj_equipment_asset_summary
SET owners = COALESCE(
        (
            SELECT jsonb_agg(elem ORDER BY elem->>'name')
            FROM jsonb_array_elements(owners) AS elem
            WHERE elem->>'name' <> $2::text
        ),
        '[]'::jsonb
    ),
    updated_at = now()
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
            "AssetAlternateIdentifierAdded",
            "AssetAlternateIdentifierRemoved",
            "AssetOwnerAdded",
            "AssetOwnerRemoved",
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
                alternate_identifiers_list = _canonical_alternate_identifiers_list(
                    event.payload.get("alternate_identifiers")
                )
                owners_list = _canonical_owners_list(event.payload.get("owners"))
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
                    alternate_identifiers_list,
                    owners_list,
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
            case "AssetAlternateIdentifierAdded":
                identifier = event.payload["alternate_identifier"]
                await conn.execute(
                    _UPDATE_ALTERNATE_IDENTIFIER_ADDED_SQL,
                    UUID(event.payload["asset_id"]),
                    identifier["kind"],
                    identifier["value"],
                )
            case "AssetAlternateIdentifierRemoved":
                identifier = event.payload["alternate_identifier"]
                await conn.execute(
                    _UPDATE_ALTERNATE_IDENTIFIER_REMOVED_SQL,
                    UUID(event.payload["asset_id"]),
                    identifier["kind"],
                    identifier["value"],
                )
            case "AssetOwnerAdded":
                owner_jsonb = _canonical_owner_jsonb(event.payload["owner"])
                await conn.execute(
                    _UPDATE_OWNER_ADDED_SQL,
                    UUID(event.payload["asset_id"]),
                    owner_jsonb,
                )
            case "AssetOwnerRemoved":
                await conn.execute(
                    _UPDATE_OWNER_REMOVED_SQL,
                    UUID(event.payload["asset_id"]),
                    event.payload["owner_name"],
                )
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


def _canonical_owner_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize one owner block into the canonical stored shape.

    Always emits the four keys in the same order (`name`, `contact`,
    `identifier`, `identifier_type`) with `None` for absent optional
    fields. The pool's jsonb codec encodes Python `None` as JSON
    null, matching the wire shape recorded in the event payload.
    """
    return {
        "name": str(raw["name"]),
        "contact": (None if raw.get("contact") is None else str(raw["contact"])),
        "identifier": (None if raw.get("identifier") is None else str(raw["identifier"])),
        "identifier_type": (
            None if raw.get("identifier_type") is None else str(raw["identifier_type"])
        ),
    }


def _canonical_owners_list(
    raw: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Serialize the AssetRegistered payload's owners into a canonical
    list of dicts the asyncpg jsonb codec can encode.

    Sorted by `name` so the same logical set produces the same byte
    sequence on disk regardless of payload insertion order. Empty or
    missing payload key produces `[]`. Mirrors the
    `_canonical_alternate_identifiers_list` helper and the projection
    UPDATE statements' `jsonb_agg(... ORDER BY name)` sort.
    """
    if not raw:
        return []
    return sorted(
        (_canonical_owner_dict(item) for item in raw),
        key=lambda item: item["name"],
    )


def _canonical_owner_jsonb(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a canonical owner dict for binding to a `$x::jsonb` parameter.

    The pool's jsonb codec (`encoder=json.dumps`) serializes Python
    dicts on the wire; the SQL cast `$2::jsonb` then wraps the encoded
    bytes back as a JSONB value that `jsonb_build_array` can wrap.
    Returning the dict (not pre-serialized JSON text) avoids the
    double-encoding the codec would otherwise apply if a JSON string
    were bound to a jsonb parameter.
    """
    return _canonical_owner_dict(raw)


def _canonical_alternate_identifiers_list(
    raw: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Serialize the AssetRegistered payload's alternate_identifiers
    into a canonical list of dicts the asyncpg jsonb codec can encode.

    Sorted by (kind, value) so the same logical set produces the same
    byte sequence on disk regardless of payload insertion order. Empty
    or missing payload key produces `[]`. The events.py to_payload
    already sorts at write time per the design memo; the projection
    re-sorts defensively so a hand-crafted replay-fixture event with
    out-of-order entries still lands canonical.

    Returns a Python `list[dict]` rather than a pre-serialized JSON
    string: the asyncpg pool registers a jsonb codec that runs
    `json.dumps` on every parameter bound to a jsonb column. Passing
    an already-stringified `"[]"` would be wrapped a second time into
    a JSON-string scalar, breaking the partial GIN index's
    `jsonb_array_length(alternate_identifiers) > 0` predicate.
    """
    if not raw:
        return []
    return sorted(
        ({"kind": str(item["kind"]), "value": str(item["value"])} for item in raw),
        key=lambda item: (item["kind"], item["value"]),
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
