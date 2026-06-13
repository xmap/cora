"""Distribution aggregate state, value objects, status enum, and domain errors.

A `Distribution` is a materialized byte-copy of a logical `Dataset` at a
storage `Supply`. Same scientific content as the Dataset, possibly
different format/location/access protocol. DCAT-3 `dcat:Distribution`
primitive imported directly.

## What a Distribution is

  - A specific byte-copy of a Dataset's content at a specific Supply
  - Has its own identity (`id`) distinct from the parent Dataset
  - Carries the same checksum + byte_size + encoding as the parent
    Dataset by invariant (byte-identical copy semantics; the decider
    enforces equality at registration per [[project-data-distribution-design]]
    L10 + L11)
  - Knows where the bytes live (uri + access_protocol)

## What a Distribution is NOT

  - Not the bytes (those live at the URI inside the Supply per
    [[project-data-territory-design]] L5)
  - Not the logical Dataset (Dataset is the content-identity tier;
    Distribution is the materialization tier; Fixture is to Assembly
    what Distribution is to Dataset)
  - Not an Edition (Edition is the publication-package tier;
    different aggregate per territory L1)
  - Not an Attestation (Attestation is the verify/format/bit-rot
    fact-chain; different aggregate per territory L7)

## Reused VOs

`DatasetChecksum` and `DatasetEncoding` are imported from the Dataset
aggregate and reused verbatim per [[project-data-distribution-design]]
L8. A Distribution's checksum/encoding are byte-identical to its
parent Dataset's; defining parallel VOs would duplicate identical
invariants and invite drift.

## New VOs

`DistributionUri` is a fresh class (per L7) with the same shape as
`DatasetUri` but distinct type identity: `Dataset.uri` is becoming
a denormalized convenience pointer to a canonical Distribution per
territory L5, while `Distribution.uri` carries the authoritative
value. Sharing a single VO type would obscure that asymmetry.

`AccessProtocol` is a closed `StrEnum` carrying the transport family
of the URI (HTTPS, Globus, S3, POSIX, NFS, OAI_PMH). All six values
land day-one per L5 even though only HTTPS + POSIX are pilot-validated
today; closed-not-open because each transport needs an adapter
before bytes can be moved or verified at that protocol.

`DistributionStatus` is a closed `StrEnum` carrying the 4-state
lifecycle (Registered, Verified, Stale, Discarded). All four land
day-one per L4 even though only Registered is reachable today
(genesis only); the Verified/Stale/Discarded transitions ship in
follow-on slices but the StrEnum and the nullable transition
attribution fields are present from the start (additive-state
pattern; matches `register_dataset` + Supply Slice 7B precedent).

## Verified/Stale flip is a projection, not an aggregate event

Per territory L7 + Distribution memo L7: `Distribution.status` flips
to `Verified` on `AttestationRecorded(kind=ChecksumVerified,
outcome=Match)` and to `Stale` on `outcome=Mismatch`. The flip is
projection-only (writer-side, no Distribution event emitted); the
Attestation aggregate carries the underlying fact. Distribution's
own state stream stays free of read-model feedback.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cora.data.aggregates.dataset.state import (
    DatasetChecksum,
    DatasetEncoding,
    _validate_storage_uri,  # pyright: ignore[reportPrivateUsage]
)
from cora.shared.identity import ActorId

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------

#: Max URI length, mirrors `DATASET_URI_MAX_LENGTH` for byte-identical
#: copy semantics: a Distribution's URI may differ from the Dataset's
#: but the length bound is the same.
DISTRIBUTION_URI_MAX_LENGTH = 2048


# ----------------------------------------------------------------------
# Status enum (closed; 4 values day-one per L4)
# ----------------------------------------------------------------------


class DistributionStatus(StrEnum):
    """The Distribution's lifecycle state.

    All four values ship day-one even though only ``Registered`` is
    reachable today (genesis only). Closed-StrEnum + day-one
    full-value-set per L4 avoids the additive-enum migration trap on
    future slices: Verified, Stale, and Discarded transitions all land
    additively, and from-stored replay on legacy events stays stable.

    Member name is SCREAMING_SNAKE per Python `StrEnum` / PEP 8
    convention; string value is PascalCase per CORA's BC-status-
    vocabulary fitness expectation.
    """

    REGISTERED = "Registered"
    VERIFIED = "Verified"
    STALE = "Stale"
    DISCARDED = "Discarded"


# ----------------------------------------------------------------------
# AccessProtocol enum (closed; 6 values day-one per L5)
# ----------------------------------------------------------------------


class AccessProtocol(StrEnum):
    """The Distribution's transport family.

    The URI scheme implies the transport (s3://, https://, globus://,
    file://, nfs://, oai-pmh://), but the operator-asserted enum is
    the source of truth because not every URI string is parseable
    into a clean scheme (custom file:// URIs sometimes carry POSIX
    semantics implicitly). Closed StrEnum; widening is additive when
    a new transport family's first adapter ships.

    Member name SCREAMING_SNAKE; string value PascalCase (or canonical
    form like ``OAI_PMH`` for OAI-PMH which is conventionally
    underscore-bracketed).
    """

    HTTPS = "HTTPS"
    GLOBUS = "Globus"
    S3 = "S3"
    POSIX = "POSIX"
    NFS = "NFS"
    OAI_PMH = "OAI_PMH"


#: Closed lookup mapping URI schemes (lowercase, per RFC 3986) to
#: AccessProtocol values. Used by the Slice 2 backfill (per L24) to
#: derive `access_protocol` from existing `Dataset.uri` rows. NO
#: fallback default: unmapped schemes raise
#: `UnmappedDistributionUriSchemeError` and abort the backfill.
URI_SCHEME_TO_ACCESS_PROTOCOL: Mapping[str, AccessProtocol] = {
    "https": AccessProtocol.HTTPS,
    "http": AccessProtocol.HTTPS,
    "globus": AccessProtocol.GLOBUS,
    "s3": AccessProtocol.S3,
    "file": AccessProtocol.POSIX,
    "nfs": AccessProtocol.NFS,
    "oai-pmh": AccessProtocol.OAI_PMH,
    "oaipmh": AccessProtocol.OAI_PMH,
}


# ----------------------------------------------------------------------
# Error classes (per L13 don't-hoist convention; per-BC isinstance)
# ----------------------------------------------------------------------


class InvalidDistributionUriError(Exception):
    """Raised when `DistributionUri` value fails validation.

    Mirrors `InvalidDatasetUriError` shape: value + reason. Same
    invariants (trim, length, urlparse scheme, XSS blocklist) and
    same blocked-scheme set per L7 copy-paste rationale.
    """

    def __init__(self, value: str, reason: str) -> None:
        super().__init__(f"Invalid Distribution URI {value!r}: {reason}")
        self.value = value
        self.reason = reason


class InvalidDistributionChecksumError(Exception):
    """Raised when the decider's checksum-shape re-check fails.

    Wraps `InvalidDatasetChecksumError` for operator-facing clarity
    (the failure happened during `register_distribution`, not
    `register_dataset`). Per L13 the underlying `DatasetChecksum` VO
    is reused verbatim; this class fires when the decider catches a
    VO failure and re-raises with Distribution-prefixed context.
    """

    def __init__(self, algorithm: str, value: str, reason: str) -> None:
        super().__init__(
            f"Invalid Distribution checksum (algorithm={algorithm!r}, value={value!r}): {reason}"
        )
        self.algorithm = algorithm
        self.value = value
        self.reason = reason


class InvalidDistributionByteSizeError(Exception):
    """Raised when ``byte_size < 0``.

    Zero is valid (empty Distributions are valid copies of empty
    Datasets). Negative is not.
    """

    def __init__(self, value: int, reason: str) -> None:
        super().__init__(f"Invalid Distribution byte_size {value}: {reason}")
        self.value = value
        self.reason = reason


class InvalidDistributionEncodingError(Exception):
    """Raised when the decider's encoding-shape re-check fails.

    Wraps `InvalidDatasetEncodingError` for operator-facing clarity.
    The underlying `DatasetEncoding` VO is reused verbatim per L8.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Distribution encoding: {reason}")
        self.reason = reason


class InvalidAccessProtocolError(Exception):
    """Raised when the decider gets an `access_protocol` outside the closed enum.

    Defensive only: the REST / MCP Pydantic boundary catches the same
    shape at 422 first. This decider-side re-check fires when an
    in-process caller (saga, atomic cross-BC write, test) bypasses
    the boundary with a bare string.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Invalid AccessProtocol value {value!r}: "
            f"not in {sorted(p.value for p in AccessProtocol)!r}"
        )
        self.value = value


class UnmappedDistributionUriSchemeError(Exception):
    """Raised by the Slice 2 backfill when a Dataset's URI scheme has no `AccessProtocol` mapping.

    Per L24: the backfill maps URI schemes to AccessProtocol via the
    closed `URI_SCHEME_TO_ACCESS_PROTOCOL` lookup. NO fallback
    default; any unmapped scheme raises this error and aborts the
    backfill. Operator must add the scheme to the closed lookup (and
    extend `AccessProtocol` if needed) or fix the source URI before
    retry.
    """

    def __init__(self, uri: str, scheme: str) -> None:
        super().__init__(
            f"Distribution backfill: URI scheme {scheme!r} (from {uri!r}) "
            f"has no AccessProtocol mapping. Add scheme to "
            f"URI_SCHEME_TO_ACCESS_PROTOCOL or fix source URI."
        )
        self.uri = uri
        self.scheme = scheme


class DistributionAlreadyExistsError(Exception):
    """Raised when the Distribution stream at `distribution_stream_id(new_id)` is non-empty.

    Genesis-only same-stream-id guard. Strict-not-idempotent per L16:
    re-registering the same `distribution_id` raises rather than
    silent no-op. The actual same-stream-id race at append time is
    caught by Postgres `ConcurrencyError` per L29; this class covers
    the in-process-replay case.
    """

    def __init__(self, distribution_id: UUID) -> None:
        super().__init__(f"Distribution {distribution_id} already exists")
        self.distribution_id = distribution_id


class DistributionSupplyNotFoundError(Exception):
    """Raised when `command.supply_id` does not resolve via `SupplyLookup.lookup`.

    Data-BC-local class (mirrors ``ProducingRunNotFoundError`` /
    ``LinkedSubjectNotFoundError`` precedent in
    `register_dataset.handler`). Lifts to HTTP 404.
    """

    def __init__(self, supply_id: UUID) -> None:
        super().__init__(f"Cannot register Distribution: supply_id {supply_id} does not exist")
        self.supply_id = supply_id


class DistributionCannotRegisterOnNonStorageSupplyError(Exception):
    """Raised when `SupplyLookup.lookup` resolves the Supply but `kind != "Storage"`.

    Domain conflict; lifts to HTTP 409. Operator remedy: register a
    storage-kind Supply or pick a different `supply_id`.
    """

    def __init__(self, supply_id: UUID, actual_kind: str) -> None:
        super().__init__(
            f"Cannot register Distribution on Supply {supply_id}: "
            f"kind={actual_kind!r} (expected {STORAGE_SUPPLY_KIND!r})"
        )
        self.supply_id = supply_id
        self.actual_kind = actual_kind


class DistributionCannotRegisterOnDiscardedDatasetError(Exception):
    """Raised when `context.dataset.status == DatasetStatus.DISCARDED`.

    Cannot bind a new Distribution to a Dataset whose bytes have been
    deleted (Discarded is GDPR-shaped). Mirrors
    `DerivedFromDatasetsDiscardedError` precedent. Note: a
    ``Retracted``-intent Dataset IS allowed to receive new
    Distributions (intent and status are orthogonal axes).
    """

    def __init__(self, dataset_id: UUID) -> None:
        super().__init__(
            f"Cannot register Distribution on Dataset {dataset_id}: "
            f"Dataset is Discarded (bytes deleted; cannot bind new copy)"
        )
        self.dataset_id = dataset_id


class DistributionChecksumMismatchError(Exception):
    """Raised when ``command.checksum_value != dataset.checksum.value``.

    Byte-identical-copy invariant per L10: a Distribution is a
    byte-identical copy of a Dataset, so checksums must match by
    definition. Lifts to HTTP 409.
    """

    def __init__(self, dataset_id: UUID, expected_checksum: str, actual_checksum: str) -> None:
        super().__init__(
            f"Distribution checksum mismatch against Dataset {dataset_id}: "
            f"expected {expected_checksum!r} (from Dataset), "
            f"got {actual_checksum!r} (from command)"
        )
        self.dataset_id = dataset_id
        self.expected_checksum = expected_checksum
        self.actual_checksum = actual_checksum


class DistributionByteSizeMismatchError(Exception):
    """Raised when ``command.byte_size != dataset.byte_size``.

    Byte-identical-copy invariant per L11. Belt-and-braces with
    checksum equality (same logical claim, redundant validation).
    """

    def __init__(self, dataset_id: UUID, expected_byte_size: int, actual_byte_size: int) -> None:
        super().__init__(
            f"Distribution byte_size mismatch against Dataset {dataset_id}: "
            f"expected {expected_byte_size} (from Dataset), "
            f"got {actual_byte_size} (from command)"
        )
        self.dataset_id = dataset_id
        self.expected_byte_size = expected_byte_size
        self.actual_byte_size = actual_byte_size


#: Canonical value used by the decider's `Supply.kind` check. Per L30:
#: PascalCase per CORA closed-StrEnum convention. The Supply BC uses
#: a free-form string `kind` today (validated via `validate_bounded_text`,
#: not yet a closed StrEnum), so we pin the literal here and grep'd
#: against Supply's existing usage at implementation time.
STORAGE_SUPPLY_KIND = "Storage"


# ----------------------------------------------------------------------
# DistributionUri value object (per L7; fresh class, shape copy of DatasetUri)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class DistributionUri:
    """Opaque URI string pointing at the bulk content for this Distribution.

    Trimmed; 1-2048 chars. Loose validation: `urllib.parse.urlparse`
    must return a non-empty scheme. XSS blocklist applied (shared
    with `DatasetUri.value` blocklist; same threat surface).

    Distinct type identity from `DatasetUri` per L7: `Dataset.uri` is
    becoming a denormalized convenience pointer to a canonical
    Distribution per territory L5, while `Distribution.uri` carries
    the authoritative byte-location. Sharing a single VO type would
    obscure that asymmetry.

    Bytes resolution / existence check is out of scope at the BC
    layer (mirrors `DatasetUri`); periodic re-checksum / verification
    is its own future workflow per the Attestation aggregate.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = _validate_storage_uri(
            self.value,
            max_length=DISTRIBUTION_URI_MAX_LENGTH,
            error_factory=InvalidDistributionUriError,
        )
        object.__setattr__(self, "value", trimmed)


def validate_distribution_byte_size(value: int) -> int:
    """Normalize / validate byte_size for the Distribution state and decider.

    Zero is valid (a Distribution of an empty Dataset is a valid
    empty Distribution); negative is not. Mirrors Dataset's
    `validate_byte_size` shape.
    """
    if value < 0:
        raise InvalidDistributionByteSizeError(
            value, "byte_size must be >= 0 (zero is valid for empty Distributions)"
        )
    return value


# ----------------------------------------------------------------------
# Distribution aggregate root
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class Distribution:
    """Aggregate root: one materialized byte-copy of a Dataset at a Supply.

    Frozen dataclass. The 9 core intrinsic + binding fields are set
    at genesis and immutable thereafter. The 7 transition attribution
    fields default to None and are populated by future-slice evolver
    arms (additive-state pattern; matches Dataset + Asset + Supply
    precedent for forward-compat on legacy event streams).

    Status FSM (per L4):
        Registered -> Verified -> Stale -> Discarded

    All four StrEnum values declared day-one even though only
    Registered is reachable today. The Verified flip is
    projection-only (Attestation Slice C); the Stale and Discarded
    transitions ship in follow-on slices.

    DatasetChecksum and DatasetEncoding reused verbatim from the
    Dataset aggregate per L8 (byte-identical copy semantics).
    """

    id: UUID
    dataset_id: UUID
    supply_id: UUID
    uri: DistributionUri
    checksum: DatasetChecksum
    byte_size: int
    encoding: DatasetEncoding
    access_protocol: AccessProtocol
    registered_at: datetime
    registered_by: ActorId
    status: DistributionStatus = DistributionStatus.REGISTERED
    # Nullable transition attribution fields, populated by future slices'
    # evolver arms (additive-state pattern per L18).
    verified_at: datetime | None = None
    verified_by: ActorId | None = None
    marked_stale_at: datetime | None = None
    marked_stale_by: ActorId | None = None
    discarded_at: datetime | None = None
    discarded_by: ActorId | None = None
    discard_reason: str | None = None
