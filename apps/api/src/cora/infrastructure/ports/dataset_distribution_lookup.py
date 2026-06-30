"""DatasetDistributionLookup port: cross-BC query for a Dataset's Distributions.

Used by the Run BC start_run gate (leg C of stage-then-reconstruct) to check
that a reconstruction's input Dataset has a Verified Distribution before the Run
may start ([[project_run_input_dependency_design]]). Cross-BC mirror of
`SupplyLookup` / `ClearanceLookup`: one implementor (Data BC ships the Postgres
adapter reading `proj_data_distribution_summary`), multiple consumers (the Run
start gate first). It lives in `cora.infrastructure.ports` because Run may not
import the Data-internal `cora.data.ports.DistributionLookup` (that one is the
Edition-shaped lowest-id canonical pick, a different need).

## Decider-gates, not port-gates

Returns EVERY non-Discarded Distribution for the Dataset regardless of status,
so the start_run decider can both gate on Verified AND produce a useful
diagnostic ("the input has a Distribution but it is Stale" vs "no Distribution
at all"). This is the `SupplyLookup` posture: the port returns rows, the decider
partitions on `status`. It deliberately does NOT reuse the canonical-pick query,
whose lowest-id row may be Stale while a higher-id Distribution is Verified.

`status` is the `DistributionStatus` value as a plain string (matches the
projection's TEXT column); `supply_id` is carried for the deferred reachability
check (which Storage Supply / tier the copy rests on); `distribution_id` is
carried for diagnostics and the eventual lineage record.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class DatasetDistributionLookupResult:
    """A non-Discarded Distribution of a Dataset, for the Run-start input gate."""

    distribution_id: UUID
    dataset_id: UUID
    supply_id: UUID
    status: str


class DatasetDistributionLookup(Protocol):
    """Cross-BC port: query Datasets' non-Discarded Distributions from the Run BC."""

    async def find_by_datasets(
        self, dataset_ids: frozenset[UUID]
    ) -> Mapping[UUID, tuple[DatasetDistributionLookupResult, ...]]:
        """Return every non-Discarded Distribution per requested Dataset id.

        The returned mapping is keyed by Dataset id and contains ONLY the
        ids for which at least one non-Discarded Distribution exists. Ids
        with no non-Discarded Distribution are absent from the mapping;
        consumers use `.get(dataset_id, ())` and treat absence as the
        no-Distribution-at-all gate path. The port does not filter on
        status so the decider can distinguish Stale from absent (it gates
        on `status == "Verified"`).

        Empty input (`dataset_ids = frozenset()`) returns an empty mapping;
        the handler short-circuits before calling the port for Runs that
        declare no input Datasets.
        """
        ...


class NoDatasetDistributionsLookup:
    """Test stub: every Dataset has no Distribution (the not-present gate path).

    The conservative default for tests that do not seed the input gate: the
    start_run decider sees an input with no Verified Distribution and raises.
    """

    async def find_by_datasets(
        self, dataset_ids: frozenset[UUID]
    ) -> Mapping[UUID, tuple[DatasetDistributionLookupResult, ...]]:
        _ = dataset_ids
        return {}


class SeededDatasetDistributionLookup:
    """Test stub: returns the Distributions configured per Dataset id.

    Construct with a mapping `{dataset_id: (result, ...)}`; an unmapped Dataset
    is absent from the returned mapping. Lets a gate test seed a Verified row, a
    Stale-only row, or no row to exercise each decider branch.
    """

    def __init__(self, by_dataset: dict[UUID, tuple[DatasetDistributionLookupResult, ...]]) -> None:
        self._by_dataset = dict(by_dataset)

    async def find_by_datasets(
        self, dataset_ids: frozenset[UUID]
    ) -> Mapping[UUID, tuple[DatasetDistributionLookupResult, ...]]:
        return {
            dataset_id: self._by_dataset[dataset_id]
            for dataset_id in dataset_ids
            if dataset_id in self._by_dataset
        }


__all__ = [
    "DatasetDistributionLookup",
    "DatasetDistributionLookupResult",
    "NoDatasetDistributionsLookup",
    "SeededDatasetDistributionLookup",
]
