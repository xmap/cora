"""Edition aggregate state, value objects, status / kind enums, and domain errors.

An `Edition` is a citable publication-package: a frozen set of
Production-intent Datasets bundled into a sealed, optionally
DOI-minted, optionally tombstoned artifact. ISBD / FRBR / BIBFRAME
publication-tier; DCAT-3 has no direct primitive (Distribution
sits one tier below).

## What an Edition is

  - A publication-grade artifact that names a set of Datasets
    + a publisher Facility + a license + a citation year
  - Carries its own identity (`id`) distinct from member Datasets
  - Has a sealing `content_hash` set at the Sealed transition (sha256
    of the canonical serialized form via `EditionSerializer`)
  - Optionally carries an `external_pid` (DOI minted via DoiMinter)
    after the Published transition
  - Can be tombstoned (Withdrawn) without deleting the DOI

## What an Edition is NOT

  - Not the bytes (those live at member Distributions / Supplies)
  - Not a Dataset (Dataset is the content-identity tier)
  - Not a Distribution (Distribution is the materialization tier)
  - Not an Attestation (Attestation is the verify / bit-rot
    fact-chain on Distribution)

## Closed kind enum (6 values day-one)

`EditionKind` ships all 6 values day-one: {ROCrate, DataCite,
Croissant, OAIS_AIP, OAIS_DIP, NeXus}. Only `RoCrate12Adapter`
ships today at the serializer port; the other 5 are
adapter-deferred. Closed-StrEnum day-one avoids the additive-enum
migration trap on future serializer adapter slices. Member name
SCREAMING_SNAKE per Python `StrEnum` / PEP 8; string value mostly
PascalCase per CORA's BC-status-vocabulary fitness expectation
(OAIS_AIP / OAIS_DIP keep underscores due to OAIS ALL_CAPS norm).

## Status FSM (4 states; Withdrawn terminal)

  Registered -> Sealed -> Published -> Withdrawn

All four StrEnum values declared day-one; transitions ship across
the 5 slices A-E with all nullable attribution columns present in
the projection migration from day one (additive-state pattern;
mirrors Distribution + Asset + Supply precedent).

## Two-content-hash model

`Edition.content_hash` is set ONCE at the Sealed transition (sha256
of the pre-DOI serializer output) and is immutable thereafter.

The `EditionPublished` event payload carries a SEPARATE
`published_content_hash` (sha256 of the re-serialized post-DOI
bytes); the projection denormalizes both via separate columns. The
aggregate state does NOT carry `published_content_hash` (projection +
event payload only). Sealed hash anchors operator commit to shape +
membership; published hash anchors the cited artifact bytes.

## License kind-gate (DataCite / Croissant only)

`license: SpdxIdentifier | None` is optional for most kinds but
REQUIRED at the Sealed transition for kinds in `{DataCite, Croissant}`.
The serializer adapter for those kinds cannot produce a complete
record without it. RO-Crate also strongly recommends a license but
does not require it; the gate may widen as adapters ship.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cora.shared.facility_code import FacilityCode
from cora.shared.identifier import PersistentIdentifier
from cora.shared.identity import ActorId

EDITION_TITLE_MAX_LENGTH = 500
EDITION_LICENSE_MAX_LENGTH = 100
EDITION_WITHDRAWAL_REASON_MAX_LENGTH = 500
EDITION_AFFILIATION_MAX_LENGTH = 200
EDITION_PUBLICATION_YEAR_MIN = 1900
EDITION_PUBLICATION_YEAR_FUTURE_BUDGET = 5
EDITION_CREATORS_MIN = 1
EDITION_CREATORS_MAX = 100
EDITION_DATASET_IDS_MIN = 1

# SPDX identifier character class: alphanumeric + `.`, `-`, `+`. SPDX
# expression syntax additionally uses parentheses and `WITH` / `AND` / `OR`
# keywords; today's free-text pass accepts simple identifier
# strings only. Closed-allowlist is a future tightening per Watch item W3.
_SPDX_ALLOWED_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.-+")


# ----------------------------------------------------------------------
# Closed kind enum (6 values day-one)
# ----------------------------------------------------------------------


class EditionKind(StrEnum):
    """The Edition's serialization-target kind.

    All six values ship day-one even though only ``ROCrate`` is
    reachable today (only `RoCrate12Adapter` lands at the seal slice).
    Closed-StrEnum + day-one full-value-set avoids the additive-enum
    migration trap on future adapter slices.

    Python member name SCREAMING_SNAKE per PEP 8. String value
    PascalCase per CORA's BC-status-vocabulary convention; OAIS_AIP
    and OAIS_DIP keep underscores because the OAIS standard uses
    ALL_CAPS abbreviations. Serializer adapters MAY translate to
    spec-required forms at the wire boundary (DataCite
    ``<resourceType>`` uses "OAIS-AIP" with a hyphen).
    """

    ROCRATE = "ROCrate"
    DATACITE = "DataCite"
    CROISSANT = "Croissant"
    OAIS_AIP = "OAIS_AIP"
    OAIS_DIP = "OAIS_DIP"
    NEXUS = "NeXus"


# ----------------------------------------------------------------------
# Closed status enum (4 values day-one)
# ----------------------------------------------------------------------


class EditionStatus(StrEnum):
    """The Edition's lifecycle state.

    All four values ship day-one. FSM:

      Registered -> Sealed -> Published -> Withdrawn

    Withdrawn is terminal (DataCite tombstone semantics: DOI stays
    Findable but resolves to a tombstone page). Re-publish from
    Withdrawn is rejected; operator registers a new Edition with
    ``replaces_edition_id`` (future slice; deferred Watch item).
    """

    REGISTERED = "Registered"
    SEALED = "Sealed"
    PUBLISHED = "Published"
    WITHDRAWN = "Withdrawn"


# Kinds that require a license at the Sealed transition. Other kinds
# may sealed without a license. Widening to RO-Crate is a Watch item.
LICENSE_REQUIRED_KINDS: frozenset[EditionKind] = frozenset(
    {EditionKind.DATACITE, EditionKind.CROISSANT}
)


# ----------------------------------------------------------------------
# Error classes (un-hoisted per genesis-error-classes convention)
# ----------------------------------------------------------------------


class InvalidEditionTitleError(ValueError):
    """The supplied Edition title is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Edition title must be 1-{EDITION_TITLE_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidEditionKindError(ValueError):
    """The supplied Edition kind is not in the closed `EditionKind` enum.

    Defensive only; the REST / MCP Pydantic boundary catches the same
    shape at 422 first. Fires when an in-process caller bypasses the
    boundary with a bare string.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Invalid EditionKind value {value!r}: not in {sorted(k.value for k in EditionKind)!r}"
        )
        self.value = value


class InvalidPublicationYearError(ValueError):
    """The supplied publication_year is out of the 1900..current_year+5 window."""

    def __init__(self, value: int, current_year: int) -> None:
        upper = current_year + EDITION_PUBLICATION_YEAR_FUTURE_BUDGET
        super().__init__(
            f"Edition publication_year must be "
            f"{EDITION_PUBLICATION_YEAR_MIN}..{upper} (got: {value})"
        )
        self.value = value
        self.current_year = current_year


class InvalidSpdxIdentifierError(ValueError):
    """The supplied license string failed SPDX character-class validation."""

    def __init__(self, value: str, reason: str) -> None:
        super().__init__(f"Edition license SPDX identifier invalid ({reason}): {value!r}")
        self.value = value
        self.reason = reason


class InvalidEditionWithdrawalReasonError(ValueError):
    """The supplied withdrawal reason is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Edition withdrawal reason must be "
            f"1-{EDITION_WITHDRAWAL_REASON_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidCreatorsError(ValueError):
    """The supplied creators tuple is empty, oversize, or has duplicate actor_ids.

    Also covers per-creator affiliation length validation; the unified
    error class keeps the operator-facing message short.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Edition creators invalid: {reason}")
        self.reason = reason


class EmptyDatasetIdsAtRegistrationError(ValueError):
    """register_edition was called with an empty dataset_ids set.

    Today requires at least one Dataset at genesis. Operator may add
    more via add_dataset_to_edition; cannot register an empty
    Edition.
    """

    def __init__(self) -> None:
        super().__init__(
            f"Edition register requires at least {EDITION_DATASET_IDS_MIN} dataset_ids (got: 0)"
        )


class EditionNotFoundError(Exception):
    """The Edition stream is empty (no genesis event yet)."""

    def __init__(self, edition_id: UUID) -> None:
        super().__init__(f"Edition {edition_id} not found")
        self.edition_id = edition_id


class EditionAlreadyExistsError(Exception):
    """Defensive: state is non-None at register_edition decider (in-process race)."""

    def __init__(self, edition_id: UUID) -> None:
        super().__init__(f"Edition {edition_id} already exists")
        self.edition_id = edition_id


class EditionCannotBindToDiscardedDatasetError(Exception):
    """A member Dataset has status==DISCARDED at register / add time.

    Cannot bind a publication to a Dataset whose bytes have been
    deleted (Discarded is GDPR-shaped on Dataset). Mirrors the
    Distribution precedent.
    """

    def __init__(self, dataset_id: UUID) -> None:
        super().__init__(f"Cannot bind Edition to Dataset {dataset_id}: Dataset is Discarded")
        self.dataset_id = dataset_id


class EditionNotInRegisteredStateError(Exception):
    """Add or remove dataset called on a non-Registered Edition.

    Single shared class for both add and remove state guards per the
    locked naming. Carries `current_status` so the operator can see
    what state blocked the membership mutation.
    """

    def __init__(self, edition_id: UUID, current_status: EditionStatus) -> None:
        super().__init__(
            f"Edition {edition_id} not in Registered state "
            f"(current_status={current_status.value!r}); "
            "membership mutations are only allowed before Sealed"
        )
        self.edition_id = edition_id
        self.current_status = current_status


class EditionDatasetAlreadyMemberError(Exception):
    """add_dataset_to_edition called with a dataset_id that's already a member.

    Strict-not-idempotent per Plan.wires precedent.
    """

    def __init__(self, edition_id: UUID, dataset_id: UUID) -> None:
        super().__init__(f"Edition {edition_id}: Dataset {dataset_id} is already a member")
        self.edition_id = edition_id
        self.dataset_id = dataset_id


class EditionDatasetNotMemberError(Exception):
    """remove_dataset_from_edition called with a dataset_id that's not a member.

    Strict-not-idempotent per Plan.wires precedent. Lifts to 404 per
    the locked taxonomy.
    """

    def __init__(self, edition_id: UUID, dataset_id: UUID) -> None:
        super().__init__(f"Edition {edition_id}: Dataset {dataset_id} is not a member")
        self.edition_id = edition_id
        self.dataset_id = dataset_id


class EditionCannotBeEmptyError(Exception):
    """remove_dataset_from_edition would leave the Edition with zero datasets.

    Rejected at remove rather than discovered at Seal (better operator
    UX: the error fires at the action that caused it).
    """

    def __init__(self, edition_id: UUID) -> None:
        super().__init__(
            f"Edition {edition_id}: cannot remove last Dataset "
            "(Edition must have at least one Dataset member)"
        )
        self.edition_id = edition_id


class EditionCannotSealError(Exception):
    """seal_edition called on a non-Registered Edition.

    Strict-not-idempotent on re-seal. Carries `current_status` so the
    operator can see what state blocked the transition.
    """

    def __init__(self, edition_id: UUID, current_status: EditionStatus) -> None:
        super().__init__(
            f"Edition {edition_id} cannot seal "
            f"(current_status={current_status.value!r}); "
            "seal requires Registered state"
        )
        self.edition_id = edition_id
        self.current_status = current_status


class EditionRequiresAtLeastOneDatasetError(Exception):
    """Defensive: seal_edition decider invoked with empty dataset_ids.

    Impossible for the happy path because remove_dataset_from_edition
    rejects the last-removal; defensive for cross-facility imports
    bypassing the standard handler chain.
    """

    def __init__(self, edition_id: UUID) -> None:
        super().__init__(f"Edition {edition_id} cannot seal: dataset_ids is empty")
        self.edition_id = edition_id


class EditionDatasetsNotAllProductionError(Exception):
    """seal_edition rejected because one or more member Datasets are not Production.

    Carries the offending (dataset_id, actual_intent) pairs so the
    operator can locate the non-Production Datasets and either
    promote them or remove them from the Edition.
    """

    def __init__(
        self,
        edition_id: UUID,
        offenders: tuple[tuple[UUID, str], ...],
    ) -> None:
        offender_strs = ", ".join(f"({dataset_id}, {intent!r})" for dataset_id, intent in offenders)
        super().__init__(
            f"Edition {edition_id} cannot seal: "
            f"all member Datasets must be Production intent (offenders: {offender_strs})"
        )
        self.edition_id = edition_id
        self.offenders = offenders


class EditionCannotSealOnDiscardedDatasetError(Exception):
    """seal_edition rejected because one or more member Datasets became Discarded.

    Edition was registered with active Datasets; a Dataset got
    Discarded between add and seal. Cannot seal because the bytes are
    gone. Operator must remove the Discarded Dataset and re-seal.
    """

    def __init__(self, edition_id: UUID, dataset_ids: tuple[UUID, ...]) -> None:
        super().__init__(
            f"Edition {edition_id} cannot seal: Datasets are Discarded: {list(dataset_ids)!r}"
        )
        self.edition_id = edition_id
        self.dataset_ids = dataset_ids


class EditionLicenseRequiredForKindError(Exception):
    """seal_edition rejected because kind requires a license but none was supplied.

    Fires for `kind in {DataCite, Croissant}` when license is None.
    Other kinds bypass this guard. Watch item: widen to RO-Crate if
    operator demand surfaces.
    """

    def __init__(self, edition_id: UUID, kind: EditionKind) -> None:
        super().__init__(
            f"Edition {edition_id} cannot seal: kind={kind.value!r} requires a non-null license"
        )
        self.edition_id = edition_id
        self.kind = kind


class EditionPublisherNotFoundError(Exception):
    """seal_edition rejected because the publisher Facility code did not resolve.

    FacilityLookup.lookup_by_code(publisher_code) returned None.
    Mirrors `SupplyFacilityNotFoundError` precedent. Lifts to 404.
    """

    def __init__(self, facility_code: str) -> None:
        super().__init__(
            f"Edition cannot seal: publisher Facility code {facility_code!r} not found"
        )
        self.facility_code = facility_code


class EditionDatasetDistributionNotFoundError(Exception):
    """seal_edition rejected because a member Dataset has no canonical Distribution.

    The serializer needs the canonical Distribution's `uri` /
    `checksum` / `byte_size` / `encoding`. If a Dataset has zero
    materialized Distributions, there is nothing to cite.
    """

    def __init__(self, edition_id: UUID, dataset_ids: tuple[UUID, ...]) -> None:
        super().__init__(
            f"Edition {edition_id} cannot seal: "
            f"Datasets have no Distribution: {list(dataset_ids)!r}"
        )
        self.edition_id = edition_id
        self.dataset_ids = dataset_ids


class EditionSerializerError(Exception):
    """The EditionSerializer adapter raised at seal or publish time.

    Wraps any underlying adapter failure (RoCrate12Adapter, future
    DataCite / Croissant / OAIS / NeXus adapters). Lifts to 502 (port
    failure, not domain conflict).
    """

    def __init__(self, kind: EditionKind, reason: str) -> None:
        super().__init__(f"Edition serializer failed for kind={kind.value!r}: {reason}")
        self.kind = kind
        self.reason = reason


class EditionCannotPublishError(Exception):
    """publish_edition called on a non-Sealed Edition.

    Strict-not-idempotent on re-publish. Carries `current_status`.
    """

    def __init__(self, edition_id: UUID, current_status: EditionStatus) -> None:
        super().__init__(
            f"Edition {edition_id} cannot publish "
            f"(current_status={current_status.value!r}); "
            "publish requires Sealed state"
        )
        self.edition_id = edition_id
        self.current_status = current_status


class EditionPublishedWithoutContentHashError(Exception):
    """Defensive invariant: Sealed Edition has no content_hash.

    Impossible-by-state under happy-path; defensive for malformed
    streams or contract-breaking adapter swaps.
    """

    def __init__(self, edition_id: UUID) -> None:
        super().__init__(
            f"Edition {edition_id} is Sealed but has no content_hash "
            "(defensive invariant; should be unreachable)"
        )
        self.edition_id = edition_id


class EditionCannotWithdrawError(Exception):
    """withdraw_edition called on a non-Published Edition.

    Sealed-not-Published is rejected because there is nothing to
    tombstone at DataCite. Carries `current_status`.
    """

    def __init__(self, edition_id: UUID, current_status: EditionStatus) -> None:
        super().__init__(
            f"Edition {edition_id} cannot withdraw "
            f"(current_status={current_status.value!r}); "
            "withdraw requires Published state"
        )
        self.edition_id = edition_id
        self.current_status = current_status


class EditionWithdrawnWithoutPersistentIdError(Exception):
    """Defensive invariant: Published Edition has no external_pid.

    Impossible-by-state under happy-path (the Published transition
    always sets external_pid); defensive for malformed streams or
    contract-breaking adapter swaps. Mirrors
    `EditionPublishedWithoutContentHashError`.
    """

    def __init__(self, edition_id: UUID) -> None:
        super().__init__(
            f"Edition {edition_id} is Published but has no external_pid "
            "(defensive invariant; should be unreachable)"
        )
        self.edition_id = edition_id


class DoiMinterTombstoneError(Exception):
    """DoiMinter.tombstone raised at withdraw time.

    Distinct from `PersistentIdentifierMintError` because operator
    remediation differs: mint failure -> retry; tombstone failure ->
    escalate, the DOI stays Findable at DataCite. Lifts to 502.
    """

    def __init__(self, persistent_id_value: str, reason: str) -> None:
        super().__init__(
            f"DoiMinter tombstone failed for persistent_id={persistent_id_value!r}: {reason}"
        )
        self.persistent_id_value = persistent_id_value
        self.reason = reason


# ----------------------------------------------------------------------
# Value objects
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class EditionTitle:
    """Display title for an Edition. Trimmed; 1-500 chars.

    Mirrors `DatasetName` / `DistributionUri` shape. The on-the-wire
    representation on `EditionRegistered.title` is `str` (post-trim).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not trimmed or len(trimmed) > EDITION_TITLE_MAX_LENGTH:
            raise InvalidEditionTitleError(self.value)
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class SpdxIdentifier:
    """Free-text SPDX identifier. Trimmed; 1-100 chars; SPDX-character-class.

    Free-text today per Lock 12. Closed-allowlist tightening
    is a Watch item triggered at the 3rd rejected operator-supplied
    id. The on-the-wire representation on event payloads is bare
    `str` (post-trim) per the wire-payload bare-str convention.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not trimmed:
            raise InvalidSpdxIdentifierError(self.value, "empty or whitespace-only")
        if len(trimmed) > EDITION_LICENSE_MAX_LENGTH:
            raise InvalidSpdxIdentifierError(
                self.value, f"exceeds {EDITION_LICENSE_MAX_LENGTH} chars"
            )
        for ch in trimmed:
            if ch not in _SPDX_ALLOWED_CHARS:
                raise InvalidSpdxIdentifierError(
                    self.value,
                    f"character {ch!r} not in SPDX identifier character class",
                )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class WithdrawalReason:
    """Free-form withdrawal reason. Trimmed; 1-500 chars.

    Mandatory at withdraw time per audit-trail requirement: tombstoning
    a public DOI MUST carry WHY forever. Mirrors `DatasetDiscardReason`
    shape.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not trimmed:
            raise InvalidEditionWithdrawalReasonError(self.value)
        if len(trimmed) > EDITION_WITHDRAWAL_REASON_MAX_LENGTH:
            raise InvalidEditionWithdrawalReasonError(self.value)
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Creator:
    """A creator credited on the Edition. Ordered tuple semantics on the carrier.

    `actor_id` is the internal-opaque Actor.id (NOT externalized to
    the public-facing record; the serializer adapter resolves it to a
    name / ORCID via ActorLookup port when that ships).

    `affiliation` is optional free-text 1-200 chars when supplied.

    Validation lives at the carrier aggregate (creators tuple-level
    invariants: 1-100 entries, no duplicate actor_id, affiliation
    bounded). This dataclass enforces only affiliation length so a
    bare construction fails fast on malformed input.
    """

    actor_id: ActorId
    affiliation: str | None = None

    def __post_init__(self) -> None:
        if self.affiliation is not None:
            trimmed = self.affiliation.strip()
            if not trimmed:
                raise InvalidCreatorsError(
                    f"affiliation empty or whitespace-only for actor_id {self.actor_id}"
                )
            if len(trimmed) > EDITION_AFFILIATION_MAX_LENGTH:
                raise InvalidCreatorsError(
                    f"affiliation exceeds {EDITION_AFFILIATION_MAX_LENGTH} chars "
                    f"for actor_id {self.actor_id}"
                )
            object.__setattr__(self, "affiliation", trimmed)


def validate_publication_year(value: int, *, current_year: int) -> int:
    """Range-check a publication_year against [1900..current_year+5]."""
    upper = current_year + EDITION_PUBLICATION_YEAR_FUTURE_BUDGET
    if value < EDITION_PUBLICATION_YEAR_MIN or value > upper:
        raise InvalidPublicationYearError(value, current_year=current_year)
    return value


def validate_creators(creators: tuple[Creator, ...]) -> tuple[Creator, ...]:
    """Tuple-level creators invariants: 1-100 entries; no duplicate actor_id."""
    if len(creators) < EDITION_CREATORS_MIN:
        raise InvalidCreatorsError(
            f"creators must have at least {EDITION_CREATORS_MIN} entry (got: {len(creators)})"
        )
    if len(creators) > EDITION_CREATORS_MAX:
        raise InvalidCreatorsError(
            f"creators must have at most {EDITION_CREATORS_MAX} entries (got: {len(creators)})"
        )
    seen: set[ActorId] = set()
    for creator in creators:
        if creator.actor_id in seen:
            raise InvalidCreatorsError(f"duplicate actor_id in creators: {creator.actor_id}")
        seen.add(creator.actor_id)
    return creators


# ----------------------------------------------------------------------
# Edition aggregate root
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class Edition:
    """Aggregate root: one citable publication-package over a set of Datasets.

    Frozen dataclass. Genesis fields (id, kind, title, creators,
    registered_at, registered_by) are immutable thereafter.
    `dataset_ids` mutates through Registered-state membership events.
    The Sealed / Published / Withdrawn transitions populate the
    nullable attribution fields additively (matches Distribution +
    Asset + Supply precedent for forward-compat on legacy events).

    Status FSM: Registered -> Sealed -> Published -> Withdrawn.

    Two-content-hash model: `content_hash` set ONCE at Sealed and
    immutable thereafter; `published_content_hash` lives on the
    event payload + projection, NOT on this state object.
    """

    id: UUID
    kind: EditionKind
    title: EditionTitle
    dataset_ids: frozenset[UUID]
    creators: tuple[Creator, ...]
    registered_at: datetime
    registered_by: ActorId
    status: EditionStatus = EditionStatus.REGISTERED
    publisher_facility_code: FacilityCode | None = None
    publication_year: int | None = None
    license: SpdxIdentifier | None = None
    content_hash: str | None = None
    external_pid: PersistentIdentifier | None = None
    sealed_at: datetime | None = None
    sealed_by: ActorId | None = None
    published_at: datetime | None = None
    published_by: ActorId | None = None
    withdrawn_at: datetime | None = None
    withdrawn_by: ActorId | None = None
    withdrawal_reason: str | None = None


__all__ = [
    "EDITION_AFFILIATION_MAX_LENGTH",
    "EDITION_CREATORS_MAX",
    "EDITION_CREATORS_MIN",
    "EDITION_DATASET_IDS_MIN",
    "EDITION_LICENSE_MAX_LENGTH",
    "EDITION_PUBLICATION_YEAR_FUTURE_BUDGET",
    "EDITION_PUBLICATION_YEAR_MIN",
    "EDITION_TITLE_MAX_LENGTH",
    "EDITION_WITHDRAWAL_REASON_MAX_LENGTH",
    "LICENSE_REQUIRED_KINDS",
    "Creator",
    "DoiMinterTombstoneError",
    "Edition",
    "EditionAlreadyExistsError",
    "EditionCannotBeEmptyError",
    "EditionCannotBindToDiscardedDatasetError",
    "EditionCannotPublishError",
    "EditionCannotSealError",
    "EditionCannotSealOnDiscardedDatasetError",
    "EditionCannotWithdrawError",
    "EditionDatasetAlreadyMemberError",
    "EditionDatasetDistributionNotFoundError",
    "EditionDatasetNotMemberError",
    "EditionDatasetsNotAllProductionError",
    "EditionKind",
    "EditionLicenseRequiredForKindError",
    "EditionNotFoundError",
    "EditionNotInRegisteredStateError",
    "EditionPublishedWithoutContentHashError",
    "EditionPublisherNotFoundError",
    "EditionRequiresAtLeastOneDatasetError",
    "EditionSerializerError",
    "EditionStatus",
    "EditionTitle",
    "EditionWithdrawnWithoutPersistentIdError",
    "EmptyDatasetIdsAtRegistrationError",
    "InvalidCreatorsError",
    "InvalidEditionKindError",
    "InvalidEditionTitleError",
    "InvalidEditionWithdrawalReasonError",
    "InvalidPublicationYearError",
    "InvalidSpdxIdentifierError",
    "SpdxIdentifier",
    "WithdrawalReason",
    "validate_creators",
    "validate_publication_year",
]
