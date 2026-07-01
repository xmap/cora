"""ProcedureIterationsProjection: folds the Procedure iteration boundary
events into the per-iteration `proj_operation_procedure_iterations` read
model (one row per iteration).

Subscribed events:
  - ProcedureIterationStarted -> INSERT (procedure_id, iteration_index,
                                 started_at) ON CONFLICT DO NOTHING
  - ProcedureIterationEnded   -> UPDATE ended_at / converged / reason
                                 + the steering decision trail
                                 (advised_stop / model_ref / advised_next_point)
                                 WHERE (procedure_id, iteration_index)

This is the per-occurrence drill-down companion to the single-row
`proj_operation_procedure_summary.iteration_count` denorm: the summary
answers "how many iterations", this table answers "which iterations
converged / time per iteration / convergence rate" and, for a steered
conduct, "what the brain advised each pass". The verdict + steering trail
are already durable on the Procedure event stream, so this is a derived,
rebuildable projection, not a system-of-record entries table.

## Steering trail (TIER-1 replay)

The steering columns surface the recorded decision trail so a finished
GP-steered run is reconstructable by READING this read model (a non-
deterministic brain cannot be reconstructed by re-asking). `advised_stop`
/ `model_ref` / `advised_next_point` are read via `.get()` (absent on
pre-TIER-1 events + on plain convergence iterations, which leave them NULL).
`advised_next_point` is a jsonb coordinate map, encoded explicitly with a
`::jsonb` cast (same posture as the Calibration operating_point projection).

Both arms are replay-safe under ordered per-stream delivery:
ProcedureIterationStarted is INSERT-ON-CONFLICT-DO-NOTHING (re-delivery
is a no-op), ProcedureIterationEnded is UPDATE-by-PK (re-delivery sets
the same values). A truncate + replay re-derives the table.

The column shape deliberately equals the body a future
`entries_operation_procedure_iterations` substream would carry (item-5
promotion at the >100-iterations trigger), so promotion is a write-tier
shift with no event-shape change.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_ITERATION_SQL = """
INSERT INTO proj_operation_procedure_iterations
    (procedure_id, iteration_index, started_at)
VALUES ($1, $2, $3)
ON CONFLICT (procedure_id, iteration_index) DO NOTHING
"""

_UPDATE_ITERATION_ENDED_SQL = """
UPDATE proj_operation_procedure_iterations
SET ended_at = $3,
    converged = $4,
    reason = $5,
    advised_stop = $6,
    model_ref = $7,
    advised_next_point = $8::jsonb,
    updated_at = now()
WHERE procedure_id = $1 AND iteration_index = $2
"""


class ProcedureIterationsProjection:
    """Maintains the `proj_operation_procedure_iterations` read model."""

    name = "proj_operation_procedure_iterations"
    subscribed_event_types = frozenset(
        {
            "ProcedureIterationStarted",
            "ProcedureIterationEnded",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "ProcedureIterationStarted":
            await conn.execute(
                _INSERT_ITERATION_SQL,
                UUID(event.payload["procedure_id"]),
                int(event.payload["iteration_index"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return

        if event.event_type == "ProcedureIterationEnded":
            advised_next_point = event.payload.get("advised_next_point")
            await conn.execute(
                _UPDATE_ITERATION_ENDED_SQL,
                UUID(event.payload["procedure_id"]),
                int(event.payload["iteration_index"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
                event.payload["converged"],
                event.payload["reason"],
                event.payload.get("advised_stop"),
                event.payload.get("model_ref"),
                json.dumps(advised_next_point) if advised_next_point is not None else None,
            )
            return

        # Unsubscribed event type (defensive; the worker shouldn't
        # deliver them given subscribed_event_types).
        return


__all__ = ["ProcedureIterationsProjection"]
