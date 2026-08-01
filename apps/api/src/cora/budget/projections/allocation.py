"""AllocationSummaryProjection: folds the envelope's lifecycle into
the `proj_budget_allocation_summary` read model.

The envelope's one production query shape is by status, not by id:
`PostgresAllocationLookup.find_active` asks "which envelope is Active
right now, and what are its ceiling, window start, and campaign
binding?" That question fires on every gated LLM call and on every
CampaignClosed delivery, so it cannot be a stream scan; the
projection carries exactly the columns the lookup selects plus the
lifecycle timestamps an operator surface would list.

Balance is deliberately NOT projected: the envelope's spend folds
from `entries_decision_inferences` at read time (the design's
never-stored-balance stance), and only the seal freezes a snapshot
(`spent_usd_at_seal`). `end_reason` stays on the aggregate for the
same reason `cost_basis` stays off the language-model projection:
no consumer reads it from the read model.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_SQL = """
INSERT INTO proj_budget_allocation_summary
    (allocation_id, ceiling_usd, campaign_id, note, status,
     granted_at, created_at)
VALUES ($1, $2, $3, $4, 'Granted', $5, $5)
ON CONFLICT (allocation_id) DO NOTHING
"""

_UPDATE_ACTIVATED_SQL = """
UPDATE proj_budget_allocation_summary
SET status = 'Active',
    activated_at = $2,
    updated_at = now()
WHERE allocation_id = $1
"""

_UPDATE_CEILING_SQL = """
UPDATE proj_budget_allocation_summary
SET ceiling_usd = $2,
    updated_at = now()
WHERE allocation_id = $1
"""

_UPDATE_SEALED_SQL = """
UPDATE proj_budget_allocation_summary
SET status = 'Sealed',
    sealed_at = $2,
    spent_usd_at_seal = $3,
    updated_at = now()
WHERE allocation_id = $1
"""

_UPDATE_VOIDED_SQL = """
UPDATE proj_budget_allocation_summary
SET status = 'Voided',
    updated_at = now()
WHERE allocation_id = $1
"""


class AllocationSummaryProjection:
    """Maintains the `proj_budget_allocation_summary` read model."""

    name = "proj_budget_allocation_summary"
    subscribed_event_types = frozenset(
        {
            "AllocationGranted",
            "AllocationActivated",
            "AllocationCeilingUpdated",
            "AllocationSealed",
            "AllocationVoided",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "AllocationGranted":
                campaign_id_raw = event.payload.get("campaign_id")
                await conn.execute(
                    _INSERT_SQL,
                    UUID(event.payload["allocation_id"]),
                    event.payload["ceiling_usd"],
                    (UUID(campaign_id_raw) if campaign_id_raw is not None else None),
                    event.payload["note"],
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "AllocationActivated":
                await conn.execute(
                    _UPDATE_ACTIVATED_SQL,
                    UUID(event.payload["allocation_id"]),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "AllocationCeilingUpdated":
                await conn.execute(
                    _UPDATE_CEILING_SQL,
                    UUID(event.payload["allocation_id"]),
                    event.payload["ceiling_usd"],
                )
            case "AllocationSealed":
                await conn.execute(
                    _UPDATE_SEALED_SQL,
                    UUID(event.payload["allocation_id"]),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                    event.payload["spent_usd"],
                )
            case "AllocationVoided":
                await conn.execute(
                    _UPDATE_VOIDED_SQL,
                    UUID(event.payload["allocation_id"]),
                )
            case _:
                pass


__all__ = ["AllocationSummaryProjection"]
