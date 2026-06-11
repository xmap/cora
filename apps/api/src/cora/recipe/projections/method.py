"""MethodSummaryProjection: folds the Method aggregate's 6 events
into the `proj_recipe_method_summary` read model that backs
`GET /methods` and supplies lifecycle timestamps to
`GET /methods/{id}` (Path C).

Subscribed events:
  - MethodDefined                  -> INSERT (status=Defined,
                                              version_tag=NULL,
                                              created_at=payload.occurred_at,
                                              parameters_schema_present=FALSE,
                                              required_roles='[]')
  - MethodVersioned                -> UPDATE status=Versioned + version_tag
                                              from payload +
                                              versioned_at=payload.occurred_at
                                              (overwritten on each re-version
                                              — state always holds latest
                                              tag, projection mirrors that)
  - MethodDeprecated               -> UPDATE status=Deprecated +
                                              deprecated_at=payload.occurred_at
                                              (version_tag preserved on
                                              purpose; the audit trail of
                                              "last revised at version X
                                              before deprecation" stays
                                              visible)
  - MethodParametersSchemaUpdated  -> UPDATE parameters_schema_present
                                              (TRUE if parameters_schema is
                                              non-NULL; FALSE if cleared
                                              via NULL)
  - MethodRequiredRoleAdded        -> UPDATE required_roles to include the
                                              new role (append-and-sort the
                                              dict shape; sort by role_name
                                              for byte-stable replay)
  - MethodRequiredRoleRemoved      -> UPDATE required_roles to drop the
                                              role whose role_name matches
                                              the payload (filter the
                                              jsonb array; sort preserved)

`versioned_at` / `deprecated_at` source: aggregate state stays minimal
per Chassaing/Pellegrini/Reynhout decider-purity guidance; lifecycle
timestamps live here on the projection per Dudycz "pragmatic redundancy"
exception for read-side convenience + K8s ObjectMeta / GitHub /
AIP-142 resource-API precedent (Path C lock).

All branches idempotent. `version_tag` lands in the projection ONLY
on MethodVersioned; the Defined INSERT leaves it NULL and the
Deprecated UPDATE doesn't touch it. `parameters_schema_present` is
TRUE iff the latest `MethodParametersSchemaUpdated.parameters_schema`
payload was non-NULL; the schema content itself lives in the event
stream (loaded on demand, not projected to keep the summary table
small). Mirrors `FamilySummaryProjection` (Equipment 5g-a).

`needed_family_ids` from the genesis payload is intentionally NOT
in this projection: it's a list, the keyset+filter shape doesn't
need it, and a future `proj_recipe_method_capabilities` join
projection can carry it when use cases demand "all methods needing
Family X".
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_METHOD_SQL = """
INSERT INTO proj_recipe_method_summary
    (method_id, name, status, version_tag, created_at,
     parameters_schema_present, required_roles)
VALUES ($1, $2, 'Defined', NULL, $3, FALSE, '[]'::jsonb)
ON CONFLICT (method_id) DO NOTHING
"""

_UPDATE_VERSIONED_SQL = """
UPDATE proj_recipe_method_summary
SET status = 'Versioned',
    version_tag = $2,
    versioned_at = $3,
    content_hash = $4,
    updated_at = now()
WHERE method_id = $1
"""

_UPDATE_DEPRECATED_SQL = """
UPDATE proj_recipe_method_summary
SET status = 'Deprecated',
    deprecated_at = $2,
    updated_at = now()
WHERE method_id = $1
"""

_UPDATE_PARAMETERS_SCHEMA_PRESENT_SQL = """
UPDATE proj_recipe_method_summary
SET parameters_schema_present = $2, updated_at = now()
WHERE method_id = $1
"""

# required_roles is materialized as a single jsonb column (list of
# role-objects, sorted by role_name for byte-stable replay). The two
# mutations use pure SQL jsonb operators (jsonb_agg + DISTINCT ON for
# add, WHERE filter + jsonb_agg for remove), mirroring the
# proj_equipment_asset_summary.owners + alternate_identifiers
# convention. Pure-SQL avoids the asyncpg jsonb-decoding ambiguity
# (PG returns jsonb as Python list when a codec is registered or as
# JSON-encoded string by default) and keeps the work atomic in one
# statement.
_UPDATE_REQUIRED_ROLE_ADDED_SQL = """
UPDATE proj_recipe_method_summary
SET required_roles = COALESCE(
        (
            SELECT jsonb_agg(elem ORDER BY elem->>'role_name')
            FROM (
                SELECT DISTINCT ON (elem->>'role_name') elem
                FROM jsonb_array_elements(
                    required_roles || jsonb_build_array($2::jsonb)
                ) AS elem
                ORDER BY elem->>'role_name'
            ) AS dedup
        ),
        '[]'::jsonb
    ),
    updated_at = now()
WHERE method_id = $1
"""

_UPDATE_REQUIRED_ROLE_REMOVED_SQL = """
UPDATE proj_recipe_method_summary
SET required_roles = COALESCE(
        (
            SELECT jsonb_agg(elem ORDER BY elem->>'role_name')
            FROM jsonb_array_elements(required_roles) AS elem
            WHERE elem->>'role_name' <> $2::text
        ),
        '[]'::jsonb
    ),
    updated_at = now()
WHERE method_id = $1
"""


class MethodSummaryProjection:
    """Maintains the `proj_recipe_method_summary` read model."""

    name = "proj_recipe_method_summary"
    subscribed_event_types = frozenset(
        {
            "MethodDefined",
            "MethodVersioned",
            "MethodDeprecated",
            "MethodParametersSchemaUpdated",
            "MethodRequiredRoleAdded",
            "MethodRequiredRoleRemoved",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "MethodDefined":
                await conn.execute(
                    _INSERT_METHOD_SQL,
                    UUID(event.payload["method_id"]),
                    event.payload["name"],
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "MethodVersioned":
                # content_hash: pre-rollout MethodVersioned events have no
                # field; passing None leaves the projection column NULL,
                # matching aggregate-state semantics.
                await conn.execute(
                    _UPDATE_VERSIONED_SQL,
                    UUID(event.payload["method_id"]),
                    event.payload["version_tag"],
                    datetime.fromisoformat(event.payload["occurred_at"]),
                    event.payload.get("content_hash"),
                )
            case "MethodDeprecated":
                await conn.execute(
                    _UPDATE_DEPRECATED_SQL,
                    UUID(event.payload["method_id"]),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "MethodParametersSchemaUpdated":
                await conn.execute(
                    _UPDATE_PARAMETERS_SCHEMA_PRESENT_SQL,
                    UUID(event.payload["method_id"]),
                    event.payload.get("parameters_schema") is not None,
                )
            case "MethodRequiredRoleAdded":
                # Build the role-object dict that gets union'd into
                # the existing array. The pool's jsonb codec
                # (`encoder=json.dumps`) serializes Python dicts on
                # the wire; the SQL cast `$2::jsonb` then wraps the
                # encoded bytes back as a JSONB value that
                # `jsonb_build_array` can wrap. Mirrors the
                # `_canonical_owner_jsonb` precedent in
                # cora.equipment.projections.asset. The SQL uses
                # DISTINCT ON (role_name) so a re-replay with the
                # same role_name (rare, only fires during a
                # projection rebuild) keeps the latest entry; the
                # SQL's ORDER BY role_name sorts the output for byte-
                # stable persistence.
                # Layer 3 sub-slice 3D: role_kind conditionally
                # rendered (only when non-None) for byte-stable
                # legacy payload preservation. family_id may be
                # None for the role_kind path.
                role_jsonb: dict[str, object] = {
                    "role_name": event.payload["role_name"],
                    "family_id": event.payload.get("family_id"),
                    "required_ports": list(event.payload.get("required_ports", [])),
                    "optional": bool(event.payload.get("optional", False)),
                }
                role_kind = event.payload.get("role_kind")
                if role_kind is not None:
                    role_jsonb["role_kind"] = role_kind
                await conn.execute(
                    _UPDATE_REQUIRED_ROLE_ADDED_SQL,
                    UUID(event.payload["method_id"]),
                    role_jsonb,
                )
            case "MethodRequiredRoleRemoved":
                await conn.execute(
                    _UPDATE_REQUIRED_ROLE_REMOVED_SQL,
                    UUID(event.payload["method_id"]),
                    event.payload["role_name"],
                )
            case _:
                pass


__all__ = ["MethodSummaryProjection"]
