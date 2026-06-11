"""Cross-aggregate context the `record_acquisition` decider validates against.

`AcquisitionRecordingContext` is built by the `record_acquisition`
handler from a Dataset pre-load, an `AssetLookup.lookup`, and an
optional Run pre-load (only when `producing_run_id` is set), before
reaching the pure decider. Validation is existence-only for the
Dataset and Run (no status / lifecycle check per the design lock);
the Asset additionally must declare the Capturing affordance (the
sole write-time cross-BC business invariant).

Slice-local module by design: only `record_acquisition` uses it
today. Mirrors the `DatasetRegistrationContext` precedent.

## Field semantics

  - `dataset`: the Dataset this Acquisition produced. ALWAYS present
    (the handler raises DatasetNotFoundError before building the
    context if the Dataset stream is empty).
  - `asset`: the producing Asset summary (carries `family_affordances`
    for the Capturing gate). ALWAYS present (the handler raises
    AcquisitionAssetNotFoundError if the lookup returns None).
  - `run`: the Run context. None when the command's `producing_run_id`
    is None (calibration / dark-field / standalone capture). When the
    command's `producing_run_id` is set, the handler either populates
    this or raises AcquisitionRunNotFoundError first.

The decider treats `dataset` and `run` as opaque proof-of-existence
(it never inspects their state); it inspects only `asset.family_affordances`
for the Capturing gate.
"""

from dataclasses import dataclass

from cora.data.aggregates.dataset import Dataset
from cora.infrastructure.ports.asset_lookup import AssetLookupResult
from cora.run.aggregates.run import Run


@dataclass(frozen=True)
class AcquisitionRecordingContext:
    """Snapshot of cross-aggregate references at Acquisition-record time."""

    dataset: Dataset
    asset: AssetLookupResult
    run: Run | None = None
