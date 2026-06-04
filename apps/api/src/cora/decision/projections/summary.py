"""DecisionSummaryProjection: folds the single DecisionRegistered
event into the `proj_decision_summary` read model that backs
`GET /decisions`.

Subscribed events:
  - DecisionRegistered  -> INSERT (full genesis payload + computed
                                   confidence_band)

Decision is immutable per the BC's design: one event = one decision,
no transitions, no terminal. Subsequent enrichments live on a
separate reasoning-entries stream (DecisionLogbookOpened/Closed are
internal logbook bookkeeping; not subscribed here).

`confidence_band` is denormalized at INSERT via the same
`confidence_band()` function the read-side uses, so categorical
filtering is a fast indexed lookup.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.decision.aggregates.decision.state import confidence_band
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_DECISION_SQL = """
INSERT INTO proj_decision_summary
    (decision_id, actor_id, rule, parent_id,
     confidence, confidence_band, choice, created_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (decision_id) DO NOTHING
"""


class DecisionSummaryProjection:
    """Maintains the `proj_decision_summary` read model."""

    name = "proj_decision_summary"
    subscribed_event_types = frozenset({"DecisionRegistered"})

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type != "DecisionRegistered":
            return
        payload = event.payload
        parent_id = UUID(payload["parent_id"]) if payload.get("parent_id") else None
        confidence = payload.get("confidence")
        # confidence_band() returns None when confidence is None;
        # both column types are nullable per the migration's CHECK.
        band = confidence_band(confidence)
        await conn.execute(
            _INSERT_DECISION_SQL,
            UUID(payload["decision_id"]),
            UUID(payload["actor_id"]),
            payload.get("rule"),
            parent_id,
            confidence,
            band.value if band is not None else None,
            payload["choice"],
            datetime.fromisoformat(payload["occurred_at"]),
        )


__all__ = ["DecisionSummaryProjection"]
