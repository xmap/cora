"""Postgres-backed `DatasetDistributionLookup` adapter for production wiring.

Implements the cross-BC `cora.infrastructure.ports.DatasetDistributionLookup`
port consumed by the Run BC's `start_run` input-data genesis gate. Queries
`proj_data_distribution_summary` for every non-Discarded Distribution of the
requested Datasets (any status) so the decider can both gate on Verified AND
diagnose a Stale-only input distinct from a no-Distribution input. One grouped
query covers every declared input id (no N+1), mirroring
`PostgresSupplyLookup.find_supplies_by_kind`.

Distinct from the same-BC `PostgresDistributionLookup` (the Edition-shaped
lowest-id canonical pick): this adapter returns the FULL non-Discarded set,
not a single canonical row. Lives in `cora.data.adapters` because it reads a
Data-owned projection; it implements the infrastructure port so the Run BC
consumes it without importing anything Data-internal.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections.abc import Mapping
from uuid import UUID

import asyncpg

from cora.infrastructure.ports.dataset_distribution_lookup import (
    DatasetDistributionLookupResult,
)

_LOOKUP_SQL = """
SELECT distribution_id, dataset_id, supply_id, status
FROM proj_data_distribution_summary
WHERE dataset_id = ANY($1)
  AND status != 'Discarded'
ORDER BY dataset_id, distribution_id
"""


class PostgresDatasetDistributionLookup:
    """Reads `proj_data_distribution_summary` for Datasets' non-Discarded rows."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_by_datasets(
        self, dataset_ids: frozenset[UUID]
    ) -> Mapping[UUID, tuple[DatasetDistributionLookupResult, ...]]:
        if not dataset_ids:
            return {}
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_LOOKUP_SQL, sorted(dataset_ids, key=str))
        grouped: dict[UUID, list[DatasetDistributionLookupResult]] = {}
        for row in rows:
            grouped.setdefault(row["dataset_id"], []).append(
                DatasetDistributionLookupResult(
                    distribution_id=row["distribution_id"],
                    dataset_id=row["dataset_id"],
                    supply_id=row["supply_id"],
                    status=row["status"],
                )
            )
        return {dataset_id: tuple(results) for dataset_id, results in grouped.items()}


__all__ = ["PostgresDatasetDistributionLookup"]
