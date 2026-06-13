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
events (the Attestation projection-writer extension), NOT via Distribution-stream events.
The Verified/Stale lifecycle is therefore expressed as ``DistributionStatus``
StrEnum values that ship day-one but are reachable only via projection
denormalization today.
"""

from cora.data.aggregates.distribution._backfill_errors import (
    DefaultStorageSupplyBootstrapError,
    DefaultStorageSupplyBootstrapFailure,
)
from cora.data.aggregates.distribution.events import (
    DistributionEvent,
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
    DistributionCannotRegisterOnDiscardedDatasetError,
    DistributionCannotRegisterOnNonStorageSupplyError,
    DistributionChecksumMismatchError,
    DistributionStatus,
    DistributionSupplyNotFoundError,
    DistributionUri,
    InvalidAccessProtocolError,
    InvalidDistributionByteSizeError,
    InvalidDistributionChecksumError,
    InvalidDistributionEncodingError,
    InvalidDistributionUriError,
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
    "DistributionCannotRegisterOnDiscardedDatasetError",
    "DistributionCannotRegisterOnNonStorageSupplyError",
    "DistributionChecksumMismatchError",
    "DistributionEvent",
    "DistributionRegistered",
    "DistributionStatus",
    "DistributionSupplyNotFoundError",
    "DistributionUri",
    "InvalidAccessProtocolError",
    "InvalidDistributionByteSizeError",
    "InvalidDistributionChecksumError",
    "InvalidDistributionEncodingError",
    "InvalidDistributionUriError",
    "UnmappedDistributionUriSchemeError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_distribution",
    "to_payload",
    "validate_distribution_byte_size",
]
