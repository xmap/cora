"""`ProcedureOutcomeLookup` adapters over the outcome entry table.

Reads back every recorded steered pass of one procedure, ascending by
`iteration_index`: the resume-time read that rebuilds the brain's observation
history and that the write-only `OutcomeStore` does not provide. No projection
(the read is rare, once per resume, and a projection would cost a permanent fold
to serve it).

Each row is self-describing (`point` + `measurements`), so reconstruction is a
plain sort-then-map with no join to the iteration event; `measurements` and
`point` come back already decoded by the pool's jsonb codec (the same codec the
write side encodes through), so the rows need no `json.loads`.

Two adapters live here because both legally depend on the aggregate (the write
store + its `Outcome` rows) AND the ports layer (`RecordedOutcome`), a
combination the aggregate layer itself may not have (tach forbids
aggregates->ports): `PostgresProcedureOutcomeLookup` (production, over the pool)
and `InMemoryProcedureOutcomeLookup` (wraps an `InMemoryOutcomeStore` for the
pool-less resume, so the read sees exactly what the conduct loop wrote).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress at module level for the adapter.

from uuid import UUID

import asyncpg

from cora.operation.aggregates.procedure import InMemoryOutcomeStore
from cora.operation.ports.procedure_outcome_lookup import RecordedOutcome

_OUTCOMES_SQL = """
SELECT iteration_index, point, measurements, succeeded, actuation_kind
FROM entries_operation_procedure_outcomes
WHERE procedure_id = $1
ORDER BY iteration_index ASC
"""


class PostgresProcedureOutcomeLookup:
    """Production `ProcedureOutcomeLookup`; reads the outcome entry table."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def read_procedure_outcomes(self, *, procedure_id: UUID) -> tuple[RecordedOutcome, ...]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_OUTCOMES_SQL, procedure_id)
        return tuple(
            RecordedOutcome(
                iteration_index=row["iteration_index"],
                point=dict(row["point"]),
                measurements=list(row["measurements"]),
                succeeded=row["succeeded"],
                actuation_kind=row["actuation_kind"],
            )
            for row in rows
        )


class InMemoryProcedureOutcomeLookup:
    """`ProcedureOutcomeLookup` over an `InMemoryOutcomeStore` (pool-less resume).

    The adapters layer legally depends on BOTH the aggregate (the write store +
    its `Outcome` rows) and the ports layer (`RecordedOutcome`), so the read
    wrapper that bridges them lives here rather than on the aggregate's store
    (which must not depend on ports, per tach layering). In tests /
    `app_env=test` the SAME `InMemoryOutcomeStore` the conduct loop wrote to is
    wrapped here, so the resume read sees exactly what was recorded.
    """

    def __init__(self, store: InMemoryOutcomeStore) -> None:
        self._store = store

    async def read_procedure_outcomes(self, *, procedure_id: UUID) -> tuple[RecordedOutcome, ...]:
        return tuple(
            RecordedOutcome(
                iteration_index=row.iteration_index,
                point=row.point,
                measurements=row.measurements,
                succeeded=row.succeeded,
                actuation_kind=row.actuation_kind,
            )
            for row in self._store.for_procedure(procedure_id)
        )
