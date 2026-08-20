"""Distribution aggregate: state, status enum, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
``cora.data.features.<verb>_distribution/`` and import from here for
state and event types. Slice-local cross-aggregate context VO:

  - ``DistributionRegistrationContext`` at
    ``cora.data.features.register_distribution.context`` - Dataset +
    Supply peers loaded at registration.

Per [[project-data-distribution-design]] L7 + territory L7:
``Distribution.status`` flips to ``Verified`` / ``Stale`` via the
Distribution projection writer subscribing to ``AttestationRecorded``
events (the Attestation projection-writer extension); this stays
projection-only, with no Distribution-stream event, for BOTH the
Verified flip and the Stale-via-checksum-mismatch flip. The
mark_distribution_stale slice adds a SECOND, independent path to Stale:
a ``DistributionMarkedStale`` Distribution-stream event for facts an
operator asserts directly (a storage failure, not a checksum probe),
with no redundancy guard or parent-Dataset guard (see
``cora.data.features.mark_distribution_stale`` for the guarded
primitive). The Verified lifecycle stays reachable only via projection
denormalization today.
"""

from cora.data.aggregates.distribution._backfill_errors import (
    DefaultStorageSupplyBootstrapError,
    DefaultStorageSupplyBootstrapFailure,
)
from cora.data.aggregates.distribution.events import (
    DistributionDiscarded,
    DistributionEvent,
    DistributionMarkedStale,
    DistributionRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.data.aggregates.distribution.evolver import evolve, fold
from cora.data.aggregates.distribution.read import load_distribution
from cora.data.aggregates.distribution.state import (
    DISTRIBUTION_URI_MAX_LENGTH,
    STORAGE_SUPPLY_KIND,
    URI_SCHEME_TO_ACCESS_PROTOCOL,
    AccessProtocol,
    Distribution,
    DistributionAlreadyExistsError,
    DistributionByteSizeMismatchError,
    DistributionCannotDiscardError,
    DistributionCannotDiscardLastVerifiedError,
    DistributionCannotDiscardUnderDiscardedDatasetError,
    DistributionCannotMarkStaleError,
    DistributionCannotRegisterOnDiscardedDatasetError,
    DistributionCannotRegisterOnNonStorageSupplyError,
    DistributionChecksumAlgorithmMismatchError,
    DistributionChecksumMismatchError,
    DistributionDiscardReason,
    DistributionMarkStaleReason,
    DistributionNotFoundError,
    DistributionStatus,
    DistributionSupplyNotFoundError,
    DistributionUri,
    InvalidAccessProtocolError,
    InvalidDistributionByteSizeError,
    InvalidDistributionChecksumError,
    InvalidDistributionDiscardReasonError,
    InvalidDistributionEncodingError,
    InvalidDistributionMarkStaleReasonError,
    InvalidDistributionUriError,
    TriggerSource,
    UnmappedDistributionUriSchemeError,
    validate_distribution_byte_size,
)

__all__ = [
    "DISTRIBUTION_URI_MAX_LENGTH",
    "STORAGE_SUPPLY_KIND",
    "URI_SCHEME_TO_ACCESS_PROTOCOL",
    "AccessProtocol",
    "DefaultStorageSupplyBootstrapError",
    "DefaultStorageSupplyBootstrapFailure",
    "Distribution",
    "DistributionAlreadyExistsError",
    "DistributionByteSizeMismatchError",
    "DistributionCannotDiscardError",
    "DistributionCannotDiscardLastVerifiedError",
    "DistributionCannotDiscardUnderDiscardedDatasetError",
    "DistributionCannotMarkStaleError",
    "DistributionCannotRegisterOnDiscardedDatasetError",
    "DistributionCannotRegisterOnNonStorageSupplyError",
    "DistributionChecksumAlgorithmMismatchError",
    "DistributionChecksumMismatchError",
    "DistributionDiscardReason",
    "DistributionDiscarded",
    "DistributionEvent",
    "DistributionMarkStaleReason",
    "DistributionMarkedStale",
    "DistributionNotFoundError",
    "DistributionRegistered",
    "DistributionStatus",
    "DistributionSupplyNotFoundError",
    "DistributionUri",
    "InvalidAccessProtocolError",
    "InvalidDistributionByteSizeError",
    "InvalidDistributionChecksumError",
    "InvalidDistributionDiscardReasonError",
    "InvalidDistributionEncodingError",
    "InvalidDistributionMarkStaleReasonError",
    "InvalidDistributionUriError",
    "TriggerSource",
    "UnmappedDistributionUriSchemeError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_distribution",
    "to_payload",
    "validate_distribution_byte_size",
]
