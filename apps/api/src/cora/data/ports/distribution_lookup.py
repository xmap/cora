"""DistributionLookup port: same-BC query for canonical Distribution by Dataset.

Used by `seal_edition` to resolve the authoritative `DistributionUri`
/ `DatasetChecksum` / `byte_size` / `DatasetEncoding` for each member
Dataset before invoking the `EditionSerializer`.

## Canonical pick policy

`lookup_canonical_by_dataset(dataset_id)` returns the lowest-id
non-Discarded `Distribution` row for the given Dataset. The pick is
deterministic across re-queries; matches the canonical-pick rule in
the Edition design memo L8.

## Convention

Same-BC port (Data BC owns both Edition and Distribution); the
production adapter (`PostgresDistributionLookup`) queries
`proj_data_distribution_summary` by `dataset_id ORDER BY
distribution_id LIMIT 1 WHERE status != 'Discarded'`. Tests use
`InMemoryDistributionLookup` seeded directly.

Lives in `cora.data.ports` rather than `cora.infrastructure.ports`
because it queries a Data-owned projection table; the port surface
is BC-internal even though its implementation reaches Postgres.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.data.aggregates.dataset.state import (
    DatasetChecksum,
    DatasetEncoding,
)
from cora.data.aggregates.distribution.state import (
    DistributionStatus,
    DistributionUri,
)


@dataclass(frozen=True)
class CanonicalDistributionLookupResult:
    """Result row from `DistributionLookup.lookup_canonical_by_dataset`.

    Carries only the fields the `EditionSerializer` boundary needs.
    """

    distribution_id: UUID
    dataset_id: UUID
    uri: DistributionUri
    checksum: DatasetChecksum
    byte_size: int
    encoding: DatasetEncoding
    status: DistributionStatus


class DistributionLookup(Protocol):
    """Same-BC port: query Distribution projection by Dataset id."""

    async def lookup_canonical_by_dataset(
        self,
        dataset_id: UUID,
    ) -> CanonicalDistributionLookupResult | None:
        """Return the canonical Distribution for `dataset_id` or None.

        Canonical pick: lowest `distribution_id` among
        non-Discarded rows. Returns None when zero non-Discarded
        Distributions exist for the Dataset.
        """
        ...


__all__ = [
    "CanonicalDistributionLookupResult",
    "DistributionLookup",
]
