"""DatasetSummaryProjection: folds the Dataset aggregate's 2 lifecycle
events into the `proj_data_dataset_summary` read model that backs
`GET /datasets`.

Subscribed events:
  - DatasetRegistered  -> INSERT (status=Registered, name + uri +
                                  producing_run_id? + subject_id? +
                                  used_calibration_ids (12c) from
                                  genesis payload)
  - DatasetDiscarded   -> UPDATE status=Discarded   (terminal)

Both branches idempotent. Genesis-event payload values
(producing_run_id, subject_id, used_calibration_ids) land on INSERT and
never change; the discard UPDATE only touches `status`. The audit
trail of "what was the producing Run / Subject / cited calibrations
for this discarded Dataset" stays visible in the projection.

`used_calibration_ids` surfaces the AsShot citation set
on the read model so downstream consumers (operator dashboards,
future Decision-derived advisories, agent subscribers) can query
"which reconstructions cited CalibrationRevision X" via the GIN-
indexed `@>` operator without folding the Dataset stream.
`.get("used_calibration_ids", [])` returns `[]` so legacy
rows backfill cleanly to an empty UUID array (additive-state
pattern mirroring Run.pinned_calibration_ids precedent).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_DATASET_SQL = """
INSERT INTO proj_data_dataset_summary
    (dataset_id, name, uri, producing_run_id, subject_id, status,
     created_at, used_calibration_ids, checksum_algorithm, checksum_value)
VALUES ($1, $2, $3, $4, $5, 'Registered', $6, $7::uuid[], $8, $9)
ON CONFLICT (dataset_id) DO NOTHING
"""

_UPDATE_DISCARDED_SQL = """
UPDATE proj_data_dataset_summary
SET status = 'Discarded', updated_at = now()
WHERE dataset_id = $1
"""


class DatasetSummaryProjection:
    """Maintains the `proj_data_dataset_summary` read model."""

    name = "proj_data_dataset_summary"
    subscribed_event_types = frozenset({"DatasetRegistered", "DatasetDiscarded"})

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "DatasetRegistered":
                payload = event.payload
                producing_run_id = (
                    UUID(payload["producing_run_id"]) if payload.get("producing_run_id") else None
                )
                subject_id = UUID(payload["subject_id"]) if payload.get("subject_id") else None
                # Forward-compat: legacy DatasetRegistered payloads have
                # no used_calibration_ids key; .get(..., []) returns [] so
                # legacy rows land with an empty UUID array.
                used_calibration_ids = [UUID(c) for c in payload.get("used_calibration_ids", [])]
                # Nested per to_payload's shape: {"checksum": {"algorithm",
                # "value"}}; flat keys do not exist on the wire.
                checksum = payload["checksum"]
                await conn.execute(
                    _INSERT_DATASET_SQL,
                    UUID(payload["dataset_id"]),
                    payload["name"],
                    payload["uri"],
                    producing_run_id,
                    subject_id,
                    datetime.fromisoformat(payload["occurred_at"]),
                    used_calibration_ids,
                    checksum["algorithm"],
                    checksum["value"],
                )
            case "DatasetDiscarded":
                await conn.execute(
                    _UPDATE_DISCARDED_SQL,
                    UUID(event.payload["dataset_id"]),
                )
            case _:
                pass


__all__ = ["DatasetSummaryProjection"]
