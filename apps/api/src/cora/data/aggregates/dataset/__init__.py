"""Dataset aggregate: state, status enum, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.data.features.<verb>_dataset/` and import from here for state
and event types. Two slice-local cross-aggregate context VOs:
  - `DatasetRegistrationContext` at
    `cora.data.features.register_dataset.context` — Run + Subject +
    derived_from peers loaded at registration.
  - `DatasetPromotionContext` at
    `cora.data.features.promote_dataset.context` — derived_from
    peers loaded at promotion-time for the lineage-must-be-Production
    guard.

The trust-level dimension is orthogonal to lifecycle:
`Dataset.intent` (Trial | Production) flipped via the dedicated
`promote_dataset` slice. `Dataset.producing_run_end_state` (str |
None) is captured at registration to support the Run-must-be-
Completed promotion guard. See [[project_dataset_lineage_design]].
"""

from cora.data.aggregates.dataset.events import (
    DatasetDemoted,
    DatasetDiscarded,
    DatasetEvent,
    DatasetPromoted,
    DatasetRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.data.aggregates.dataset.evolver import evolve, fold
from cora.data.aggregates.dataset.read import load_dataset
from cora.data.aggregates.dataset.state import (
    ACTUATION_KIND_HYBRID,
    ACTUATION_KIND_PHYSICAL,
    ACTUATION_KIND_SIMULATED,
    DATASET_CHECKSUM_ALGORITHM_SHA256,
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DATASET_CONFORMS_TO_ENTRY_MAX_LENGTH,
    DATASET_CONFORMS_TO_MAX_ENTRIES,
    DATASET_DERIVED_FROM_MAX_ENTRIES,
    DATASET_MEDIA_TYPE_MAX_LENGTH,
    DATASET_NAME_MAX_LENGTH,
    DATASET_URI_BLOCKED_SCHEMES,
    DATASET_URI_MAX_LENGTH,
    DATASET_USED_CALIBRATIONS_MAX_ENTRIES,
    RUN_END_STATE_COMPLETED,
    Dataset,
    DatasetAlreadyExistsError,
    DatasetAlreadyPromotedError,
    DatasetAlreadyRetractedError,
    DatasetCannotDemoteError,
    DatasetCannotDiscardError,
    DatasetCannotPromoteError,
    DatasetChecksum,
    DatasetDiscardReason,
    DatasetEncoding,
    DatasetName,
    DatasetNotFoundError,
    DatasetStatus,
    DatasetUri,
    DemotionReason,
    DerivedFromDatasetsDiscardedError,
    DerivedFromDatasetsNotFoundError,
    Intent,
    InvalidDatasetByteSizeError,
    InvalidDatasetChecksumError,
    InvalidDatasetDiscardReasonError,
    InvalidDatasetEncodingError,
    InvalidDatasetNameError,
    InvalidDatasetUriError,
    InvalidDemotionReasonError,
    InvalidDerivedFromError,
    InvalidPromotionReasonError,
    InvalidUsedCalibrationsError,
    LinkedSubjectNotFoundError,
    ProducingRunNotFoundError,
    PromotionReason,
    validate_byte_size,
    validate_derived_from,
    validate_used_calibration_ids,
)

__all__ = [
    "ACTUATION_KIND_HYBRID",
    "ACTUATION_KIND_PHYSICAL",
    "ACTUATION_KIND_SIMULATED",
    "DATASET_CHECKSUM_ALGORITHM_SHA256",
    "DATASET_CHECKSUM_SHA256_HEX_LENGTH",
    "DATASET_CONFORMS_TO_ENTRY_MAX_LENGTH",
    "DATASET_CONFORMS_TO_MAX_ENTRIES",
    "DATASET_DERIVED_FROM_MAX_ENTRIES",
    "DATASET_MEDIA_TYPE_MAX_LENGTH",
    "DATASET_NAME_MAX_LENGTH",
    "DATASET_URI_BLOCKED_SCHEMES",
    "DATASET_URI_MAX_LENGTH",
    "DATASET_USED_CALIBRATIONS_MAX_ENTRIES",
    "RUN_END_STATE_COMPLETED",
    "Dataset",
    "DatasetAlreadyExistsError",
    "DatasetAlreadyPromotedError",
    "DatasetAlreadyRetractedError",
    "DatasetCannotDemoteError",
    "DatasetCannotDiscardError",
    "DatasetCannotPromoteError",
    "DatasetChecksum",
    "DatasetDemoted",
    "DatasetDiscardReason",
    "DatasetDiscarded",
    "DatasetEncoding",
    "DatasetEvent",
    "DatasetName",
    "DatasetNotFoundError",
    "DatasetPromoted",
    "DatasetRegistered",
    "DatasetStatus",
    "DatasetUri",
    "DemotionReason",
    "DerivedFromDatasetsDiscardedError",
    "DerivedFromDatasetsNotFoundError",
    "Intent",
    "InvalidDatasetByteSizeError",
    "InvalidDatasetChecksumError",
    "InvalidDatasetDiscardReasonError",
    "InvalidDatasetEncodingError",
    "InvalidDatasetNameError",
    "InvalidDatasetUriError",
    "InvalidDemotionReasonError",
    "InvalidDerivedFromError",
    "InvalidPromotionReasonError",
    "InvalidUsedCalibrationsError",
    "LinkedSubjectNotFoundError",
    "ProducingRunNotFoundError",
    "PromotionReason",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_dataset",
    "to_payload",
    "validate_byte_size",
    "validate_derived_from",
    "validate_used_calibration_ids",
]
