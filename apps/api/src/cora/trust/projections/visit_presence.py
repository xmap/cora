"""VisitPresenceProjection: folds VisitCheckedIn / VisitCheckedOut events
into the `proj_trust_visit_presence` read model.

Subscribed events:
  - VisitCheckedIn  -> INSERT row with check_out_at=NULL
                       ON CONFLICT DO NOTHING (replay idempotency)
  - VisitCheckedOut -> UPDATE check_out_at where (visit_id, actor_id, NULL)
                       (naturally idempotent on replay)

PK on (visit_id, actor_id, check_in_at) lets the same actor check in
again after checking out -- each cycle is a separate row.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_TERMINAL: frozenset[str] = frozenset(
    {"VisitCompleted", "VisitCancelled", "VisitAborted", "VisitVoided"}
)
_CLOSING: frozenset[str] = frozenset({"VisitCheckedOut", "VisitPresenceClosed"})
_SUBSCRIBED: frozenset[str] = frozenset({"VisitCheckedIn"}) | _CLOSING | _TERMINAL

_INSERT_PRESENCE_SQL = """
INSERT INTO proj_trust_visit_presence
    (visit_id, actor_id, mode, check_in_at, check_out_at)
VALUES ($1, $2, $3, $4, NULL)
ON CONFLICT (visit_id, actor_id, check_in_at) DO NOTHING
"""

# Updates the OPEN entry for this (visit_id, actor_id); naturally idempotent
# because second replay finds zero rows with `check_out_at IS NULL`.
_UPDATE_PRESENCE_SQL = """
UPDATE proj_trust_visit_presence
SET check_out_at = $3, updated_at = now()
WHERE visit_id = $1 AND actor_id = $2 AND check_out_at IS NULL
"""

# A Visit reaching a terminal state ends presence for EVERY actor still open on
# it, which is the same rule the aggregate evolver applies in `_closed_at`. The
# two must agree: the aggregate is what a decider reads and this table is what a
# query reads, and a Visit that folds to "nobody present" while the read model
# still shows open rows would make presence unusable as evidence. Idempotent for
# the same reason as the single-actor update: a replay matches zero open rows.
_CLOSE_ALL_PRESENCE_SQL = """
UPDATE proj_trust_visit_presence
SET check_out_at = $2, updated_at = now()
WHERE visit_id = $1 AND check_out_at IS NULL
"""


class VisitPresenceProjection:
    """Maintains the `proj_trust_visit_presence` read model."""

    name = "proj_trust_visit_presence"
    subscribed_event_types = _SUBSCRIBED

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type not in _SUBSCRIBED:
            return

        payload = event.payload
        visit_id = UUID(payload["visit_id"])
        occurred_at = datetime.fromisoformat(payload["occurred_at"])

        if event.event_type in _TERMINAL:
            await conn.execute(_CLOSE_ALL_PRESENCE_SQL, visit_id, occurred_at)
            return

        actor_id = UUID(payload["actor_id"])

        match event.event_type:
            case "VisitCheckedIn":
                await conn.execute(
                    _INSERT_PRESENCE_SQL,
                    visit_id,
                    actor_id,
                    payload["mode"],
                    occurred_at,
                )
            case "VisitCheckedOut" | "VisitPresenceClosed":
                # Same row update for both: they differ in cause, which the
                # event type already records, not in what happens to the row.
                await conn.execute(
                    _UPDATE_PRESENCE_SQL,
                    visit_id,
                    actor_id,
                    occurred_at,
                )
            case _:  # pragma: no cover  # _SUBSCRIBED gate above prevents reaching here
                pass


__all__ = ["VisitPresenceProjection"]
