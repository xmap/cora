"""AcquisitionSummaryProjection: folds the Acquisition aggregate's
single AcquisitionRecorded event into the
`proj_data_acquisition_summary` read model.

Subscribed events:
  - AcquisitionRecorded -> INSERT (status='Recorded')

The Acquisition is terminal at genesis (one event ever per stream),
so this projection only ever inserts. INSERT ON CONFLICT
(acquisition_id) DO NOTHING keeps replay idempotent.

Dual-time columns: `captured_at` comes straight from the payload
(instrument wall-clock); `recorded_at` is the event's `occurred_at`
payload key (CORA-side wall-clock). The carrier dicts (settings,
evidence) land as JSONB; both may be the empty object but never NULL.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_ACQUISITION_SQL = """
INSERT INTO proj_data_acquisition_summary
    (acquisition_id, dataset_id, producing_asset_id, producing_run_id,
     captured_at, settings, evidence, recorded_at, recorded_by, status)
VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, $9, 'Recorded')
ON CONFLICT (acquisition_id) DO NOTHING
"""


class AcquisitionSummaryProjection:
    """Maintains the `proj_data_acquisition_summary` read model."""

    name = "proj_data_acquisition_summary"
    subscribed_event_types = frozenset({"AcquisitionRecorded"})

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "AcquisitionRecorded":
                payload = event.payload
                producing_run_id = (
                    UUID(payload["producing_run_id"]) if payload.get("producing_run_id") else None
                )
                await conn.execute(
                    _INSERT_ACQUISITION_SQL,
                    UUID(payload["acquisition_id"]),
                    UUID(payload["dataset_id"]),
                    UUID(payload["producing_asset_id"]),
                    producing_run_id,
                    datetime.fromisoformat(payload["captured_at"]),
                    json.dumps(payload["settings"]),
                    json.dumps(payload["evidence"]),
                    datetime.fromisoformat(payload["occurred_at"]),
                    UUID(payload["recorded_by"]),
                )
            case _:
                pass


__all__ = ["AcquisitionSummaryProjection"]
