"""Kill-switch K2: the `proj_run_actor_involvement` read model.

Answers "which in-flight Runs does principal P drive?" for the authority-
revocation holder subscriber (K3). The starter of a Run is the RunStarted
event's ENVELOPE principal_id (the Authorize-gated issuer), not a payload field,
so this projection reads `event.principal_id`.

Involvement scope is STARTER-ONLY for v1, structured extensible: rows carry
`involvement_role='starter'` and the table reserves 'supervisor' for a later
additive fold (the HoldRun / ResumeRun envelope principals) that widens "drives"
to "started or supervises" without a schema change.

Lifecycle events (RunHeld ... RunTruncated) update `status` keyed by run_id, so
they touch every involvement row for the Run (one starter row today; more when
the supervisor arm lands). Terminal rows are retained, not deleted: the resolver
stays a pure fold and past involvement remains auditable. The lookup filters to
in-flight (status IN Running, Held).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_SQL = """
INSERT INTO proj_run_actor_involvement
    (principal_id, run_id, involvement_role, status, created_at)
VALUES ($1, $2, 'starter', 'Running', $3)
ON CONFLICT (principal_id, run_id) DO NOTHING
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
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "RunStarted":
            if event.principal_id is None:
                # No starter to attribute (legacy/backfilled event with no
                # envelope principal); nothing to resolve against, so skip.
                return
            await conn.execute(
                _INSERT_SQL,
                event.principal_id,
                UUID(event.payload["run_id"]),
                event.occurred_at,
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
