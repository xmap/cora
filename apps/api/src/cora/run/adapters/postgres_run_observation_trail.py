"""asyncpg-backed `RunObservationTrail` over `entries_run_observations`.

Same table `PostgresRunChannelLookup` reads, different shape of query: this
one is whole-run and unbounded by channel, ordered oldest-first for a
scrubber rather than latest-only for a live decider.

The existing btree is `(run_id, channel_name, recorded_at DESC)`. A query
with no `channel_name` predicate can't ride it as an ordered scan and will
fall back to a bitmap scan plus sort; at pilot volumes (a run's own rows,
not the whole table) this is expected to be fine. Measure with `EXPLAIN`
against a real run before adding a `(run_id, recorded_at)` index -- don't
add it speculatively.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress at module level for the adapter.

from uuid import UUID

import asyncpg

from cora.run.ports.run_observation_trail import RunObservationRow

_TRAIL_SQL = """
SELECT event_id, channel_name, value, categorical_value, units,
       sampling_procedure, sampled_at, occurred_at, recorded_at, is_simulated
FROM entries_run_observations
WHERE run_id = $1
ORDER BY recorded_at, event_id
LIMIT $2
"""


class PostgresRunObservationTrail:
    """Production `RunObservationTrail`; reads the observation entry table."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def read_run_observations(self, *, run_id: UUID, limit: int) -> list[RunObservationRow]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_TRAIL_SQL, run_id, limit)
        return [
            RunObservationRow(
                event_id=row["event_id"],
                channel_name=row["channel_name"],
                value=row["value"],
                categorical_value=row["categorical_value"],
                units=row["units"],
                sampling_procedure=row["sampling_procedure"],
                sampled_at=row["sampled_at"],
                occurred_at=row["occurred_at"],
                recorded_at=row["recorded_at"],
                is_simulated=row["is_simulated"],
            )
            for row in rows
        ]
