"""ProcedureSummaryProjection: folds the Procedure aggregate's events
into the `proj_operation_procedure_summary` read model that backs
`GET /procedures`.

Subscribed events:
  - ProcedureRegistered          -> INSERT (status='Defined', last_status_*=NULL,
                                            interrupted_at=NULL, activity_logbook_id=NULL)
  - ProcedureStarted             -> UPDATE status='Running'   + status-change ts
  - ProcedureCompleted           -> UPDATE status='Completed' + status-change ts
  - ProcedureAborted             -> UPDATE status='Aborted'   + status-change ts
                                                              + last_status_reason
  - ProcedureTruncated           -> UPDATE status='Truncated' + status-change ts
                                                              + last_status_reason
                                                              + interrupted_at
  - ProcedureHeld                -> UPDATE status='Held'      + status-change ts
                                                              + last_status_reason
  - ProcedureResumed             -> UPDATE status='Running'   + status-change ts
                                                              (clears last_status_reason:
                                                               Running is not reason-bearing)
  - ProcedureActivitiesLogbookOpened  -> UPDATE activity_logbook_id (status NOT touched;
                                                             logbook is orthogonal
                                                             to lifecycle)
  - ProcedureIterationStarted    -> UPDATE iteration_count = iteration_index
                                           (status NOT touched; iteration is
                                           orthogonal to lifecycle)

`ProcedureIterationEnded` is deliberately NOT subscribed: the iteration
denorm tracks iterations begun, and the convergence-verdict projection
(`converged` false-rate) is a deferred watch item. `iteration_count` is
set to the operator-supplied `iteration_index` (replay-safe under
ordered per-stream delivery; equals the count because the start decider
enforces strict-successor indexing).

The 6 status-change UPDATEs (Started / Completed / Aborted / Truncated /
Held / Resumed) keep per-event SQL constants rather than a parameterized
`_UPDATE_STATUS_SQL`. The "hoist at the 5th arm" note from the 4-arm era
was re-evaluated when Held/Resumed landed: the arms are NOT uniform
(Truncated also sets interrupted_at, Resumed CLEARS last_status_reason
rather than setting it), so a single parameterized SQL would need
conditional columns and read worse than the explicit constants. Revisit
only if a future arm restores uniformity.

All branches idempotent. The status CHECK was widened to admit 'Held' in
migration `20260621060000_proc_summary_status_admit_held` (Resumed maps
back to 'Running', so 'Held' is the only new persisted value). See
[[project_resumable_conduct_design]].
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_PROCEDURE_SQL = """
INSERT INTO proj_operation_procedure_summary
    (procedure_id, name, kind, target_asset_ids, parent_run_id, status,
     activity_logbook_id, registered_at,
     last_status_changed_at, last_status_reason, interrupted_at,
     recipe_id, iteration_count)
VALUES ($1, $2, $3, $4::uuid[], $5, 'Defined', NULL, $6, NULL, NULL, NULL, $7, 0)
ON CONFLICT (procedure_id) DO NOTHING
"""

_UPDATE_STARTED_SQL = """
UPDATE proj_operation_procedure_summary
SET status = 'Running',
    last_status_changed_at = $2,
    updated_at = now()
WHERE procedure_id = $1
"""

_UPDATE_COMPLETED_SQL = """
UPDATE proj_operation_procedure_summary
SET status = 'Completed',
    last_status_changed_at = $2,
    updated_at = now()
WHERE procedure_id = $1
"""

_UPDATE_ABORTED_SQL = """
UPDATE proj_operation_procedure_summary
SET status = 'Aborted',
    last_status_changed_at = $2,
    last_status_reason = $3,
    updated_at = now()
WHERE procedure_id = $1
"""

_UPDATE_TRUNCATED_SQL = """
UPDATE proj_operation_procedure_summary
SET status = 'Truncated',
    last_status_changed_at = $2,
    last_status_reason = $3,
    interrupted_at = $4,
    updated_at = now()
WHERE procedure_id = $1
"""

_UPDATE_HELD_SQL = """
UPDATE proj_operation_procedure_summary
SET status = 'Held',
    last_status_changed_at = $2,
    last_status_reason = $3,
    updated_at = now()
WHERE procedure_id = $1
"""

_UPDATE_RESUMED_SQL = """
UPDATE proj_operation_procedure_summary
SET status = 'Running',
    last_status_changed_at = $2,
    last_status_reason = NULL,
    updated_at = now()
WHERE procedure_id = $1
"""

_UPDATE_STEPS_LOGBOOK_OPENED_SQL = """
UPDATE proj_operation_procedure_summary
SET activity_logbook_id = $2,
    updated_at = now()
WHERE procedure_id = $1
"""

_UPDATE_ITERATION_STARTED_SQL = """
UPDATE proj_operation_procedure_summary
SET iteration_count = $2,
    updated_at = now()
WHERE procedure_id = $1
"""


class ProcedureSummaryProjection:
    """Maintains the `proj_operation_procedure_summary` read model."""

    name = "proj_operation_procedure_summary"
    subscribed_event_types = frozenset(
        {
            "ProcedureRegistered",
            "ProcedureStarted",
            "ProcedureCompleted",
            "ProcedureAborted",
            "ProcedureTruncated",
            "ProcedureHeld",
            "ProcedureResumed",
            "ProcedureActivitiesLogbookOpened",
            "ProcedureIterationStarted",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "ProcedureRegistered":
            payload = event.payload
            target_asset_ids = [UUID(a) for a in payload.get("target_asset_ids", [])]
            raw_parent = payload.get("parent_run_id")
            parent_run_id = UUID(raw_parent) if raw_parent is not None else None
            raw_recipe = payload.get("recipe_id")
            recipe_id = UUID(raw_recipe) if raw_recipe is not None else None
            await conn.execute(
                _INSERT_PROCEDURE_SQL,
                UUID(payload["procedure_id"]),
                payload["name"],
                payload["kind"],
                target_asset_ids,
                parent_run_id,
                datetime.fromisoformat(payload["occurred_at"]),
                recipe_id,
            )
            return

        if event.event_type == "ProcedureStarted":
            await conn.execute(
                _UPDATE_STARTED_SQL,
                UUID(event.payload["procedure_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return

        if event.event_type == "ProcedureCompleted":
            await conn.execute(
                _UPDATE_COMPLETED_SQL,
                UUID(event.payload["procedure_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return

        if event.event_type == "ProcedureAborted":
            await conn.execute(
                _UPDATE_ABORTED_SQL,
                UUID(event.payload["procedure_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
                event.payload["reason"],
            )
            return

        if event.event_type == "ProcedureTruncated":
            # Strict indexing matches the evolver's `from_stored` posture:
            # interrupted_at is required-on-the-payload (None | datetime),
            # not future-additive optional. Any stream lacking the
            # key is malformed, not legacy. Mirrors evolver fold.
            raw_interrupted_at = event.payload["interrupted_at"]
            interrupted_at = (
                datetime.fromisoformat(raw_interrupted_at)
                if raw_interrupted_at is not None
                else None
            )
            await conn.execute(
                _UPDATE_TRUNCATED_SQL,
                UUID(event.payload["procedure_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
                event.payload["reason"],
                interrupted_at,
            )
            return

        if event.event_type == "ProcedureHeld":
            await conn.execute(
                _UPDATE_HELD_SQL,
                UUID(event.payload["procedure_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
                event.payload["reason"],
            )
            return

        if event.event_type == "ProcedureResumed":
            await conn.execute(
                _UPDATE_RESUMED_SQL,
                UUID(event.payload["procedure_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return

        if event.event_type == "ProcedureActivitiesLogbookOpened":
            await conn.execute(
                _UPDATE_STEPS_LOGBOOK_OPENED_SQL,
                UUID(event.payload["procedure_id"]),
                UUID(event.payload["logbook_id"]),
            )
            return

        if event.event_type == "ProcedureIterationStarted":
            # iteration_count := iteration_index (operator-supplied, strict
            # successor). Set-to-index is idempotent under ordered per-stream
            # delivery, so re-delivery does not double-count.
            await conn.execute(
                _UPDATE_ITERATION_STARTED_SQL,
                UUID(event.payload["procedure_id"]),
                int(event.payload["iteration_index"]),
            )
            return

        # Unsubscribed event type (defensive; the worker shouldn't
        # deliver them given subscribed_event_types).
        return


__all__ = ["ProcedureSummaryProjection"]
