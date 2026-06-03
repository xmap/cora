"""Asset aggregate state, value objects, status enums, and domain errors.

`Asset` is the physical equipment instance: a beamline, a detector,
a sample changer, an HPC node. Hierarchical via `parent_id` (forms
a tree, NOT a DAG — single-parent rule per BC map). Carries a
`level` discriminator (Enterprise / Site / Area / Unit / Component /
Device, ISA-88-derived), a `lifecycle` FSM
(Commissioned -> Active -> Maintenance -> Decommissioned), a
`condition` enum (Nominal / Degraded / Faulted, 5g-b: orthogonal to
lifecycle), a `settings` dict (5g-c: slow-changing operational
parameters validated at write time against the union of assigned
Capabilities' settings_schemas), and `ports` (5h: typed connection
points for trigger / encoder / sync / network signals; declarations
of what ports the equipment HAS — Plan.wiring (6h) carries the
actual port-to-port connections).


Minimal Asset: `id` + `name` + `level` + `lifecycle` (defaults
`Commissioned`) + `parent_id: UUID | None`. Lifecycle transitions
cover activate, decommission, and the maintenance cycle.
Hierarchy mutation (`AssetRelocated`) is a sibling slice. Additive
facets — `condition`, `settings`, `ports`, `owner`,
`persistent_id` (PIDINST DOI) — are deferred.

## Hierarchy rule

Per the BC map:
  - `Enterprise` is the root level — `parent_id` MUST be null.
  - All other levels (Site / Area / Unit / Component / Device) MUST
    have a `parent_id`.

Eventual-consistency stance for the parent ref: the decider does
NOT verify the referenced parent Asset exists in the event store.
Same precedent as Trust's Conduit zone refs (3b-pinned). Cycle
detection (target's ancestors must not include this asset) requires
walking the parent chain via additional event-store queries; defer
to projection-worker era. Single-parent tree is enforced
structurally (one `parent_id` field, can't be a list).

**Levels are conventional, not enforced** per the BC map: the
decider does NOT check that a Device's parent is a Component.
`Device`-in-`Device` is allowed when reality demands it (smart
instruments with addressable sub-modules).

## Status as enum-in-state, derived-from-event-type-in-evolver

`AssetLifecycle` is a `StrEnum` so values serialize naturally as
JSON-friendly strings IF carried in an event payload. State holds
the enum (typed); evolver derives lifecycle from event type
(`AssetRegistered → COMMISSIONED`, future `AssetActivated → ACTIVE`).
Same precedent as `SubjectStatus` / `FamilyStatus`.

`AssetLevel` is also a StrEnum but its value DOES travel in event
payloads (level is set at registration and doesn't change — there
are no AssetLevelChanged events). The payload carries the string;
the evolver reconstructs via `AssetLevel(payload["level"])`.

## Seventh bounded-name VO

`AssetName` is the **seventh** trimmed-bounded-name VO. The shared
trim+length-check logic was hoisted to
`cora.infrastructure.bounded_text.validate_bounded_text` once the 10th
VO (PlanName) landed; AssetName now calls that helper while keeping
its own frozen dataclass type and per-aggregate error class.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from cora.equipment.aggregates._drawing import Drawing
from cora.infrastructure.bounded_text import validate_bounded_text

ASSET_NAME_MAX_LENGTH = 200
ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH = 200
ASSET_OWNER_NAME_MAX_LENGTH = 255
ASSET_OWNER_CONTACT_MAX_LENGTH = 255
ASSET_OWNER_IDENTIFIER_MAX_LENGTH = 255
ASSET_OWNER_IDENTIFIER_TYPE_MAX_LENGTH = 64


class AssetLevel(StrEnum):
    """The hierarchical level of an Asset.

    Per the BC map (ISA-88-derived, single-word convention):
      - `Enterprise`: root; the institution itself
      - `Site`: a facility (for example, APS)
      - `Area`: a section of a site (for example, the experimental hall)
      - `Unit`: an operational unit (for example, a beamline)
      - `Component`: a composed sub-system (ISA-88 "Equipment Module" tier)
      - `Device`: an addressable control surface (ISA-88 "Control Module")

    Common pattern is the strict ordering above, but Device-in-Device
    is allowed when reality demands it (smart instruments). Levels
    are conventional, not enforced: the decider does not check that
    a Device's parent is a Component.
    """

    ENTERPRISE = "Enterprise"
    SITE = "Site"
    AREA = "Area"
    UNIT = "Unit"
    COMPONENT = "Component"
    DEVICE = "Device"


class AssetLifecycle(StrEnum):
    """The Asset's lifecycle state.

    Transitions land per-slice:
      - 5c: Commissioned -> Active        (activate_asset)
      - 5c: (Commissioned | Active) -> Decommissioned   (decommission_asset)
      - 5e: Active -> Maintenance         (enter_asset_maintenance)
      - 5e: Maintenance -> Active         (exit_asset_maintenance)
      - 5e (extends 5c): decommission accepts Maintenance as third source

    `Commissioned` is the genesis state set by `register_asset`. The
    enum values are PascalCase strings (matching the BC-map status
    vocabulary) so log lines and DTOs read naturally without
    additional mapping.
    """

    COMMISSIONED = "Commissioned"
    ACTIVE = "Active"
    MAINTENANCE = "Maintenance"
    DECOMMISSIONED = "Decommissioned"


class PortDirection(StrEnum):
    """The direction of an Asset port (5h).

    Two values only: `INPUT` (receives a signal) and `OUTPUT`
    (drives a signal). Bidirectional devices declare TWO ports with
    opposite directions; matches PandABox / EPICS convention. A
    single `BIDIRECTIONAL` value would create ambiguity at wire-up
    time (Plan.wiring needs to know which side is the source).
    """

    INPUT = "Input"
    OUTPUT = "Output"


PORT_NAME_MAX_LENGTH = 100
PORT_SIGNAL_TYPE_MAX_LENGTH = 50


class InvalidAssetPortNameError(ValueError):
    """The supplied port name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Asset port name must be 1-{PORT_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidAssetPortSignalTypeError(ValueError):
    """The supplied port signal_type is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Asset port signal_type must be 1-{PORT_SIGNAL_TYPE_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class AssetPort:
    """A typed connection point exposed by an Asset (5h).

    Tuple `(name, direction, signal_type)` describes one port. The
    Asset declares what ports it HAS via `add_asset_port` /
    `remove_asset_port`; the connection between two ports (which
    port wires to which) lives in `Plan.wiring` (6h), not here.

    `name` is operator-supplied within the Asset's scope (for example,
    `"trigger_in"`, `"encoder_a"`, `"sync_clock"`). Trimmed and
    bounded 1-100 chars. Asset-wide name uniqueness is enforced by
    the `add_asset_port` decider, NOT by this dataclass.

    `signal_type` is operator-supplied free text 1-50 chars
    (`"TTL"`, `"LVDS"`, `"Encoder"`, `"Network"`, `"Sync"`, etc.).
    Free-form intentionally; promote to a closed StrEnum once the
    pilot vocabulary settles (see project_asset_ports_design memo).
    """

    name: str
    direction: PortDirection
    signal_type: str

    def __post_init__(self) -> None:
        trimmed_name = self.name.strip()
        if not trimmed_name or len(trimmed_name) > PORT_NAME_MAX_LENGTH:
            raise InvalidAssetPortNameError(self.name)
        trimmed_signal = self.signal_type.strip()
        if not trimmed_signal or len(trimmed_signal) > PORT_SIGNAL_TYPE_MAX_LENGTH:
            raise InvalidAssetPortSignalTypeError(self.signal_type)
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install trimmed values.
        object.__setattr__(self, "name", trimmed_name)
        object.__setattr__(self, "signal_type", trimmed_signal)


class AlternateIdentifierKind(StrEnum):
    """Closed vocabulary for an Asset's alternate-identifier kind.

    Values are verbatim from PIDINST v1.0 spec page 8 (Table 1)
    Property 13 `alternateIdentifierType` controlled vocabulary:
    SerialNumber, InventoryNumber, Other. Operationally:

      - `SerialNumber` is the manufacturer's per-unit identifier
        (the value engraved on the chassis or printed on the QR
        sticker; for example, an Aerotech ANT130-L's `12345-ABC`).
      - `InventoryNumber` is the facility-issued asset tag (for
        example, an APS-issued `APS-2BM-CAM-001`).
      - `Other` is the catch-all for vendor-specific or
        unconventional identifier schemes that don't fit the prior
        two; resolution is operator-supplied free text in the
        `value` field.

    Adding a fourth member is an additive enum change at a future
    migration boundary. The closed-enum stance mirrors
    `ManufacturerIdentifierType` (Model BC) and the broader
    [[project-family-affordance-design]] closed-vocabulary
    precedent. See [[project-asset-alternate-identifiers-design]]
    Lock B for the design rationale.
    """

    SERIAL_NUMBER = "SerialNumber"
    INVENTORY_NUMBER = "InventoryNumber"
    OTHER = "Other"


class InvalidAlternateIdentifierValueError(ValueError):
    """The supplied alternate-identifier value is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Alternate identifier value must be 1-{ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class AlternateIdentifier:
    """A flat (kind, value) tuple identifying an Asset under an alternate scheme.

    PIDINST v1.0 Property 13: instance-tier alternate identifiers
    distinct from the PID-tier persistent identifier. Examples:

      - `(SerialNumber, "12345-ABC")` for a manufacturer's serial
      - `(InventoryNumber, "APS-2BM-CAM-001")` for a facility asset tag
      - `(Other, "RIC-99")` for a legacy or vendor-specific scheme

    `value` is trimmed and length-bounded 1-200 chars via the shared
    `validate_bounded_text` helper, matching the
    `ManufacturerIdentifier` precedent in the Model BC. The VO is
    FLAT (kind + value); no scheme URIs, namespaces, or labels per
    [[project-asset-alternate-identifiers-design]] Lock C. Pairing
    uniqueness across Assets is NOT enforced in v1 (Lock F).
    """

    kind: AlternateIdentifierKind
    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH,
            error_class=InvalidAlternateIdentifierValueError,
        )
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


class AssetAlternateIdentifierAlreadyPresentError(Exception):
    """Attempted to add an AlternateIdentifier already in the asset's set.

    Strict-not-idempotent: same precedent as
    `AssetCannotAddPortError` and `ModelFamilyAlreadyPresentError`.
    The full `AlternateIdentifier` VO (kind + value) is carried for
    diagnostics; uniqueness is keyed on the (kind, value) tuple at
    the Asset scope ONLY (per
    [[project-asset-alternate-identifiers-design]] Lock F, no
    cross-Asset uniqueness in v1).
    """

    def __init__(self, asset_id: UUID, identifier: AlternateIdentifier) -> None:
        super().__init__(
            f"Asset {asset_id} already has alternate identifier "
            f"{identifier.kind.value}={identifier.value!r}; "
            "add_asset_alternate_identifier is strict-not-idempotent"
        )
        self.asset_id = asset_id
        self.identifier = identifier


class AssetAlternateIdentifierNotPresentError(Exception):
    """Attempted to remove an AlternateIdentifier not in the asset's set.

    Mirror of `AssetAlternateIdentifierAlreadyPresentError`.
    Strict-not-idempotent: the decider rejects rather than no-ops on
    a missing identifier. Same shape as `AssetCannotRemovePortError`
    and `ModelFamilyNotPresentError`.
    """

    def __init__(self, asset_id: UUID, identifier: AlternateIdentifier) -> None:
        super().__init__(
            f"Asset {asset_id} does not have alternate identifier "
            f"{identifier.kind.value}={identifier.value!r}; nothing to remove"
        )
        self.asset_id = asset_id
        self.identifier = identifier


class AssetCannotAddAlternateIdentifierError(Exception):
    """Attempted to add / remove an AlternateIdentifier under a disqualifying lifecycle.

    Used by BOTH `add_asset_alternate_identifier` and
    `remove_asset_alternate_identifier` deciders: the lifecycle guard
    (asset is `Decommissioned`) is symmetric across the add and
    remove transitions; mirrors `AssetCannotAddPortError`'s
    reason-bearing pattern. Operationally: a Decommissioned asset is
    out of inventory and identifier changes are not permitted.
    """

    def __init__(
        self,
        asset_id: UUID,
        kind: AlternateIdentifierKind,
        value: str,
        *,
        reason: str,
    ) -> None:
        super().__init__(
            f"Asset {asset_id} cannot mutate alternate identifier {kind.value}={value!r}: {reason}"
        )
        self.asset_id = asset_id
        self.kind = kind
        self.value = value
        self.reason = reason


class InvalidAssetOwnerNameError(ValueError):
    """The supplied owner name is empty, whitespace-only, or too long.

    PIDINST v1.0 Property 5.1 `ownerName` is MANDATORY free text. The
    aggregate enforces non-empty + length-cap; semantic validation
    (registry name match, casing) is operator-side.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Asset owner name must be 1-{ASSET_OWNER_NAME_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidAssetOwnerContactError(ValueError):
    """The supplied owner contact is empty, whitespace-only, or too long.

    PIDINST v1.0 Property 5.2 `ownerContact` is optional free text;
    spec hints at email but does not enforce a format. Shape-only
    validation at this layer; email-format checks live at the route
    layer (Pydantic `EmailStr`) if a future deployment opts in.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Asset owner contact must be 1-{ASSET_OWNER_CONTACT_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidAssetOwnerIdentifierError(ValueError):
    """The supplied owner identifier is empty, whitespace-only, or too long.

    PIDINST v1.0 Property 5.3 `ownerIdentifier` is opaque free text;
    the spec recommends ROR but accepts any globally unique string.
    Both bare codes (for example `02aj13c28`) and full URLs (for example
    `https://ror.org/02aj13c28`) round-trip as-is; no normalization at
    this layer.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Asset owner identifier must be 1-{ASSET_OWNER_IDENTIFIER_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidAssetOwnerIdentifierTypeError(ValueError):
    """The supplied owner identifier_type is empty, whitespace-only, or too long.

    PIDINST v1.0 Property 5.3.1 `ownerIdentifierType` is **free text**
    by spec design (unlike sibling fields `relatedIdentifierType`,
    `alternateIdentifierType`, `dateType`, which use closed vocabularies).
    CORA honors the spec posture: shape-only validation, no closed
    enum. ROR is documented as the recommended scheme in operator docs
    but never enforced at this layer.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Asset owner identifier_type must be "
            f"1-{ASSET_OWNER_IDENTIFIER_TYPE_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class AssetOwnerName:
    """Owner display name. Trimmed; 1-255 chars."""

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=ASSET_OWNER_NAME_MAX_LENGTH,
            error_class=InvalidAssetOwnerNameError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class AssetOwnerContact:
    """Owner contact string (typically email). Trimmed; 1-255 chars when present."""

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=ASSET_OWNER_CONTACT_MAX_LENGTH,
            error_class=InvalidAssetOwnerContactError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class AssetOwnerIdentifier:
    """Opaque owner identifier value (typically a ROR URL or bare code). Trimmed; 1-255 chars."""

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=ASSET_OWNER_IDENTIFIER_MAX_LENGTH,
            error_class=InvalidAssetOwnerIdentifierError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class AssetOwnerIdentifierType:
    """Owner identifier scheme label (free text). Trimmed; 1-64 chars.

    Deliberately NOT a closed StrEnum (unlike
    `ManufacturerIdentifierType`): PIDINST v1.0 Property 5.3.1 is the
    one identifier-type field the spec leaves open. ROR is the
    recommended scheme but the field accepts arbitrary
    organization-identifier authorities (RAID, IGSN-for-orgs, internal
    facility codes).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=ASSET_OWNER_IDENTIFIER_TYPE_MAX_LENGTH,
            error_class=InvalidAssetOwnerIdentifierTypeError,
        )
        object.__setattr__(self, "value", trimmed)


class InvalidAssetOwnerIdentifierPairingError(ValueError):
    """Owner identifier and identifier_type must be both-set or both-None.

    PIDINST v1.0 Property 5.3.1 only exists when 5.3 is provided; a
    bare identifier with no scheme cannot be resolved, a scheme with
    no identifier is meaningless. Same shape as Model's
    `InvalidManufacturerIdentifierPairingError`; per-BC, not hoisted.
    """

    def __init__(
        self,
        *,
        name: "AssetOwnerName",
        identifier: "AssetOwnerIdentifier | None",
        identifier_type: "AssetOwnerIdentifierType | None",
    ) -> None:
        super().__init__(
            f"Asset owner {name.value!r}: identifier and identifier_type must be "
            f"both set or both None (got identifier="
            f"{identifier.value if identifier is not None else None!r}, "
            f"identifier_type="
            f"{identifier_type.value if identifier_type is not None else None!r})"
        )
        self.name = name
        self.identifier = identifier
        self.identifier_type = identifier_type


@dataclass(frozen=True)
class AssetOwner:
    """A body owning or curating the Asset (PIDINST v1.0 Property 5).

    `name` is mandatory (5.1). `contact` is optional (5.2; free text,
    spec hints at email). `identifier` (5.3) and `identifier_type`
    (5.3.1) are independently optional but jointly constrained: both
    set or both None. The pairing invariant raises
    `InvalidAssetOwnerIdentifierPairingError` from `__post_init__`.

    Uniqueness within one Asset's `owners` frozenset is keyed on
    `name` and enforced at the decider, not at the VO; this lets
    operators record genuine same-name distinct contacts only after
    they disambiguate the names (see Defer-5 in the design memo).
    """

    name: AssetOwnerName
    contact: AssetOwnerContact | None = None
    identifier: AssetOwnerIdentifier | None = None
    identifier_type: AssetOwnerIdentifierType | None = None

    def __post_init__(self) -> None:
        has_id = self.identifier is not None
        has_type = self.identifier_type is not None
        if has_id != has_type:
            raise InvalidAssetOwnerIdentifierPairingError(
                name=self.name,
                identifier=self.identifier,
                identifier_type=self.identifier_type,
            )


class AssetOwnerAlreadyPresentError(Exception):
    """Attempted to add an AssetOwner whose name is already on the asset.

    Strict-not-idempotent: same precedent as
    `AssetAlternateIdentifierAlreadyPresentError`. Owner uniqueness
    is keyed on `name` per Lock 5 of the design memo; two owners
    sharing a name on the same Asset are forbidden in v1.
    """

    def __init__(self, asset_id: UUID, name: "AssetOwnerName") -> None:
        super().__init__(
            f"Asset {asset_id} already has owner with name {name.value!r}; "
            "owner names are unique within a single Asset"
        )
        self.asset_id = asset_id
        self.name = name


class AssetOwnerNotPresentError(Exception):
    """Attempted to remove an AssetOwner whose name is not on the asset.

    Mirror of `AssetOwnerAlreadyPresentError`. Strict-not-idempotent:
    removing an unknown owner_name rejects rather than no-ops, so a
    typo cannot mask a missing-owner audit gap.
    """

    def __init__(self, asset_id: UUID, name: "AssetOwnerName") -> None:
        super().__init__(
            f"Asset {asset_id} does not have owner with name {name.value!r}; nothing to remove"
        )
        self.asset_id = asset_id
        self.name = name


class AssetCannotAddOwnerError(Exception):
    """Attempted to add / remove an AssetOwner under a disqualifying lifecycle.

    Used by BOTH `add_asset_owner` and `remove_asset_owner` deciders:
    the lifecycle guard (asset is `Decommissioned`) is symmetric across
    the add and remove transitions; mirrors
    `AssetCannotAddAlternateIdentifierError`'s reason-bearing pattern.
    A Decommissioned asset is out of inventory; owner-data curation
    after retirement would drift unobserved.
    """

    def __init__(
        self,
        asset_id: UUID,
        name: "AssetOwnerName",
        *,
        reason: str,
    ) -> None:
        super().__init__(f"Asset {asset_id} cannot mutate owner {name.value!r}: {reason}")
        self.asset_id = asset_id
        self.name = name
        self.reason = reason


class AssetCondition(StrEnum):
    """The Asset's real-time device-health state.

    Orthogonal to lifecycle: lifecycle answers "is this device part
    of inventory and assignable", condition answers "is it actually
    working right now". An Active asset can be Faulted (broken but
    still owned); a Decommissioned asset can be discovered Faulted on
    inventory check (honest about device-state-in-storage).

    Transitions land per-slice (5g-b), each moves to a fixed target
    from any source:
      - degrade_asset            -> Degraded
      - fault_asset              -> Faulted
      - restore_asset            -> Nominal

    `Nominal` is the default at registration time (no synthetic
    initialization event; default-via-state). Pattern matches PI-System
    asset-health attributes (Good / Warning / Bad) and SEMI E10's
    productive vs unproductive time orthogonality.
    """

    NOMINAL = "Nominal"
    DEGRADED = "Degraded"
    FAULTED = "Faulted"


class InvalidAssetNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Asset name must be 1-{ASSET_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidAssetSettingsError(ValueError):
    """The proposed Asset.settings dict failed cross-Family validation.

    Three failure modes (5g-c):
      1. A key in the proposed settings is not declared by any
         currently-assigned Family's settings_schema (orphan key
         on a fully-schema-covered Asset).
      2. A value violates the schema constraints declared for its
         key by one or more assigned Capabilities (intersection via
         `allOf` semantics; the most restrictive wins).
      3. Two or more assigned Capabilities declare the same key with
         incompatible types (true conflict; no value satisfies both).

    Mapped to HTTP 400 by the equipment BC's exception handler. The
    `reason` string identifies the offending key(s) and, where
    applicable, the conflicting Family ids.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Asset settings: {reason}")
        self.reason = reason


class InvalidAssetParentError(ValueError):
    """The hierarchy rule was violated.

    Two failure modes:
      - Enterprise-level Asset supplied a non-null `parent_id`
        (Enterprise is the root; cannot have a parent)
      - Non-Enterprise-level Asset supplied a null `parent_id`
        (Site / Area / Unit / Component / Device must have a parent)

    Eventual-consistency stance: this decider rule does NOT check
    that the referenced parent Asset exists. Cycle detection
    (target's ancestors must not include this asset) is a separate
    deferred concern (requires walking the parent chain via the
    event store; revisit when projection-worker exists).
    """


class AssetAlreadyExistsError(Exception):
    """Attempted to register an asset whose stream already has events."""

    def __init__(self, asset_id: UUID) -> None:
        super().__init__(f"Asset {asset_id} already exists")
        self.asset_id = asset_id


class AssetNotFoundError(Exception):
    """Attempted an operation on an asset whose stream has no events."""

    def __init__(self, asset_id: UUID) -> None:
        super().__init__(f"Asset {asset_id} not found")
        self.asset_id = asset_id


class AssetCannotActivateError(Exception):
    """Attempted to activate an asset not in the `Commissioned` lifecycle.

    Strict semantics: re-activating an already-`Active` asset also
    raises (rather than no-op or always-emit). Per-transition error
    class — same naming convention as `SubjectCannot<X>Error`. The
    current lifecycle is carried as `current_lifecycle` for
    diagnostics; the error message lists both the current and the
    expected source state.
    """

    def __init__(self, asset_id: UUID, current_lifecycle: "AssetLifecycle") -> None:
        super().__init__(
            f"Asset {asset_id} cannot be activated: currently in lifecycle "
            f"{current_lifecycle.value}, activate requires "
            f"{AssetLifecycle.COMMISSIONED.value}"
        )
        self.asset_id = asset_id
        self.current_lifecycle = current_lifecycle


class AssetCannotDecommissionError(Exception):
    """Attempted to decommission an asset not in `Commissioned`, `Active`, or `Maintenance`.

    Multi-source guard: `decommission` accepts `Commissioned` (asset
    never went into service — operator changed mind), `Active` (asset
    retired from service), and `Maintenance` (asset retired during a
    maintenance window). The decider's `_DECOMMISSIONABLE_LIFECYCLES`
    tuple is the single edit point that controls the allowed source
    set; the error message lists currently-allowed source states for
    diagnostic clarity. Mirrors Subject's `SubjectCannotRemoveError`
    pattern.
    """

    def __init__(self, asset_id: UUID, current_lifecycle: "AssetLifecycle") -> None:
        super().__init__(
            f"Asset {asset_id} cannot be decommissioned: currently in lifecycle "
            f"{current_lifecycle.value}, decommission requires "
            f"{AssetLifecycle.COMMISSIONED.value}, {AssetLifecycle.ACTIVE.value}, "
            f"or {AssetLifecycle.MAINTENANCE.value}"
        )
        self.asset_id = asset_id
        self.current_lifecycle = current_lifecycle


class AssetCannotEnterMaintenanceError(Exception):
    """Attempted to enter maintenance on an asset not in `Active`.

    Strict semantics: re-entering maintenance on an already-`Maintenance`
    asset also raises (rather than no-op). Industrial convention: only
    in-service (Active) assets enter maintenance; Commissioned assets
    are still pre-service, Decommissioned ones are retired. Per-transition
    error class — same naming convention as `SubjectCannot<X>Error` and
    `AssetCannotActivateError`.
    """

    def __init__(self, asset_id: UUID, current_lifecycle: "AssetLifecycle") -> None:
        super().__init__(
            f"Asset {asset_id} cannot enter maintenance: currently in lifecycle "
            f"{current_lifecycle.value}, enter_asset_maintenance requires "
            f"{AssetLifecycle.ACTIVE.value}"
        )
        self.asset_id = asset_id
        self.current_lifecycle = current_lifecycle


class AssetCannotExitMaintenanceError(Exception):
    """Attempted to exit-maintenance on an asset not in `Maintenance`.

    Strict semantics: exiting maintenance on an already-`Active` asset
    also raises (the maintenance window has already ended). Mirrors
    AssetCannotEnterMaintenanceError. Single-source guard like activate.
    """

    def __init__(self, asset_id: UUID, current_lifecycle: "AssetLifecycle") -> None:
        super().__init__(
            f"Asset {asset_id} cannot exit maintenance: currently in lifecycle "
            f"{current_lifecycle.value}, exit_asset_maintenance requires "
            f"{AssetLifecycle.MAINTENANCE.value}"
        )
        self.asset_id = asset_id
        self.current_lifecycle = current_lifecycle


class AssetCannotAddFamilyError(Exception):
    """Attempted to add a Family to an asset under disqualifying conditions.

    Family mutation (5f-1): like relocate, has multiple
    disqualifying conditions that don't share a single state-mismatch
    shape. They collapse into one error class with a diagnostic
    `reason` string that surfaces in the route's 409 body:

      - asset is `Decommissioned` (retired; no further family changes)
      - family already in `asset.family_ids` (strict-not-idempotent;
        same precedent as activate / mount-second-call-raises)

    Eventual-consistency: the decider does NOT verify the referenced
    Family id refers to a real Family stream. Same precedent
    as Trust Conduit zone refs (3b) and Method.needed_family_ids
    (6a).
    """

    def __init__(self, asset_id: UUID, family_id: UUID, reason: str) -> None:
        super().__init__(f"Asset {asset_id} cannot add family {family_id}: {reason}")
        self.asset_id = asset_id
        self.family_id = family_id
        self.reason = reason


class AssetCannotRemoveFamilyError(Exception):
    """Attempted to remove a Family from an asset under disqualifying conditions.

    Mirrors `AssetCannotAddFamilyError`. Disqualifying conditions:

      - asset is `Decommissioned` (retired)
      - family not in `asset.family_ids` (strict-not-idempotent)
    """

    def __init__(self, asset_id: UUID, family_id: UUID, reason: str) -> None:
        super().__init__(f"Asset {asset_id} cannot remove family {family_id}: {reason}")
        self.asset_id = asset_id
        self.family_id = family_id
        self.reason = reason


class AssetCannotAddPortError(Exception):
    """Attempted to add a port to an Asset under disqualifying conditions (5h).

    Two failure modes:
      - asset is `Decommissioned` (retired; no further port changes)
      - port name is already in `asset.ports` (strict-not-idempotent;
        same convention as Family mutation)

    Mirrors `AssetCannotAddFamilyError`. The `port_name` is
    surfaced as a separate field for diagnostics; the `reason`
    string is what the route's 409 body shows.
    """

    def __init__(self, asset_id: UUID, port_name: str, reason: str) -> None:
        super().__init__(f"Asset {asset_id} cannot add port {port_name!r}: {reason}")
        self.asset_id = asset_id
        self.port_name = port_name
        self.reason = reason


class AssetCannotRemovePortError(Exception):
    """Attempted to remove a port from an Asset under disqualifying conditions (5h).

    Two failure modes:
      - asset is `Decommissioned` (retired)
      - no port with the given name in `asset.ports` (strict-not-
        idempotent; symmetric with `AssetCannotAddPortError`)
    """

    def __init__(self, asset_id: UUID, port_name: str, reason: str) -> None:
        super().__init__(f"Asset {asset_id} cannot remove port {port_name!r}: {reason}")
        self.asset_id = asset_id
        self.port_name = port_name
        self.reason = reason


class AssetModelMismatchError(Exception):
    """The Asset's families set does not satisfy the bound Model's declared families.

    Cross-BC subset invariant: when an Asset is bound to a Model via
    `model_id`, the Asset's `family_ids` must be a superset of the
    Model's `declared_family_ids`. The check fires at `add_asset_family`
    against a freshly loaded Model snapshot; if the post-add families
    set is not a superset of `declared_family_ids`, this error is raised
    and no event is emitted.

    The message lists both sets verbatim so operators reading the API
    error response see immediately which Families are missing on the
    Asset (or, in the cascade case, which Families the Model has added
    since the binding). Mapped to HTTP 409 via the
    `cannot_transition_cls` tuple in `routes.py`.

    Per the model-binding design memo (Lock E), this class lives in
    the Asset BC per the per-BC error-class convention; the Model-side
    equivalent does not exist because the binding is one-directional.
    """

    def __init__(
        self,
        asset_id: UUID,
        model_id: UUID,
        declared_family_ids: frozenset[UUID],
        asset_family_ids: frozenset[UUID],
    ) -> None:
        super().__init__(
            f"Asset {asset_id} bound to Model {model_id} which declares families "
            f"{sorted(declared_family_ids)}, but Asset families would be "
            f"{sorted(asset_family_ids)} after this transition"
        )
        self.asset_id = asset_id
        self.model_id = model_id
        self.declared_family_ids = declared_family_ids
        self.asset_family_ids = asset_family_ids


class AssetCannotRelocateError(Exception):
    """Attempted to relocate an asset under disqualifying conditions.

    Hierarchy mutation (5d): unlike the lifecycle-transition errors
    (Activate/Decommission), relocation has multiple disqualifying
    conditions that don't share a single state-mismatch shape. They
    all collapse into one error class with a diagnostic `reason`
    string that surfaces in the route's 409 body:

      - asset is `Enterprise` level (root; cannot have a parent at all)
      - asset is `Decommissioned` (retired; no further hierarchy changes)
      - target_parent_id == asset_id (single-parent-tree self-loop)
      - target_parent_id == current parent_id (no-op)

    Cycle detection beyond the trivial self-loop case (target's
    ancestor chain contains the asset) is **deferred** — requires
    walking the parent chain via additional event-store queries;
    revisit when projection-worker exists. Documented as a known
    gap.
    """

    def __init__(self, asset_id: UUID, reason: str) -> None:
        super().__init__(f"Asset {asset_id} cannot be relocated: {reason}")
        self.asset_id = asset_id
        self.reason = reason


@dataclass(frozen=True)
class AssetName:
    """Display name for an asset. Trimmed; 1-200 chars.

    Seventh occurrence of the trimmed-bounded-name VO pattern. Uses
    the shared `validate_bounded_text` helper (see
    `cora.infrastructure.bounded_text`).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=ASSET_NAME_MAX_LENGTH,
            error_class=InvalidAssetNameError,
        )
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Asset:
    """Aggregate root: a physical equipment instance.

    `parent_id` is the immediate parent in the hierarchy tree.
    `None` only when `level == Enterprise` (root). Mutable across
    `AssetRelocated` events.

    `family_ids` is the set of Family ids this asset belongs to.
    Operationally curated: operators add via `add_asset_family` when
    commissioning a new device-class on the asset, remove via
    `remove_asset_family` when retiring one. Used at Plan binding
    time (6e) for the structural check
    `asset.family_ids ⊇ method.needed_family_ids`. Eventual-
    consistency: each Family id is NOT verified against the
    Family stream at decide time. Defaults to empty so prior
    `AssetRegistered`-only streams fold cleanly without an upcaster
    (the additive-state pattern; see CONTRIBUTING.md).

    `condition`: real-time device health, orthogonal to
    lifecycle. Defaults to `AssetCondition.NOMINAL` at registration
    (no synthetic initialization event); transitions land via the
    degrade / fault / restore slices. Older AssetRegistered-only
    streams without a condition field fold cleanly with the default
    (additive-state pattern).

    `settings`: slow-changing operational parameters
    (gap, energy, exposure, filter_material, etc.; units live in
    each Family's settings_schema as a `unit` annotation).
    Validated at write time against the union of currently-assigned
    Capabilities' `settings_schema` declarations. Updated via
    the `update_asset_settings` slice with PATCH RFC 7396 merge
    semantics. Defaults to empty dict; legacy streams without
    settings fold cleanly via the additive-state pattern.

    `ports`: typed connection points the Asset exposes
    (trigger_in, encoder_a, sync_clock, etc.). Each AssetPort is a
    name + direction + signal_type tuple. Updated incrementally via
    `add_asset_port` / `remove_asset_port` slices (mirrors the
    Family-mutation precedent). Defaults to empty frozenset;
    legacy streams without ports fold cleanly via the additive-state
    pattern. Plan.wiring will reference these by name to declare
    port-to-port connections.

    `drawing`: optional reference to the engineering document that
    defines the build-to specification for this physical specimen
    (ICMS drawing number, EDMS link, DOI). Distinct from
    Mount.drawing, which references the slot's drawing (an assembly
    location, not the specimen's build). Defaults to None; legacy
    AssetRegistered streams without the drawing field fold cleanly
    via the additive-state pattern.

    `model_id`: optional reference to the Model catalog entry this
    Asset is an instance of (Family -> Model -> Assembly -> Asset
    ladder). Set ONCE at `register_asset` time per the model-binding
    design memo (Lock A); rebind path is decommission + re-register.
    Carries the cross-BC subset invariant
    `Model.declared_family_ids ⊆ Asset.family_ids`, enforced at
    `add_asset_family` against a freshly loaded Model snapshot.
    Defaults to None; legacy AssetRegistered streams without the
    model_id field fold cleanly via the additive-state pattern.

    `alternate_identifiers`: frozenset of PIDINST v1.0 Property 13
    alternate identifiers (serial numbers, inventory tags, vendor-
    specific schemes). Each entry is a flat `AlternateIdentifier`
    VO (kind + value). Updated incrementally via
    `add_asset_alternate_identifier` /
    `remove_asset_alternate_identifier` slices; the optional
    `alternate_identifiers` parameter at `register_asset` time
    seeds the initial set. Defaults to empty frozenset; legacy
    AssetRegistered streams without the field fold cleanly via the
    additive-state pattern. See
    [[project-asset-alternate-identifiers-design]] Locks A, D, E.

    `owners`: frozenset of PIDINST v1.0 Property 5 owner blocks
    (institutional bodies owning or curating the Asset). Each entry is
    an `AssetOwner` VO (name + optional contact + optional paired
    identifier+identifier_type). Updated incrementally via
    `add_asset_owner` / `remove_asset_owner` slices; the optional
    `owners` parameter at `register_asset` time seeds the initial set.
    Aggregate allows 0-n owners; PIDINST 1-n MANDATORY cardinality is
    a serializer-time gate, not an aggregate-time invariant. Defaults
    to empty frozenset; legacy AssetRegistered streams without the
    field fold cleanly via the additive-state pattern.

    Future additive facet: `persistent_id` (PIDINST DOI). The state-
    level field lands with a default for the same forward-
    compatibility reason.
    """

    id: UUID
    name: AssetName
    level: AssetLevel
    parent_id: UUID | None
    lifecycle: AssetLifecycle = AssetLifecycle.COMMISSIONED
    condition: AssetCondition = AssetCondition.NOMINAL
    # frozenset[UUID] generic-callable trick (PEP 585): plain
    # `frozenset` as default_factory triggers reportUnknownVariableType
    # under pyright strict because the empty frozenset has no element
    # type to infer. The parametrized form gives pyright the type
    # without runtime cost. Same trick used in Method.needed_family_ids.
    family_ids: frozenset[UUID] = field(default_factory=frozenset[UUID])
    # dict[str, Any] for runtime-typed operator-supplied settings.
    # Same default_factory pattern as family_ids — the empty dict
    # has no element types for pyright to infer, so the parametrized
    # `dict[str, Any]` callable is supplied as the factory.
    settings: dict[str, Any] = field(default_factory=dict[str, Any])
    # frozenset[AssetPort] for typed connection points (5h).
    # Same parametrized-callable trick as family_ids.
    ports: frozenset[AssetPort] = field(default_factory=frozenset[AssetPort])
    drawing: Drawing | None = None
    model_id: UUID | None = None
    # frozenset[AlternateIdentifier] for PIDINST v1.0 Property 13
    # alternate-identifier tuples. Same parametrized-callable trick
    # as family_ids / ports — empty frozenset has no element type for
    # pyright to infer under strict, so the parametrized callable is
    # supplied as the factory.
    alternate_identifiers: frozenset[AlternateIdentifier] = field(
        default_factory=frozenset[AlternateIdentifier]
    )
    # frozenset[AssetOwner] for PIDINST v1.0 Property 5 owner blocks.
    # Same parametrized-callable trick as family_ids / ports /
    # alternate_identifiers; the empty frozenset has no element type
    # for pyright to infer under strict.
    owners: frozenset[AssetOwner] = field(default_factory=frozenset[AssetOwner])
