"""Cross-aggregate context the `seal_edition` decider validates against.

`SealEditionContext` is built by the seal handler from:

  - `load_dataset` calls per member `dataset_id` (proof of existence
    + intent + Discarded status check)
  - `DistributionLookup.lookup_canonical_by_dataset` per Dataset for
    the serializer's `DatasetRef` boundary; the context carries the
    set of `dataset_ids` that resolved to a canonical Distribution
    (the decider checks for the dataset_id set complement to surface
    the `EditionDatasetDistributionNotFoundError`)
  - `FacilityLookup.lookup_by_code` for the publisher binding
  - `EditionSerializer.serialize(..., external_pid=None)` for the
    pre-DOI `content_hash`

The handler captures `now` + `sealing_year` + `effective_publisher_code`
+ `effective_license` + `content_hash` into the context so the decider
stays pure (per non-determinism principle).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.data.aggregates.dataset import Dataset


@dataclass(frozen=True)
class SealEditionContext:
    """Snapshot of cross-aggregate references at seal-time."""

    datasets: dict[UUID, Dataset]
    dataset_ids_with_canonical_distribution: frozenset[UUID]
    publisher_facility_code: str
    publication_year: int
    license: str | None
    content_hash: str
