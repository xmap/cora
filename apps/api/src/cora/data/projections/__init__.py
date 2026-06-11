"""Data BC projections.

Five projection writers:
  - DatasetSummaryProjection: folds Dataset lifecycle events into
    proj_data_dataset_summary.
  - AcquisitionSummaryProjection: folds AcquisitionRecorded into
    proj_data_acquisition_summary.
  - DistributionSummaryProjection: folds DistributionRegistered into
    proj_data_distribution_summary, and AttestationRecorded into the
    same row's status column (Match -> Verified; Mismatch -> Stale).
  - EditionSummaryProjection: folds Edition 6-event lifecycle into
    proj_data_edition_summary.
  - AttestationSummaryProjection: folds AttestationRecorded into
    proj_data_attestation_summary.
"""

from cora.data.projections.acquisition_summary import AcquisitionSummaryProjection
from cora.data.projections.attestation_summary import AttestationSummaryProjection
from cora.data.projections.distribution_summary import DistributionSummaryProjection
from cora.data.projections.edition_summary import EditionSummaryProjection
from cora.data.projections.summary import DatasetSummaryProjection

__all__ = [
    "AcquisitionSummaryProjection",
    "AttestationSummaryProjection",
    "DatasetSummaryProjection",
    "DistributionSummaryProjection",
    "EditionSummaryProjection",
]
