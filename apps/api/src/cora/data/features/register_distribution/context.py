"""Cross-aggregate context the `register_distribution` decider validates against.

`DistributionRegistrationContext` is built by the
`register_distribution` handler from `load_dataset` (same-BC) and
`SupplyLookup.lookup` (cross-BC) calls before reaching the pure
decider. Per [[project-data-distribution-design]] L15 + L17 the
handler pre-loads both refs; the decider treats them as injected
proof-of-existence + carries the loaded peers in so the Discarded
+ kind guards are O(1) closures over already-fetched data.

Slice-local module by design: only `register_distribution` uses it
today. Mirrors the `DatasetRegistrationContext` precedent.

## Field semantics

  - `dataset`: the parent Dataset (always required). The handler
    raises `DatasetNotFoundError` upstream if `command.dataset_id`
    does not resolve, so the decider can assume this field is
    non-None. Used by the decider for the Discarded guard (L17
    step 6) and the byte-identical-copy checksum + byte_size
    equality guards (L17 steps 9, 10).
  - `supply`: the resolved Supply reference from the SupplyLookup
    port (always required). The handler raises
    `DistributionSupplyNotFoundError` upstream if the lookup
    returns None, so the decider can assume this field is
    non-None. Used by the decider for the storage-kind guard
    (L17 step 8).
"""

from dataclasses import dataclass

from cora.data.aggregates.dataset import Dataset
from cora.infrastructure.ports.supply_lookup import SupplyLookupResult


@dataclass(frozen=True)
class DistributionRegistrationContext:
    """Snapshot of cross-aggregate references at Distribution-registration time.

    Both fields are required; the handler populates each before
    constructing the context. The decider treats both as proof of
    existence + as carriers of the data it needs for the byte-
    identical-copy and storage-kind guards.
    """

    dataset: Dataset
    supply: SupplyLookupResult
