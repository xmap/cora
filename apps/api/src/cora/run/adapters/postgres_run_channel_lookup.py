"""asyncpg-backed `RunChannelLookup` over `entries_run_observations`.

Queries the existing observation table directly: the "range query when a
real consumer asks" the entries module reserved, with the closed-loop
rules as that consumer. No projection (a projection would cost a
permanent fold and read staler than the source on the very freshness
signal Rule R depends on).

Both queries key on `recorded_at` (the CORA write-time trust anchor) and
are channel-scoped, so they ride the
`entries_run_observations_run_channel_recorded_idx`
`(run_id, channel_name, recorded_at DESC)` btree added alongside this
adapter. The pre-existing `sampled_at` indexes do NOT serve these
queries (wrong column, no channel_name).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress at module level for the adapter.

from datetime import datetime
from uuid import UUID

import asyncpg

from cora.run.ports.run_channel_lookup import (
    RunChannelLatest,
    RunChannelSignal,
    RunFeedHealth,
)

_LATEST_SQL = """
SELECT channel_name, value, units, sampled_at, recorded_at, is_simulated
FROM entries_run_observations
WHERE run_id = $1 AND channel_name = $2
ORDER BY recorded_at DESC
LIMIT 1
"""

_WINDOW_SQL = """
SELECT
    count(*)                       AS count_since,
    min(recorded_at)               AS first_recorded_at,
    max(recorded_at)               AS latest_recorded_at,
    coalesce(bool_or(is_simulated), false) AS is_simulated_window
FROM entries_run_observations
WHERE run_id = $1 AND channel_name = $2 AND recorded_at > $3
"""

_FEED_HEALTH_SQL = """
SELECT max(recorded_at) AS latest_heartbeat_recorded_at
FROM entries_run_feed_heartbeats
WHERE run_id = $1
"""


class PostgresRunChannelLookup:
    """Production `RunChannelLookup`; reads the observation entry table."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def read_run_channel_latest(
        self, *, run_id: UUID, channel_name: str
    ) -> RunChannelLatest | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_LATEST_SQL, run_id, channel_name)
        if row is None:
            return None
        return RunChannelLatest(
            channel_name=row["channel_name"],
            value=row["value"],
            units=row["units"],
            sampled_at=row["sampled_at"],
            recorded_at=row["recorded_at"],
            is_simulated=row["is_simulated"],
        )

    async def read_run_channel_window(
        self, *, run_id: UUID, channel_name: str, since: datetime
    ) -> RunChannelSignal:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_WINDOW_SQL, run_id, channel_name, since)
        # count(*) always returns exactly one row, even for an empty window.
        assert row is not None
        return RunChannelSignal(
            channel_name=channel_name,
            count_since=row["count_since"],
            first_recorded_at=row["first_recorded_at"],
            latest_recorded_at=row["latest_recorded_at"],
            is_simulated_window=row["is_simulated_window"],
        )

    async def read_feed_health(self, *, run_id: UUID) -> RunFeedHealth:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_FEED_HEALTH_SQL, run_id)
        # max() over an empty set returns one row with a NULL aggregate.
        latest = row["latest_heartbeat_recorded_at"] if row is not None else None
        return RunFeedHealth(latest_heartbeat_recorded_at=latest)
