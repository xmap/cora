"""ShortfallSummaryProjection: folds the Shortfall aggregate's single
ShortfallRecorded event into the `proj_data_shortfall_summary` read
model.

Subscribed events:
  - ShortfallRecorded -> INSERT (status='Recorded')

The Shortfall is terminal at genesis (one event ever per stream), so
this projection only ever inserts. INSERT ... ON CONFLICT
(shortfall_id) DO NOTHING keeps replay idempotent.

Dual-time columns: `file_modified_at` / `run_ended_at` are the
finality evidence pair the reason judgement was made from; `recorded_at`
is the event's `occurred_at` payload key (CORA-side wall-clock).
`commanded_projection_count` and `dropped_frame_count` are nullable
because the FILE may not record them, not because the read fell short:
`Description` carries each as None when the corresponding dataset is
absent from the layout. A null commanded count is what makes the
shortfall unquantifiable rather than absent, so it must stay
distinguishable from zero.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_SHORTFALL_SQL = """
INSERT INTO proj_data_shortfall_summary
    (shortfall_id, producing_run_id, capture_path_id, host, root,
     projection_count, commanded_projection_count, dropped_frame_count,
     reason, file_modified_at, run_ended_at, recorded_at, recorded_by,
     status)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, 'Recorded')
ON CONFLICT (shortfall_id) DO NOTHING
"""


class ShortfallSummaryProjection:
    """Maintains the `proj_data_shortfall_summary` read model."""

    name = "proj_data_shortfall_summary"
    subscribed_event_types = frozenset({"ShortfallRecorded"})

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "ShortfallRecorded":
                payload = event.payload
                await conn.execute(
                    _INSERT_SHORTFALL_SQL,
                    UUID(payload["shortfall_id"]),
                    UUID(payload["producing_run_id"]),
                    UUID(payload["capture_path_id"]),
                    payload["host"],
                    payload["root"],
                    payload["projection_count"],
                    payload["commanded_projection_count"],
                    payload["dropped_frame_count"],
                    payload["reason"],
                    datetime.fromisoformat(payload["file_modified_at"]),
                    datetime.fromisoformat(payload["run_ended_at"]),
                    datetime.fromisoformat(payload["occurred_at"]),
                    UUID(payload["recorded_by"]),
                )
            case _:
                pass


__all__ = ["ShortfallSummaryProjection"]
