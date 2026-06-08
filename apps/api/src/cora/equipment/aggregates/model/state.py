"""Model aggregate state, status enum, errors, and value objects.

`Model` is the Equipment BC's vendor-catalog entry: HOW a deployed
`Asset` is identified as an instance of "Vendor X part number Y".
A `Model` pins together a `Manufacturer` (name plus optional
identifier in a closed-StrEnum scheme), a `part_number` (vendor SKU),
and a `declared_family_ids: frozenset[UUID]` pointing at one or more
registered `Family` aggregates that the catalog entry satisfies.

## Aggregate scope

Model sits between `Family` (the device-class kind) and `Asset` (the
deployed instance) in the Equipment ladder. Examples: an Aerotech
ANT130-L rotary stage is one Model; the two PCO Edge 5.5 cameras
mounted at 2-BM share a single Model. Asset gains an optional
`model_id` pointer; if set, `Model.declared_family_ids` must be a
subset of `Asset.family_ids` at `register_asset` and `add_asset_family`
time (cross-BC subset invariant).

`declared_family_ids: frozenset[UUID]` is REQUIRED at `define_model`
time with cardinality at least one (empty rejected at the API
boundary). The set mutates incrementally through `add_model_family`
and `remove_model_family` (targeted-mutation events), or wholesale
through `version_model` (a new version IS a new declaration; matches
Family/Method/Plan/Practice replace-on-version precedent).

## Catalog-tier required-manufacturer rationale

`Manufacturer` is required: a catalog entry without a manufacturer is
incoherent across the four catalog-tier traditions (CMMS Equipment
Type per ISO 14224, AAS Type-AAS DigitalNameplate IDTA 02006, OPC UA
vendor profile, ECLASS-augmented Property). The PIDINST property 6
`1-n Mandatory` cardinality is an INSTANCE-tier obligation (PIDINST
v1.0 spec page 1: "The group considers instrument instances, e.g.
the individual physical objects, as opposed to instrument types or
models") and transfers to `Asset.alternate_identifiers` in a future
slice, NOT to `Model.manufacturer` at the catalog tier.

## Status as enum-in-state, derived-from-event-type-in-evolver

`ModelStatus` is a `StrEnum` so the values would serialize naturally
as JSON-friendly strings IF carried in an event payload. Today they
aren't: state holds the enum (typed) and the evolver derives the new
status from the event TYPE, mirroring `FamilyStatus`.

## Closed `ManufacturerIdentifierType` enum

`ManufacturerIdentifierType` is a closed StrEnum (`ROR | GRID | ISNI`)
per the [[project-family-affordance-design]] closed-vocabulary
precedent. Adding a fourth scheme (e.g., `WIKIDATA`) is an additive
enum change at a future migration boundary.

## Bounded-name VOs

`ModelName`, `PartNumber`, `ManufacturerName`, `ManufacturerIdentifier`,
`ModelVersionTag`, and `ModelDeprecationReason` follow the
trimmed-bounded-text VO pattern via the shared
`validate_bounded_text` helper. Part numbers are NOT case-folded
because vendor SKUs are case-sensitive (`RV120CCHL` and `rv120cchl`
are different Newport entries).
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cora.shared.bounded_text import bounded_name, validate_bounded_text

MODEL_NAME_MAX_LENGTH = 200
MODEL_PART_NUMBER_MAX_LENGTH = 100
MODEL_VERSION_TAG_MAX_LENGTH = 50
MODEL_DEPRECATION_REASON_MAX_LENGTH = 500
MANUFACTURER_NAME_MAX_LENGTH = 200
MANUFACTURER_IDENTIFIER_MAX_LENGTH = 200


class ModelStatus(StrEnum):
    """The Model's lifecycle state.

    Transitions:
      - Defined -> Versioned        (version_model)
      - (Defined | Versioned) -> Deprecated   (deprecate_model)

    `Defined` is the genesis state set by `define_model`. Multi-source
    `(Defined | Versioned) -> Versioned` matches the Family precedent
    at `family/state.py` (`FamilyCannotVersionError`).
    """

    DEFINED = "Defined"
    VERSIONED = "Versioned"
    DEPRECATED = "Deprecated"


class ManufacturerIdentifierType(StrEnum):
    """Closed scheme for the optional manufacturer identifier.

    Three members ship in v1: ROR (Research Organization Registry),
    GRID (Global Research Identifier Database; subsumed by ROR but
    still in active use at many facilities), ISNI (International
    Standard Name Identifier). Adding a fourth scheme is an additive
    enum change.
    """

    ROR = "ROR"
    GRID = "GRID"
    ISNI = "ISNI"


class InvalidModelNameError(ValueError):
    """The supplied model name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Model name must be 1-{MODEL_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidPartNumberError(ValueError):
    """The supplied part number is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Part number must be 1-{MODEL_PART_NUMBER_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidManufacturerNameError(ValueError):
    """The supplied manufacturer name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Manufacturer name must be 1-{MANUFACTURER_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidManufacturerIdentifierError(ValueError):
    """The supplied manufacturer identifier is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Manufacturer identifier must be 1-{MANUFACTURER_IDENTIFIER_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidManufacturerIdentifierPairingError(ValueError):
    """`identifier` and `identifier_type` must be both set or both None.

    Cross-field invariant: setting only one half of the optional pair
    is ambiguous (a bare identifier with no scheme cannot be resolved;
    a scheme with no identifier is meaningless). Both together, or
    both None.
    """

    def __init__(self, *, identifier: str | None, identifier_type: object) -> None:
        super().__init__(
            "Manufacturer.identifier and Manufacturer.identifier_type must be both set "
            f"or both None (got identifier={identifier!r}, identifier_type={identifier_type!r})"
        )
        self.identifier = identifier
        self.identifier_type = identifier_type


class InvalidModelVersionTagError(ValueError):
    """The supplied version tag is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Model version tag must be 1-{MODEL_VERSION_TAG_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidModelDeprecationReasonError(ValueError):
    """The supplied deprecation reason is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Model deprecation reason must be 1-{MODEL_DEPRECATION_REASON_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidDeclaredFamiliesError(ValueError):
    """`declared_family_ids` is empty (cardinality at least one required)."""

    def __init__(self) -> None:
        super().__init__(
            "Model.declared_family_ids must contain at least one Family id "
            "(empty set rejected at the catalog tier)"
        )


class ModelAlreadyExistsError(Exception):
    """Attempted to define a model whose stream already has events."""

    def __init__(self, model_id: UUID) -> None:
        super().__init__(f"Model {model_id} already exists")
        self.model_id = model_id


class ModelNotFoundError(Exception):
    """Attempted an operation on a model whose stream has no events."""

    def __init__(self, model_id: UUID) -> None:
        super().__init__(f"Model {model_id} not found")
        self.model_id = model_id


class ModelCannotVersionError(Exception):
    """Attempted to version a model not in `Defined` or `Versioned`.

    Multi-source guard: `version_model` accepts both `Defined` and
    `Versioned`. Only `Deprecated` is rejected.
    """

    def __init__(self, model_id: UUID, current_status: "ModelStatus") -> None:
        super().__init__(
            f"Model {model_id} cannot be versioned: currently in status "
            f"{current_status.value}, version requires "
            f"{ModelStatus.DEFINED.value} or {ModelStatus.VERSIONED.value}"
        )
        self.model_id = model_id
        self.current_status = current_status


class ModelCannotDeprecateError(Exception):
    """Attempted to deprecate a model not in `Defined` or `Versioned`."""

    def __init__(self, model_id: UUID, current_status: "ModelStatus") -> None:
        super().__init__(
            f"Model {model_id} cannot be deprecated: currently in status "
            f"{current_status.value}, deprecate requires "
            f"{ModelStatus.DEFINED.value} or {ModelStatus.VERSIONED.value}"
        )
        self.model_id = model_id
        self.current_status = current_status


class ModelCannotAddFamilyError(Exception):
    """Attempted to add a family to a model not in `Defined` or `Versioned`.

    Mirrors `ModelCannotVersionError` and `ModelCannotDeprecateError`:
    `add_model_family` accepts both `Defined` and `Versioned` source
    states. Only `Deprecated` is rejected; the rejection rationale is
    the same "deprecated catalog entry is frozen" guard that drives
    version and deprecate.
    """

    def __init__(self, model_id: UUID, current_status: "ModelStatus") -> None:
        super().__init__(
            f"Model {model_id} cannot add family: currently in status "
            f"{current_status.value}, add_model_family requires "
            f"{ModelStatus.DEFINED.value} or {ModelStatus.VERSIONED.value}"
        )
        self.model_id = model_id
        self.current_status = current_status


class ModelCannotRemoveFamilyError(Exception):
    """Attempted to remove a family from a model not in `Defined` or `Versioned`.

    Mirrors `ModelCannotAddFamilyError`: `remove_model_family` accepts
    both `Defined` and `Versioned` source states. Only `Deprecated`
    is rejected on the same frozen-catalog-entry rationale.
    """

    def __init__(self, model_id: UUID, current_status: "ModelStatus") -> None:
        super().__init__(
            f"Model {model_id} cannot remove family: currently in status "
            f"{current_status.value}, remove_model_family requires "
            f"{ModelStatus.DEFINED.value} or {ModelStatus.VERSIONED.value}"
        )
        self.model_id = model_id
        self.current_status = current_status


class ModelFamilyAlreadyPresentError(Exception):
    """Attempted to add a family already present in `declared_family_ids`."""

    def __init__(self, model_id: UUID, family_id: UUID) -> None:
        super().__init__(
            f"Model {model_id} already declares family {family_id}; "
            "add_model_family is strict-not-idempotent"
        )
        self.model_id = model_id
        self.family_id = family_id


class ModelFamilyNotPresentError(Exception):
    """Attempted to remove a family not present in `declared_family_ids`."""

    def __init__(self, model_id: UUID, family_id: UUID) -> None:
        super().__init__(f"Model {model_id} does not declare family {family_id}; nothing to remove")
        self.model_id = model_id
        self.family_id = family_id


@bounded_name(max_length=MODEL_NAME_MAX_LENGTH, error_class=InvalidModelNameError)
@dataclass(frozen=True)
class ModelName:
    """Display name for a model. Trimmed; 1-200 chars."""

    value: str


@dataclass(frozen=True)
class PartNumber:
    """Vendor SKU. Trimmed; 1-100 chars; case-sensitive (no folding).

    Vendor part numbers like Newport's `RV120CCHL` and `rv120cchl`
    are distinct entries in vendor catalogs; case-folding would
    collide them.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=MODEL_PART_NUMBER_MAX_LENGTH,
            error_class=InvalidPartNumberError,
        )
        object.__setattr__(self, "value", trimmed)


@bounded_name(max_length=MANUFACTURER_NAME_MAX_LENGTH, error_class=InvalidManufacturerNameError)
@dataclass(frozen=True)
class ManufacturerName:
    """Manufacturer display name. Trimmed; 1-200 chars."""

    value: str


@dataclass(frozen=True)
class ManufacturerIdentifier:
    """Optional manufacturer identifier value. Trimmed; 1-200 chars.

    Opaque string; the scheme lives in `ManufacturerIdentifierType`.
    See [[project-asset-condition-design]] for the orthogonal-axis
    precedent (the scheme is one axis, the identifier value is the
    other; coupled through the `Manufacturer` VO's pairing invariant).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=MANUFACTURER_IDENTIFIER_MAX_LENGTH,
            error_class=InvalidManufacturerIdentifierError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Manufacturer:
    """A model's manufacturer: required name, optional (identifier, type).

    Deviation from Identifier VO: 3-field VO with closed-enum
    identifier_type {ROR, GRID, ISNI} + pairing invariant + name per
    PIDINST 4.2.

    Pairing invariant: `identifier` and `identifier_type` are both set
    or both None. A bare identifier with no scheme cannot be resolved;
    a scheme with no identifier is meaningless. Enforced in
    `__post_init__`; raises `InvalidManufacturerIdentifierPairingError`.
    """

    name: ManufacturerName
    identifier: ManufacturerIdentifier | None = None
    identifier_type: ManufacturerIdentifierType | None = None

    def __post_init__(self) -> None:
        has_id = self.identifier is not None
        has_type = self.identifier_type is not None
        if has_id != has_type:
            raise InvalidManufacturerIdentifierPairingError(
                identifier=self.identifier.value if self.identifier is not None else None,
                identifier_type=self.identifier_type,
            )


@dataclass(frozen=True)
class ModelVersionTag:
    """Operator-supplied revision label. Trimmed; 1-50 chars."""

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=MODEL_VERSION_TAG_MAX_LENGTH,
            error_class=InvalidModelVersionTagError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class ModelDeprecationReason:
    """Operator-supplied deprecation rationale. Trimmed; 1-500 chars."""

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=MODEL_DEPRECATION_REASON_MAX_LENGTH,
            error_class=InvalidModelDeprecationReasonError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Model:
    """Aggregate root: a vendor-catalog entry.

    `version` is the operator-supplied label of the most recent
    `version_model` call (None until first version). State always
    holds the latest tag; past tags live in the event stream as
    `ModelVersioned` events.

    `declared_family_ids` is the frozenset of Family ids the catalog
    entry satisfies. Required non-empty at `define_model` time.
    Mutated incrementally through `add_model_family` /
    `remove_model_family` (targeted-mutation), or wholesale through
    `version_model` (replace-on-version).

    Cross-BC subset invariant `Model.declared_family_ids subset-of
    Asset.family_ids` evaluated by the Asset BC at `register_asset` and
    `add_asset_family`; NOT enforced inside the Model aggregate.
    """

    id: UUID
    name: ModelName
    manufacturer: Manufacturer
    part_number: PartNumber
    declared_family_ids: frozenset[UUID]
    status: ModelStatus = ModelStatus.DEFINED
    version: str | None = None
