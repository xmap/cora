"""ModelSummaryProjection: folds the Model aggregate's 5 events into
the `proj_equipment_model_summary` read model that backs
`GET /models/{id}` and the future `list_models` slice, and that
materializes the Lock-4 vendor-key uniqueness guard
`(manufacturer_name, part_number)` for command-time precondition
checks.

  - ModelDefined        -> INSERT (status=Defined; version_tag from
        payload when present, NULL otherwise; manufacturer flat
        columns; declared_families JSONB array sorted as carried
        in the event payload)
  - ModelVersioned      -> UPDATE status=Versioned and REPLACE
        name / manufacturer_name / manufacturer_identifier /
        manufacturer_identifier_type / part_number /
        declared_families / version_tag wholesale (a new revision
        re-authors the catalog entry's identity block)
  - ModelDeprecated     -> UPDATE status=Deprecated and set
        deprecation_reason; vendor-key columns
        (manufacturer_name, part_number) and declared_families
        preserved so the audit answer to "what was deprecated"
        stays queryable
  - ModelFamilyAdded    -> UPDATE declared_families to append the
        single family_id and re-sort, matching the canonical
        sorted-string-array ordering used in event payloads
  - ModelFamilyRemoved  -> UPDATE declared_families to drop the
        single family_id while preserving sort order

All branches idempotent. `version_tag` lands in the projection on
Defined (when carried) and on Versioned, and is replaced wholesale
on Versioned; the Deprecated UPDATE does not touch it. The flat
manufacturer columns (rather than a single JSONB blob) keep the
vendor-key uniqueness index and the manufacturer-keyed filter path
queryable without JSONB expression indexes.

The targeted-mutation events fold via pure-SQL re-aggregation
(`jsonb_array_elements_text` + `UNION` / filter + `jsonb_agg(...
ORDER BY ...)`) rather than read-then-rewrite in Python; this keeps
the apply step in one round trip and reproduces the canonical
sorted-array shape the event payloads carry for the wholesale
events.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike


def _id(payload: dict[str, object]) -> UUID:
    return UUID(str(payload["model_id"]))


def _manufacturer_columns(
    payload: dict[str, object],
) -> tuple[str, str | None, str | None]:
    """Extract flat manufacturer columns from a payload's `manufacturer` sub-dict.

    The pairing invariant (`identifier` and `identifier_type` both set
    or both None) is preserved end-to-end: the event payload omits the
    pair together, so .get() returning None for both is the correct
    shape and the projection table's paired CHECK constraint allows it.
    """
    manufacturer = payload["manufacturer"]
    assert isinstance(manufacturer, dict)
    name = str(manufacturer["name"])
    identifier_raw = manufacturer.get("identifier")
    identifier_type_raw = manufacturer.get("identifier_type")
    identifier = str(identifier_raw) if identifier_raw is not None else None
    identifier_type = str(identifier_type_raw) if identifier_type_raw is not None else None
    return name, identifier, identifier_type


_INSERT_MODEL_SQL = """
INSERT INTO proj_equipment_model_summary
    (model_id, name,
     manufacturer_name, manufacturer_identifier, manufacturer_identifier_type,
     part_number, declared_families,
     status, version_tag, created_at)
VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, 'Defined', $8, $9)
ON CONFLICT (model_id) DO NOTHING
"""

_UPDATE_VERSIONED_SQL = """
UPDATE proj_equipment_model_summary
SET status = 'Versioned',
    name = $2,
    manufacturer_name = $3,
    manufacturer_identifier = $4,
    manufacturer_identifier_type = $5,
    part_number = $6,
    declared_families = $7::jsonb,
    version_tag = $8,
    updated_at = now()
WHERE model_id = $1
"""

_UPDATE_DEPRECATED_SQL = """
UPDATE proj_equipment_model_summary
SET status = 'Deprecated',
    deprecation_reason = $2,
    updated_at = now()
WHERE model_id = $1
"""

# Append a single family_id to the JSONB array and re-sort. The UNION
# de-duplicates so re-applying ModelFamilyAdded is a no-op (the
# aggregate already rejected the duplicate at command time; this is
# the replay-safety layer).
_UPDATE_FAMILY_ADDED_SQL = """
UPDATE proj_equipment_model_summary
SET declared_families = COALESCE((
        SELECT jsonb_agg(elem ORDER BY elem)
        FROM (
            SELECT jsonb_array_elements_text(declared_families) AS elem
            UNION
            SELECT $2::text
        ) sub
    ), '[]'::jsonb),
    updated_at = now()
WHERE model_id = $1
"""

# Drop a single family_id from the JSONB array while preserving sort
# order. The WHERE clause inside the subquery skips the removed id;
# the outer COALESCE handles the all-removed degenerate case (which
# the aggregate's empty-set guard makes unreachable in practice but
# keeps the projection robust under replay of historical streams).
_UPDATE_FAMILY_REMOVED_SQL = """
UPDATE proj_equipment_model_summary
SET declared_families = COALESCE((
        SELECT jsonb_agg(elem ORDER BY elem)
        FROM (
            SELECT jsonb_array_elements_text(declared_families) AS elem
        ) sub
        WHERE elem <> $2::text
    ), '[]'::jsonb),
    updated_at = now()
WHERE model_id = $1
"""


class ModelSummaryProjection:
    """Maintains the `proj_equipment_model_summary` read model."""

    name = "proj_equipment_model_summary"
    subscribed_event_types = frozenset(
        {
            "ModelDefined",
            "ModelVersioned",
            "ModelDeprecated",
            "ModelFamilyAdded",
            "ModelFamilyRemoved",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "ModelDefined":
                name, identifier, identifier_type = _manufacturer_columns(event.payload)
                declared_families = event.payload.get("declared_families", [])
                await conn.execute(
                    _INSERT_MODEL_SQL,
                    _id(event.payload),
                    event.payload["name"],
                    name,
                    identifier,
                    identifier_type,
                    event.payload["part_number"],
                    json.dumps(declared_families),
                    event.payload.get("version_tag"),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "ModelVersioned":
                name, identifier, identifier_type = _manufacturer_columns(event.payload)
                declared_families = event.payload.get("declared_families", [])
                await conn.execute(
                    _UPDATE_VERSIONED_SQL,
                    _id(event.payload),
                    event.payload["name"],
                    name,
                    identifier,
                    identifier_type,
                    event.payload["part_number"],
                    json.dumps(declared_families),
                    event.payload["version_tag"],
                )
            case "ModelDeprecated":
                await conn.execute(
                    _UPDATE_DEPRECATED_SQL,
                    _id(event.payload),
                    event.payload["reason"],
                )
            case "ModelFamilyAdded":
                await conn.execute(
                    _UPDATE_FAMILY_ADDED_SQL,
                    _id(event.payload),
                    str(event.payload["family_id"]),
                )
            case "ModelFamilyRemoved":
                await conn.execute(
                    _UPDATE_FAMILY_REMOVED_SQL,
                    _id(event.payload),
                    str(event.payload["family_id"]),
                )
            case _:
                pass


__all__ = ["ModelSummaryProjection"]
