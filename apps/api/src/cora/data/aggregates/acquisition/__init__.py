"""Acquisition aggregate: state, status enum, errors, events, evolver, read repo.

The Acquisition is a slim recorded-fact-chain in the Data BC: the
birth-certificate fact that a producing Asset captured bytes into a
Dataset under an optional Run context. Terminal at genesis, one
stream per Acquisition, exactly one `AcquisitionRecorded` event ever.

Vertical slices that operate on this aggregate live under
`cora.data.features.<verb>_acquisition/` and import from here for
state and event types. The `record_acquisition` slice carries a
slice-local cross-aggregate context VO at
`cora.data.features.record_acquisition.context` (Dataset + Asset
lookup + optional Run loaded at record time).
"""

from cora.data.aggregates.acquisition.events import (
    AcquisitionEvent,
    AcquisitionRecorded,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.data.aggregates.acquisition.evolver import evolve, fold
from cora.data.aggregates.acquisition.read import load_acquisition
from cora.data.aggregates.acquisition.state import (
    Acquisition,
    AcquisitionAlreadyExistsError,
    AcquisitionAssetNotFoundError,
    AcquisitionCannotRecordWithoutCapturingError,
    AcquisitionRunNotFoundError,
    AcquisitionStatus,
    InvalidAcquisitionCapturedAtError,
    InvalidAcquisitionEvidenceError,
    InvalidAcquisitionSettingsError,
    validate_evidence,
    validate_settings,
)

__all__ = [
    "Acquisition",
    "AcquisitionAlreadyExistsError",
    "AcquisitionAssetNotFoundError",
    "AcquisitionCannotRecordWithoutCapturingError",
    "AcquisitionEvent",
    "AcquisitionRecorded",
    "AcquisitionRunNotFoundError",
    "AcquisitionStatus",
    "InvalidAcquisitionCapturedAtError",
    "InvalidAcquisitionEvidenceError",
    "InvalidAcquisitionSettingsError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_acquisition",
    "to_payload",
    "validate_evidence",
    "validate_settings",
]
