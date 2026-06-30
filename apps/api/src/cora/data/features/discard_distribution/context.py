"""Cross-aggregate context the `discard_distribution` decider validates against.

`DiscardDistributionContext` is built by the `discard_distribution`
handler from `load_dataset` (the parent Dataset, same-BC) and
`DatasetDistributionLookup.find_by_datasets` (the sibling copies, read
from the projection-backed lookup) before reaching the pure decider.
The decider treats both as injected proof-of-fact and reads the
sibling-Verified redundancy signal off them, so the guards are O(1)
closures over already-fetched data.

Slice-local module by design: only `discard_distribution` uses it
today. Mirrors the `DistributionRegistrationContext` precedent.

## Field semantics

  - `dataset`: the parent Dataset of the target Distribution (always
    required). The handler raises `DatasetNotFoundError` upstream if
    `distribution.dataset_id` does not resolve, so the decider can
    assume this field is non-None. Used by the decider for the
    parent-Discarded guard.
  - `sibling_distributions`: every non-Discarded Distribution of the
    target's parent Dataset (the `find_by_datasets` result for the
    distribution's `dataset_id`), INCLUDING the target itself. The
    decider filters out the target by id and reads the Verified-on-a-
    different-tier redundancy signal off the rest. The set is
    projection-derived (eventual): the same input-gate stance start_run
    uses for its Verified-Distribution check.
"""

from dataclasses import dataclass

from cora.data.aggregates.dataset import Dataset
from cora.infrastructure.ports.dataset_distribution_lookup import (
    DatasetDistributionLookupResult,
)


@dataclass(frozen=True)
class DiscardDistributionContext:
    """Snapshot of cross-aggregate facts at Distribution-discard time.

    Both fields are required; the handler populates each before
    constructing the context. The decider treats the Dataset as proof
    of the parent's status and the sibling set as the
    projection-derived redundancy signal.
    """

    dataset: Dataset
    sibling_distributions: tuple[DatasetDistributionLookupResult, ...]
