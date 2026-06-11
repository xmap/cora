"""FamilySummaryProjection: folds the Family aggregate's events into
the `proj_equipment_family_summary` read model that backs
`GET /families` and the Layer-3 `FamilyLookup` cross-BC port.

  - FamilyDefined                  -> INSERT (status=Defined,
        version_tag=NULL, settings_schema_present=FALSE,
        affordances from payload, presents_as=[])
  - FamilyVersioned                -> UPDATE status=Versioned +
        version_tag + affordances replacement (5j semantics)
  - FamilyDeprecated               -> UPDATE status=Deprecated
        (version_tag, affordances, presents_as all preserved on
        purpose: the audit trail stays visible)
  - FamilySettingsSchemaUpdated    -> UPDATE
        settings_schema_present (TRUE if settings_schema is
        non-NULL; FALSE if cleared via NULL)
  - FamilyPresentsAsAdded          -> UPDATE
        presents_as = array_append(presents_as, role_id)
        (3B; idempotent at the DB tier via the decider's strict-
        not-idempotent guard)
  - FamilyPresentsAsRemoved        -> UPDATE
        presents_as = array_remove(presents_as, role_id)
        (3B; idempotent at the DB tier via the decider's strict-
        not-idempotent guard)

All branches idempotent. `version_tag` lands in the projection ONLY
on Versioned events; the Defined INSERT leaves it NULL and the
Deprecated UPDATE doesn't touch it. `settings_schema_present` is
TRUE iff the latest FamilySettingsSchemaUpdated payload's
`settings_schema` was non-NULL; the schema content itself lives in
the event stream (loaded on demand, not projected to keep the
summary table small).

`affordances` (TEXT[] of closed-enum Affordance value strings) lands
on the Defined INSERT and is REPLACED on Versioned (the versioned
affordance set is the new declaration). Deprecated leaves it
untouched (the last-declared set stays visible for audit). Cross-BC
consumers read this column via the AssetLookup port's PG adapter
JOIN to gate on a Family declaring a given affordance, and via the
FamilyLookup port for the bind_plan_role role_kind satisfaction
superset check (memo Lock 17).

`presents_as` (UUID[] of global Role contract ids) is seeded empty
on the Defined INSERT, appended on FamilyPresentsAsAdded, and removed
on FamilyPresentsAsRemoved; the FamilyLookup port reads it alongside
`affordances` for the role_kind satisfaction check.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike


def _id(payload: dict[str, object]) -> UUID:
    return UUID(str(payload["family_id"]))


_INSERT_FAMILY_SQL = """
INSERT INTO proj_equipment_family_summary
    (family_id, name, status, version_tag, created_at,
     settings_schema_present, affordances, presents_as)
VALUES ($1, $2, 'Defined', NULL, $3, FALSE, $4::text[], ARRAY[]::UUID[])
ON CONFLICT (family_id) DO NOTHING
"""

_UPDATE_VERSIONED_SQL = """
UPDATE proj_equipment_family_summary
SET status = 'Versioned',
    version_tag = $2,
    versioned_at = $3,
    affordances = $4::text[],
    updated_at = now()
WHERE family_id = $1
"""

_UPDATE_DEPRECATED_SQL = """
UPDATE proj_equipment_family_summary
SET status = 'Deprecated',
    deprecated_at = $2,
    updated_at = now()
WHERE family_id = $1
"""

_UPDATE_SCHEMA_PRESENT_SQL = """
UPDATE proj_equipment_family_summary
SET settings_schema_present = $2, updated_at = now()
WHERE family_id = $1
"""

_UPDATE_PRESENTS_AS_ADDED_SQL = """
UPDATE proj_equipment_family_summary
SET presents_as = (
    SELECT ARRAY(
        SELECT DISTINCT unnest(presents_as || ARRAY[$2]::UUID[])
    )
),
    updated_at = now()
WHERE family_id = $1
"""

_UPDATE_PRESENTS_AS_REMOVED_SQL = """
UPDATE proj_equipment_family_summary
SET presents_as = array_remove(presents_as, $2),
    updated_at = now()
WHERE family_id = $1
"""


class FamilySummaryProjection:
    """Maintains the `proj_equipment_family_summary` read model."""

    name = "proj_equipment_family_summary"
    subscribed_event_types = frozenset(
        {
            "FamilyDefined",
            "FamilyVersioned",
            "FamilyDeprecated",
            "FamilySettingsSchemaUpdated",
            "FamilyPresentsAsAdded",
            "FamilyPresentsAsRemoved",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "FamilyDefined":
                await conn.execute(
                    _INSERT_FAMILY_SQL,
                    _id(event.payload),
                    event.payload["name"],
                    datetime.fromisoformat(str(event.payload["occurred_at"])),
                    list(event.payload.get("affordances", [])),
                )
            case "FamilyVersioned":
                await conn.execute(
                    _UPDATE_VERSIONED_SQL,
                    _id(event.payload),
                    event.payload["version_tag"],
                    datetime.fromisoformat(str(event.payload["occurred_at"])),
                    list(event.payload.get("affordances", [])),
                )
            case "FamilyDeprecated":
                await conn.execute(
                    _UPDATE_DEPRECATED_SQL,
                    _id(event.payload),
                    datetime.fromisoformat(str(event.payload["occurred_at"])),
                )
            case "FamilySettingsSchemaUpdated":
                await conn.execute(
                    _UPDATE_SCHEMA_PRESENT_SQL,
                    _id(event.payload),
                    event.payload.get("settings_schema") is not None,
                )
            case "FamilyPresentsAsAdded":
                await conn.execute(
                    _UPDATE_PRESENTS_AS_ADDED_SQL,
                    _id(event.payload),
                    UUID(str(event.payload["role_id"])),
                )
            case "FamilyPresentsAsRemoved":
                await conn.execute(
                    _UPDATE_PRESENTS_AS_REMOVED_SQL,
                    _id(event.payload),
                    UUID(str(event.payload["role_id"])),
                )
            case _:
                pass


__all__ = ["FamilySummaryProjection"]
