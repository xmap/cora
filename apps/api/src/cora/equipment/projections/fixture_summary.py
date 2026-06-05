"""FixtureSummaryProjection: folds Fixture stream events into the
`proj_equipment_fixture_summary` read model.

Subscribed events (v1):
  - FixtureRegistered          -> INSERT (snapshot of assembly_content_hash,
                                  surface_id, plus binding_count and
                                  override_count for cheap summary reads).
  - FixturePersistentIdAssigned -> UPDATE persistent_id JSONB with
                                  {scheme, value} for the assigned
                                  PIDINST v1.0 Property 1 identifier
                                  (Fixture-tier PIDINST integration).

Genesis is single-event (FixtureRegistered, idempotent via ON CONFLICT
DO NOTHING). Subsequent mutations stay append-only-monotonic; the
PIDINST assign is the first Fixture-stream mutation past genesis.
The full slot_asset_bindings stays in the event payload; this read
model is summary-only by design.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from typing import cast
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_FIXTURE_SQL = """
INSERT INTO proj_equipment_fixture_summary
    (fixture_id, assembly_id, assembly_content_hash, surface_id,
     binding_count, override_count, created_at)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (fixture_id) DO NOTHING
"""


_UPDATE_FIXTURE_PERSISTENT_ID_ASSIGNED_SQL = """
UPDATE proj_equipment_fixture_summary
SET persistent_id = jsonb_build_object(
        'scheme', $2::text,
        'value', $3::text
    ),
    updated_at = now()
WHERE fixture_id = $1
"""


class FixtureSummaryProjection:
    """Maintains the `proj_equipment_fixture_summary` read model."""

    name = "proj_equipment_fixture_summary"
    subscribed_event_types = frozenset(
        {
            "FixtureRegistered",
            "FixturePersistentIdAssigned",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "FixtureRegistered":
                payload = event.payload
                bindings = cast("list[dict[str, object]]", payload["slot_asset_bindings"])
                overrides = cast("dict[str, object]", payload["parameter_overrides"])
                await conn.execute(
                    _INSERT_FIXTURE_SQL,
                    UUID(str(payload["fixture_id"])),
                    UUID(str(payload["assembly_id"])),
                    payload["assembly_content_hash"],
                    UUID(str(payload["surface_id"])),
                    len(bindings),
                    len(overrides),
                    datetime.fromisoformat(str(payload["occurred_at"])),
                )
            case "FixturePersistentIdAssigned":
                await conn.execute(
                    _UPDATE_FIXTURE_PERSISTENT_ID_ASSIGNED_SQL,
                    UUID(str(event.payload["fixture_id"])),
                    event.payload["persistent_id_scheme"],
                    event.payload["persistent_id_value"],
                )
            case _:
                pass


__all__ = ["FixtureSummaryProjection"]
