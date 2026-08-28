"""Test / `app_env=test` adapter for `RunObservationTrail`.

Wraps the SAME `InMemoryObservationStore` instance `append_observations`
writes through (see `wire.py`), rather than keeping its own seeded dict:
that is what lets a contract test call `POST /runs/{id}/observations` and
then read the result back through `get_run_history` without a real
Postgres. `Observation` (the write model) carries no `recorded_at` -- that
column is Postgres-assigned (`DEFAULT now()`) -- so this adapter sets
`recorded_at = occurred_at`. That is a test-only stand-in, never a record
of truth: the in-memory store has no write clock to ask.
"""

from uuid import UUID

from cora.run.aggregates.run.entries import InMemoryObservationStore
from cora.run.ports.run_observation_trail import RunObservationRow


class InMemoryRunObservationTrail:
    """Test `RunObservationTrail`, backed by an `InMemoryObservationStore`."""

    def __init__(self, store: InMemoryObservationStore) -> None:
        self._store = store

    async def read_run_observations(self, *, run_id: UUID, limit: int) -> list[RunObservationRow]:
        rows = [row for row in self._store.all() if row.run_id == run_id]
        rows.sort(key=lambda row: (row.occurred_at, row.event_id))
        return [
            RunObservationRow(
                event_id=row.event_id,
                channel_name=row.channel_name,
                value=row.value,
                categorical_value=row.categorical_value,
                units=row.units,
                sampling_procedure=row.sampling_procedure,
                sampled_at=row.sampled_at,
                occurred_at=row.occurred_at,
                recorded_at=row.occurred_at,
                is_simulated=row.is_simulated,
            )
            for row in rows[:limit]
        ]
