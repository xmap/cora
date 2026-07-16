"""LanguageModelSummaryProjection: folds the catalog entry's lifecycle
into the `proj_agent_language_model_summary` read model.

The catalog's one query shape is by model identity, not by id: the
define_agent gate asks "is (provider, model) Approved, and at what
tiers?" (the shipped fleet's defaults are pinned against the seeds by
a unit consistency test, not by any startup check), so the projection
carries the identity columns the `LanguageModelLookup` adapter filters
on, plus the two tier axes and the lifecycle columns the
at-risk-results surface reads. Follows the Path C convention (state
stays decider-minimal; lifecycle timestamps live on the projection);
the same state-always-holds-latest posture as
`AgentSummaryProjection`.

`cost_basis` is intentionally NOT projected: the pricing bridge reads
the aggregate (few entries, config-shaped), and duplicating rates into
a read model would create a second pricing home to drift.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_SQL = """
INSERT INTO proj_agent_language_model_summary
    (language_model_id, name, provider, model, snapshot_pin, served_via,
     data_tier, archivability, status, created_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'Defined', $9)
ON CONFLICT (language_model_id) DO NOTHING
"""

_UPDATE_APPROVED_SQL = """
UPDATE proj_agent_language_model_summary
SET status = 'Approved',
    approved_at = $2,
    updated_at = now()
WHERE language_model_id = $1
"""

_UPDATE_RETIREMENT_ANNOUNCED_SQL = """
UPDATE proj_agent_language_model_summary
SET status = 'RetirementAnnounced',
    retirement_announced_at = $2,
    retirement_effective_at = $3,
    updated_at = now()
WHERE language_model_id = $1
"""

_UPDATE_RETIRED_SQL = """
UPDATE proj_agent_language_model_summary
SET status = 'Retired',
    retired_at = $2,
    updated_at = now()
WHERE language_model_id = $1
"""

_UPDATE_DEPRECATED_SQL = """
UPDATE proj_agent_language_model_summary
SET status = 'Deprecated',
    deprecated_at = $2,
    updated_at = now()
WHERE language_model_id = $1
"""


class LanguageModelSummaryProjection:
    """Maintains the `proj_agent_language_model_summary` read model."""

    name = "proj_agent_language_model_summary"
    subscribed_event_types = frozenset(
        {
            "LanguageModelDefined",
            "LanguageModelApproved",
            "LanguageModelRetirementAnnounced",
            "LanguageModelRetired",
            "LanguageModelDeprecated",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "LanguageModelDefined":
                await conn.execute(
                    _INSERT_SQL,
                    UUID(event.payload["language_model_id"]),
                    event.payload["name"],
                    event.payload["provider"],
                    event.payload["model"],
                    event.payload.get("snapshot_pin"),
                    event.payload["served_via"],
                    event.payload["data_tier"],
                    event.payload["archivability"],
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "LanguageModelApproved":
                await conn.execute(
                    _UPDATE_APPROVED_SQL,
                    UUID(event.payload["language_model_id"]),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "LanguageModelRetirementAnnounced":
                effective_raw = event.payload.get("effective_at")
                await conn.execute(
                    _UPDATE_RETIREMENT_ANNOUNCED_SQL,
                    UUID(event.payload["language_model_id"]),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                    (datetime.fromisoformat(effective_raw) if effective_raw is not None else None),
                )
            case "LanguageModelRetired":
                await conn.execute(
                    _UPDATE_RETIRED_SQL,
                    UUID(event.payload["language_model_id"]),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "LanguageModelDeprecated":
                await conn.execute(
                    _UPDATE_DEPRECATED_SQL,
                    UUID(event.payload["language_model_id"]),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case _:
                pass


__all__ = ["LanguageModelSummaryProjection"]
