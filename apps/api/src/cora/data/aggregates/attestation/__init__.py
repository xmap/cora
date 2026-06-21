"""Attestation aggregate: state, status enum, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
``cora.data.features.<verb>_attestation/`` and import from here for
state and event types. The slice-local cross-aggregate context VO is:

  - ``AttestationRecordingContext`` at
    ``cora.data.features.record_attestation.context`` - Dataset (always)
    plus Distribution (when ``distribution_id`` provided) peers loaded
    at recording.

Per [[project_data_attestation_design]] L7 + L20 the Attestation
aggregate writes only to its own stream; the Distribution projection
writer extension (Slice C) flips ``proj_data_distribution_summary.status``
on Match/Mismatch outcomes (projection-only flip, no Distribution
event emitted).
"""

from cora.data.aggregates.attestation.events import (
    AttestationEvent,
    AttestationRecorded,
    build_checksum_verified_evidence_payload,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.data.aggregates.attestation.evolver import evolve, fold
from cora.data.aggregates.attestation.read import load_attestation
from cora.data.aggregates.attestation.state import (
    ATTESTATION_ERROR_DETAIL_MAX_LENGTH,
    ATTESTATION_VERIFIER_KIND_MAX_LENGTH,
    Attestation,
    AttestationAlreadyExistsError,
    AttestationChecksumEvidenceMismatchError,
    AttestationDistributionDatasetMismatchError,
    AttestationDistributionNotFoundError,
    AttestationEvidence,
    AttestationKind,
    AttestationKindNotYetSupportedError,
    AttestationKindRejectsDistributionError,
    AttestationKindRequiresDistributionError,
    AttestationOutcome,
    AttestationStatus,
    AttestationTreeChecksumNotYetSupportedError,
    ChecksumVerifiedEvidence,
    InvalidAttestationEvidenceError,
    InvalidAttestationKindError,
    InvalidAttestationOutcomeError,
)

__all__ = [
    "ATTESTATION_ERROR_DETAIL_MAX_LENGTH",
    "ATTESTATION_VERIFIER_KIND_MAX_LENGTH",
    "Attestation",
    "AttestationAlreadyExistsError",
    "AttestationChecksumEvidenceMismatchError",
    "AttestationDistributionDatasetMismatchError",
    "AttestationDistributionNotFoundError",
    "AttestationEvent",
    "AttestationEvidence",
    "AttestationKind",
    "AttestationKindNotYetSupportedError",
    "AttestationKindRejectsDistributionError",
    "AttestationKindRequiresDistributionError",
    "AttestationOutcome",
    "AttestationRecorded",
    "AttestationStatus",
    "AttestationTreeChecksumNotYetSupportedError",
    "ChecksumVerifiedEvidence",
    "InvalidAttestationEvidenceError",
    "InvalidAttestationKindError",
    "InvalidAttestationOutcomeError",
    "build_checksum_verified_evidence_payload",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_attestation",
    "to_payload",
]
