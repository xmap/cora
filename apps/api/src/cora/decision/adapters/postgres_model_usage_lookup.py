"""Postgres adapter implementing `ModelUsageLookup` over `entries_decision_inferences`.

Consumed by the Agent BC's `list_at_risk_results` read slice via the
`Kernel.model_usage_lookup` port. Enumerates the Decisions whose
recorded LLM calls touched one model identity, one row per Decision
(the newest touching call), newest Decision first.

## Match semantics (see the port docstring for the WHY)

A row matches when `provider_name = $1` AND (`request_model = $2` OR
`response_model = $2` OR `response_model LIKE $2 || '-%'`). The LIKE
arm catches alias calls the provider answered with a dated snapshot
(`claude-sonnet-4-5` -> `claude-sonnet-4-5-20250929`); those results
are equally at risk when the alias retires.

## Why query the entries table (not a projection)

The slice is an operator-rare read (a vendor retirement is a
once-a-quarter event, not a hot path), and the facts it needs already
sit on the inference rows the Decision BC owns. No existing index
leads with `provider_name` or the model columns, so this is a
sequential scan of the append-only entries table; at pilot scale
(single-digit LLM calls per run) that is well inside p95, the same
posture as `PostgresSpendLookup`. The escalation ladder if the read
ever shows up in latency dashboards: first a
`(provider_name, request_model)` index, then a dedicated
at-risk-results read model fed by the retirement announcement.
Neither before the trigger fires.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncpg

from cora.infrastructure.ports.model_usage_lookup import ModelTouchedDecision

# DISTINCT ON keeps the newest row per Decision (inner ORDER BY pairs
# decision_id with occurred_at DESC as DISTINCT ON requires); the outer
# ORDER BY then presents affected Decisions newest-call-first.
_FIND_TOUCHING_DECISIONS_SQL = """
SELECT decision_id, occurred_at, request_model, response_model, agent_id
FROM (
    SELECT DISTINCT ON (decision_id)
        decision_id,
        occurred_at,
        request_model,
        response_model,
        agent_id
    FROM entries_decision_inferences
    WHERE provider_name = $1
      AND (
        request_model = $2
        OR response_model = $2
        OR response_model LIKE $2 || '-%'
      )
    ORDER BY decision_id, occurred_at DESC
) newest_per_decision
ORDER BY occurred_at DESC
"""


class PostgresModelUsageLookup:
    """asyncpg-backed `ModelUsageLookup` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_decisions_touching_model(
        self,
        *,
        provider: str,
        model: str,
    ) -> tuple[ModelTouchedDecision, ...]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_FIND_TOUCHING_DECISIONS_SQL, provider, model)
        return tuple(
            ModelTouchedDecision(
                decision_id=row["decision_id"],
                occurred_at=row["occurred_at"],
                request_model=row["request_model"],
                response_model=row["response_model"],
                agent_id=row["agent_id"],
            )
            for row in rows
        )


__all__ = ["PostgresModelUsageLookup"]
