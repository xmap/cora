"""RatificationCoverageProjection: the consequence gate's coverage read model.

Answers "is action `(target_action_id, command_name)` covered by a GRANTED
Ratification?" for the `ConsequenceLookup` port that Run BC's `stop_run` gate
consults (the target action is the run being stopped, so the consumer passes
`run_id` as the `target_action_id`).

The scope keys (`target_action_id`, `command_name`) live only on the genesis
event (`RatificationRequested`); `RatificationGranted` / `RatificationDenied` are
keyed by `ratification_id` alone. So this projection carries the scope from
genesis and folds the status forward by `ratification_id`:

  - RatificationRequested -> INSERT (ratification_id, target_action_id,
    command_name, status='Requested')
  - RatificationGranted   -> UPDATE status='Granted'  WHERE ratification_id
  - RatificationDenied    -> UPDATE status='Denied'   WHERE ratification_id

The lookup filters to `status = 'Granted'`. Rows are retained across status
changes (a Denied row stays, auditable); the coverage query keys on status, not
on row presence.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_SQL = """
INSERT INTO proj_trust_ratification_coverage
    (ratification_id, target_action_id, command_name, status, created_at)
VALUES ($1, $2, $3, 'Requested', $4)
ON CONFLICT (ratification_id) DO NOTHING
"""

_UPDATE_STATUS_SQL = """
UPDATE proj_trust_ratification_coverage
SET status = $2, updated_at = now()
WHERE ratification_id = $1
"""

_EVENT_TO_STATUS = {
    "RatificationGranted": "Granted",
    "RatificationDenied": "Denied",
}


class RatificationCoverageProjection:
    """Maintains the `proj_trust_ratification_coverage` read model."""

    name = "proj_trust_ratification_coverage"
    subscribed_event_types = frozenset(
        {
            "RatificationRequested",
            "RatificationGranted",
            "RatificationDenied",
        }
    )

    async def apply(self, event: StoredEvent, conn: ConnectionLike) -> None:
        if event.event_type == "RatificationRequested":
            await conn.execute(
                _INSERT_SQL,
                UUID(event.payload["ratification_id"]),
                UUID(event.payload["target_action_id"]),
                event.payload["command_name"],
                event.occurred_at,
            )
            return
        new_status = _EVENT_TO_STATUS.get(event.event_type)
        if new_status is None:
            return
        await conn.execute(
            _UPDATE_STATUS_SQL,
            UUID(event.payload["ratification_id"]),
            new_status,
        )


__all__ = ["RatificationCoverageProjection"]
