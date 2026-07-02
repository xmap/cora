"""RunActorInvolvementProjection: which in-flight runs is an actor behind?

CORA's first cross-BC projection. Folds TWO streams into one read model
(`proj_run_actor_involvement`) that backs the authority-revocation
kill-switch: when an actor's grant is revoked, a compensation subscriber
looks up that actor's in-flight runs here and holds them.

Two involvement kinds per (actor, run):
  - starter:    the actor who started the run. Read from the RunStarted
                envelope `principal_id` (RunStarted carries no actor in
                its payload), so this is the one projection that folds an
                envelope field into the row key.
  - supervisor: an actor who authored a RunSupervision-context Decision
                linked to the run (e.g. the RunSupervisor agent that
                holds / resumes it). Read from the DecisionRegistered
                payload's `decided_by` + `inputs.run_id`.

Subscribed events:
  - RunStarted          -> INSERT (kind=starter, status=Running)
  - RunHeld             -> UPDATE status=Held        (all rows for run_id)
  - RunResumed          -> UPDATE status=Running     (all rows for run_id)
  - RunCompleted/Aborted/Stopped/Truncated -> UPDATE terminal status
  - DecisionRegistered  -> context=RunSupervision only: INSERT
                           (kind=supervisor) at the run's current status.

Global event order guarantees RunStarted precedes any RunSupervision
Decision for the run, so the supervisor INSERT copies the starter row's
current status (fallback 'Running' if somehow absent). All branches
idempotent (ON CONFLICT DO NOTHING on INSERT; status UPDATE is a plain
overwrite). Terminal rows stay in the table for audit but fall out of the
in-flight partial index the lookup queries.

Cross-stream note: this projection subscribes to event_type strings from
two aggregates (Run + Decision). The framework matches on event_type
only (no stream-type scoping), and the DecisionRegistered arm guards on
`payload.context` so non-supervision Decisions are ignored.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_DECISION_CONTEXT_RUN_SUPERVISION = "RunSupervision"

_INSERT_STARTER_SQL = """
INSERT INTO proj_run_actor_involvement
    (actor_id, run_id, involvement_kind, status, created_at)
VALUES ($1, $2, 'starter', 'Running', $3)
ON CONFLICT (actor_id, run_id, involvement_kind) DO NOTHING
"""

# The supervisor row copies the run's current status from the existing
# starter row. RunStarted always precedes a RunSupervision Decision in
# global commit order, so the starter row exists with the accurate current
# status (including Held / a terminal) by the time this runs. The
# INSERT ... SELECT is guarded on the starter row's existence (the SELECT
# yields no row otherwise), so a supervision Decision for a run with no
# starter row (e.g. a principal-less legacy RunStarted that was skipped)
# creates NO phantom supervisor row rather than defaulting to a wrongly
# in-flight 'Running'.
_INSERT_SUPERVISOR_SQL = """
INSERT INTO proj_run_actor_involvement
    (actor_id, run_id, involvement_kind, status, created_at)
SELECT $1, $2, 'supervisor', starter.status, $3
FROM proj_run_actor_involvement AS starter
WHERE starter.run_id = $2 AND starter.involvement_kind = 'starter'
ON CONFLICT (actor_id, run_id, involvement_kind) DO NOTHING
"""

_UPDATE_STATUS_SQL = """
UPDATE proj_run_actor_involvement
SET status = $2, updated_at = now()
WHERE run_id = $1
"""

_EVENT_TO_STATUS = {
    "RunHeld": "Held",
    "RunResumed": "Running",
    "RunCompleted": "Completed",
    "RunAborted": "Aborted",
    "RunStopped": "Stopped",
    "RunTruncated": "Truncated",
}


class RunActorInvolvementProjection:
    """Maintains the `proj_run_actor_involvement` read model."""

    name = "proj_run_actor_involvement"
    subscribed_event_types = frozenset(
        {
            "RunStarted",
            "RunHeld",
            "RunResumed",
            "RunCompleted",
            "RunAborted",
            "RunStopped",
            "RunTruncated",
            "DecisionRegistered",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "RunStarted":
            # The starter is the envelope principal_id, not a payload field.
            # A run with no recorded principal (should not happen for a real
            # start) is skipped: there is no actor to be "behind" it.
            if event.principal_id is None:
                return
            await conn.execute(
                _INSERT_STARTER_SQL,
                event.principal_id,
                UUID(event.payload["run_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return
        if event.event_type == "DecisionRegistered":
            payload = event.payload
            if payload.get("context") != _DECISION_CONTEXT_RUN_SUPERVISION:
                return
            inputs = payload.get("inputs") or {}
            run_id_raw = inputs.get("run_id")
            if run_id_raw is None:
                return
            await conn.execute(
                _INSERT_SUPERVISOR_SQL,
                UUID(payload["decided_by"]),
                UUID(run_id_raw),
                datetime.fromisoformat(payload["occurred_at"]),
            )
            return
        new_status = _EVENT_TO_STATUS.get(event.event_type)
        if new_status is None:
            return
        await conn.execute(
            _UPDATE_STATUS_SQL,
            UUID(event.payload["run_id"]),
            new_status,
        )


__all__ = ["RunActorInvolvementProjection"]
