"""asyncpg `ProcedureActivityLookup` over entries_operation_procedure_activities.

Queries the activity entry table directly for the newest `recorded_at` of
one procedure: the read the ProcedureWatcher anti-false-flag fold needs
and the write-only `ActivityStore` does not provide. No projection (a
projection would cost a permanent fold to serve a rare per-tick point
read; the watcher only folds for a Running candidate already past its
status-timestamp window).

Keys on `recorded_at` (the CORA write-time trust anchor, not the
spoofable `sampled_at`) and rides the
`entries_operation_procedure_activities_proc_recorded_idx`
`(procedure_id, recorded_at DESC)` btree added alongside this adapter.
The pre-existing indexes are keyed on `sampled_at` (plus a BRIN on
recorded_at), so none serves a procedure-scoped max(recorded_at) without
scanning the procedure's full activity history.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress at module level for the adapter.

from uuid import UUID

import asyncpg

from cora.operation.ports.procedure_activity_lookup import ProcedureActivityRecency

_RECENCY_SQL = """
SELECT max(recorded_at) AS latest_recorded_at
FROM entries_operation_procedure_activities
WHERE procedure_id = $1
"""


class PostgresProcedureActivityLookup:
    """Production `ProcedureActivityLookup`; reads the activity entry table."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def read_procedure_activity_recency(
        self, *, procedure_id: UUID
    ) -> ProcedureActivityRecency:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_RECENCY_SQL, procedure_id)
        # max() over an empty set returns one row with a NULL aggregate.
        latest = row["latest_recorded_at"] if row is not None else None
        return ProcedureActivityRecency(latest_recorded_at=latest)
