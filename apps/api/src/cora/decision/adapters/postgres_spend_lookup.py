"""Postgres adapter implementing `SpendLookup` over `entries_decision_inferences`.

Consumed by the budget gate at the LLM producers' seams via the
`Kernel.spend_lookup` port. Sums the durable spend facts the inference
entries already carry (`cost_usd`, token counts) for one agent inside
one half-open window.

## Why query the entries table (not a projection)

The gate reads one aggregate per call: SUM + COUNT over rows matching
`agent_id` + an `occurred_at` range. No existing index leads with
`agent_id` (the table indexes decision_id/logbook_id/conversation_id
plus a BRIN on recorded_at), so this is a sequential scan of the
append-only entries table; at pilot scale (single-digit LLM calls per
run) that is well inside p95. The escalation ladder when the gate's
read shows up in latency dashboards: first an `(agent_id, occurred_at)`
index, then a dedicated `proj_agent_spend` read model. Neither before
the trigger fires.

## NULL and type notes

`cost_usd` is nullable (pre-migration rows) and `COALESCE`d to $0, so
history never inflates a balance. `agent_id` is a TEXT column (OTel
`gen_ai.agent.id` is a string); the adapter stringifies the UUID the
consumer passes. `tokens_spent` counts input + output tokens (cache
tokens are not persisted on the entry; see the port docstring for why
the resulting undercount is the accepted failure direction).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

import asyncpg

from cora.infrastructure.ports.spend_lookup import SpendLookupResult

_SUM_AGENT_SPEND_SQL = """
SELECT
    COALESCE(SUM(cost_usd), 0)::float8 AS usd_spent,
    COALESCE(SUM(COALESCE(input_tokens, 0)::numeric + COALESCE(output_tokens, 0)::numeric), 0)
        AS tokens_spent,
    COUNT(*)::bigint AS call_count
FROM entries_decision_inferences
WHERE agent_id = $1
  AND occurred_at >= $2
  AND occurred_at < $3
"""

# Token sums accumulate in NUMERIC (arbitrary precision) so one
# adversarially large row can never raise bigint-out-of-range and wedge
# the subscriber's retry loop; the Python side clamps the Decimal back
# into int range, which still exceeds any cap by construction.
_TOKENS_CLAMP = 2**63 - 1


class PostgresSpendLookup:
    """asyncpg-backed `SpendLookup` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_agent_spend(
        self,
        *,
        agent_id: UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> SpendLookupResult:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                _SUM_AGENT_SPEND_SQL,
                str(agent_id),
                window_start,
                window_end,
            )
        assert row is not None  # aggregate queries always return one row
        return SpendLookupResult(
            agent_id=agent_id,
            window_start=window_start,
            window_end=window_end,
            usd_spent=float(row["usd_spent"]),
            tokens_spent=min(int(row["tokens_spent"]), _TOKENS_CLAMP),
            call_count=int(row["call_count"]),
        )


__all__ = ["PostgresSpendLookup"]
