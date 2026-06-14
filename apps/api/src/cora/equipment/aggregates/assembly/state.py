"""Assembly aggregate state, value objects, status enum, and domain errors.

An `Assembly` is a content-addressed composition blueprint for a
reusable cluster of Assets (e.g., the Microscope fixture at APS 2-BM:
an Optics sub-assembly + camera + scintillator, wired together).
Declares `required_slots` (Family-typed, cardinality-annotated,
optionally pre-Placed), `required_wires` (slot-keyed 4-tuples), and
`required_sub_assemblies` (version-pinned links to child Assemblies,
so a blueprint can be composed of smaller reusable blueprints, not
only of individual parts). Exposes a stable `presents_as_family_id`
so other aggregates
(Method.needed_families, Capability bindings) can treat an
instantiated Assembly as one typed unit at the same level as a
single Asset.

See `project_assembly_aggregate_design` for the locked design memo.

## Identity

`id` is the opaque UUID (CORA's standard internal id) used for
event-store stream keying. `name` is a human-readable AssemblyName
(non-unique). `content_hash` is the structural fingerprint
(SHA-256 hex over the canonical subset
`{name, presents_as_family_id, required_slots, required_wires,
required_sub_assemblies, parameter_overrides_schema}`); two operators
independently authoring the same Assembly converge on the same hash.
Each `required_sub_assemblies` link carries the child's content_hash,
so the parent fingerprint chains: a change deep in the tree ripples
upward one deliberate re-version at a time.

## Slot keying

`required_slots: frozenset[TemplateSlot]` and `required_wires:
frozenset[TemplateWire]` BOTH key by `slot_name` (string), NOT by
Asset UUID. Reason: an Assembly is a template; the Assets it
references do not exist at template-definition time. Slot-to-asset
translation happens at `register_fixture` time.
Plan.wires, by contrast, has concrete Asset.ports and so enforces
direction + signal-type + fan-in at write time; an Assembly cannot,
because the ports do not exist yet (see the wire-conformance note
below).

## Internal closure

`Assembly.__post_init__` enforces that every `TemplateWire`'s
endpoints reference a slot present in `required_slots`. That is the
only wire check the spine performs.

## Wire conformance is not checked at materialization (yet)

`register_fixture` expands slots and binds Assets, but it does NOT
validate wires: direction (OUTPUT -> INPUT), signal-type match, and
fan-in are checked NOWHERE today, neither at define / version nor at
register_fixture. A `required_wire` is therefore a declared intent,
closure-checked against slot names only. Per-port conformance against
the materialized Asset.ports is a deferred read-side projection (the
`AssemblyConformanceMismatch` posture, not yet built), the same
eventual-consistency stance Asset.parent_id and Method.needed_family_ids
take. Whole-experiment routing that must be enforced lives in
`Plan.wiring`, keyed by concrete Asset UUIDs.

## Revision lineage

`status` is the AssemblyStatus FSM (Defined / Versioned /
Deprecated). `version` is an operator-curated free-form label
(no SemVer enforcement). Multiple AssemblyVersioned events on the
same stream are permitted; each writes a fresh content_hash
snapshot. Mirrors CalibrationRevision's append-only revisions.

## Drawing

`drawing` is the optional engineering reference for the assembly
itself (ICMS or DOI). Excluded from the content_hash canonical
subset because it is operator-curatorial metadata, not structural
identity: two Assemblies with identical structure but different
drawings collide on content_hash, which is the intended semantic.

## Bounded VOs

`AssemblyName` is trimmed 1-200 chars (matches Family/Mount).
`SlotName` is trimmed 1-100 chars (matches Wire port-name bound).
Both raise dedicated InvalidXError classes on violation.
"""

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from cora.equipment.aggregates._drawing import Drawing
from cora.equipment.aggregates._placement import Placement
from cora.equipment.aggregates._value_types import RoleId
from cora.shared.bounded_text import bounded_name

ASSEMBLY_NAME_MAX_LENGTH = 200
SLOT_NAME_MAX_LENGTH = 100
WIRE_PORT_NAME_MAX_LENGTH = 100


class AssemblyStatus(StrEnum):
    """The Assembly's lifecycle state.

    Template-shaped FSM matching CalibrationRevision and the six
    template aggregates per project_template_aggregate_timestamps.
    """

    DEFINED = "Defined"
    VERSIONED = "Versioned"
    DEPRECATED = "Deprecated"


class SlotCardinality(StrEnum):
    """How many Assets can fill a slot at instantiation time.

    Closed enum: adding a fifth member is a deliberate widen, not
    an additive default. Numeric bounds (`AtLeast2`, `AtMost3`) are
    explicitly out of scope to keep the closed-enum discipline.
    """

    EXACTLY_1 = "Exactly1"
    ZERO_OR_ONE = "ZeroOrOne"
    ONE_OR_MORE = "OneOrMore"
    ZERO_OR_MORE = "ZeroOrMore"


class InvalidAssemblyNameError(ValueError):
    """The supplied Assembly name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Assembly name must be 1-{ASSEMBLY_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidSlotNameError(ValueError):
    """The supplied slot name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"TemplateSlot slot_name must be 1-{SLOT_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidSlotCardinalityError(ValueError):
    """The supplied cardinality is not a SlotCardinality member.

    Closed enum violation; mapped to HTTP 400 by the BC exception
    handler. The boundary Pydantic layer rejects 422 before this
    fires; the domain error exists for in-code constructors.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"TemplateSlot cardinality must be one of "
            f"{[c.value for c in SlotCardinality]} (got: {value!r})"
        )
        self.value = value


class InvalidWireSpecError(ValueError):
    """A TemplateWire is structurally malformed.

    Failure modes:
      - Any of the 4 string fields fails the trim-and-bound check
        (1-100 chars after trimming).
      - The degenerate full-loop case: same slot AND same port on
        both endpoints (mirrors PlanWireSelfLoopError). Self-slot
        with DIFFERENT ports is allowed (PandABox LUT pattern).

    Direction, signal_type, and fan-in are NOT checked here, and (as
    of today) NOT checked anywhere: register_fixture does not validate
    wires. Per-port conformance against materialized Asset.ports is a
    deferred read-side projection (the AssemblyConformanceMismatch
    posture); enforced routing lives in Plan.wiring.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid TemplateWire: {reason}")
        self.reason = reason


class InvalidTemplateSlotError(ValueError):
    """A TemplateSlot is structurally malformed.

    Failure modes:
      - `required_family_ids` is empty (a slot must require at least
        one Family for instantiation-time validation to mean anything).

    Distinct from InvalidWireSpecError so the route's exception
    handler can diverge if needed; today both map to HTTP 400.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid TemplateSlot: {reason}")
        self.reason = reason


class WireReferencesUnknownSlotError(ValueError):
    """A TemplateWire endpoint names a slot absent from `required_slots`.

    Structural well-formedness internal to the Assembly definition.
    The slot-name set is closed by the same construction call, so a
    missing reference is a typo or design mistake, not a cross-aggregate
    eventual-consistency case.
    """

    def __init__(self, slot_name: str) -> None:
        super().__init__(
            f"TemplateWire references slot {slot_name!r}, not present in required_slots"
        )
        self.slot_name = slot_name


class InvalidParameterOverridesSchemaError(ValueError):
    """The supplied parameter_overrides_schema is not a valid JSON
    Schema in CORA's constrained subset.

    Mapped to HTTP 400 by the BC exception handler, matching the
    `InvalidFamilySettingsSchemaError` precedent (both flow through
    `_handle_validation_error` in routes.py).
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Assembly parameter_overrides_schema: {reason}")
        self.reason = reason


class AssemblyAlreadyExistsError(Exception):
    """Attempted to define an assembly whose stream already has events."""

    def __init__(self, assembly_id: UUID) -> None:
        super().__init__(f"Assembly {assembly_id} already exists")
        self.assembly_id = assembly_id


class AssemblyNotFoundError(Exception):
    """Attempted an operation on an assembly whose stream has no events."""

    def __init__(self, assembly_id: UUID) -> None:
        super().__init__(f"Assembly {assembly_id} not found")
        self.assembly_id = assembly_id


class AssemblyCannotVersionError(Exception):
    """Attempted to version a Deprecated assembly.

    New revisions of a Deprecated Assembly must fork via
    `define_assembly` with a fresh id; the existing stream stays
    terminal.
    """

    def __init__(self, assembly_id: UUID, reason: str) -> None:
        super().__init__(f"Assembly {assembly_id} cannot be versioned: {reason}")
        self.assembly_id = assembly_id
        self.reason = reason


class AssemblyCannotDeprecateError(Exception):
    """Attempted to deprecate an already-Deprecated assembly.

    Strict-not-idempotent; the second call raises. Mirrors
    MountCannotDecommissionError.
    """

    def __init__(self, assembly_id: UUID, reason: str) -> None:
        super().__init__(f"Assembly {assembly_id} cannot be deprecated: {reason}")
        self.assembly_id = assembly_id
        self.reason = reason


class AssemblyCannotInstantiateError(Exception):
    """Attempted to instantiate a Deprecated assembly."""

    def __init__(self, assembly_id: UUID, reason: str) -> None:
        super().__init__(f"Assembly {assembly_id} cannot be instantiated: {reason}")
        self.assembly_id = assembly_id
        self.reason = reason


class FamilyNotFoundForAssemblyError(Exception):
    """A FamilyId referenced by `presents_as_family_id` or by a
    TemplateSlot's `required_family_ids` does not resolve to a defined
    Family.

    Handler-side projection check (mirrors Plan binding's existence
    checks). Distinct from the Recipe BC's FamilyNotFoundError so the
    route mapping can diverge if needed; today both map to 404.
    """

    def __init__(self, family_id: UUID) -> None:
        super().__init__(f"Family {family_id} not found")
        self.family_id = family_id


class FixtureAssetNotFoundError(Exception):
    """An asset_id referenced by `register_fixture`'s
    `slot_asset_bindings` does not resolve to a registered Asset.

    Handler-side projection check; mirrors
    FamilyNotFoundForAssemblyError. Distinct from the Asset BC's
    AssetNotFoundError so the route mapping stays scoped to the
    register_fixture call site; both map to 404 today.
    """

    def __init__(self, asset_id: UUID) -> None:
        super().__init__(f"Asset {asset_id} not found")
        self.asset_id = asset_id


class FixtureAssetNotAttachableError(Exception):
    """A referenced Asset's lifecycle disallows attachment to a Fixture.

    Currently fires for `Decommissioned` Assets only (terminal state;
    no further wiring). Mirrors the Asset BC's
    `AssetCannotAttachToFixtureError` precondition at register time:
    rejecting a Decommissioned binding here prevents the operator
    from registering a Fixture that would inevitably fail later at
    `attach_asset_to_fixture` (the Fixture is single-event-genesis
    and cannot be amended).

    Carries the sorted-first offending `asset_id` for deterministic
    error responses.
    """

    def __init__(self, asset_id: UUID, current_lifecycle: str) -> None:
        super().__init__(
            f"Asset {asset_id} cannot be bound into a Fixture: currently in "
            f"lifecycle {current_lifecycle}; expected Commissioned, Active, "
            f"or Maintenance"
        )
        self.asset_id = asset_id
        self.current_lifecycle = current_lifecycle


class FixtureAssetNotInstalledError(Exception):
    """A referenced Asset is not currently installed in any Mount.

    Fires when `proj_equipment_asset_location` carries no row for the
    Asset at register_fixture time, i.e., the Asset exists but has
    not been physically racked. A Fixture should materialize only
    equipment that is already on the floor, so the
    install-then-register-fixture choreography is the contract.

    Carries the sorted-first offending `asset_id` for deterministic
    error responses.
    """

    def __init__(self, asset_id: UUID) -> None:
        super().__init__(
            f"Asset {asset_id} cannot be bound into a Fixture: not currently "
            f"installed in any Mount; install_asset first"
        )
        self.asset_id = asset_id


class FixtureMappingIncompleteError(Exception):
    """`register_fixture`'s slot_asset_bindings does not satisfy
    the required cardinality of one or more slots.

    Example failure modes:
      - An `Exactly1` slot has zero or two mapped Assets.
      - A `OneOrMore` slot has zero mapped Assets.
    """

    def __init__(self, slot_name: str, reason: str) -> None:
        super().__init__(f"Slot {slot_name!r} cardinality not satisfied for Fixture: {reason}")
        self.slot_name = slot_name
        self.reason = reason


class FixtureAssetFamilyMismatchError(Exception):
    """A mapped Asset's `family_ids` do not intersect the TemplateSlot's
    `required_family_ids`."""

    def __init__(self, slot_name: str, asset_id: UUID) -> None:
        super().__init__(
            f"Asset {asset_id} mapped to slot {slot_name!r} does not carry "
            f"any of the slot's required_family_ids"
        )
        self.slot_name = slot_name
        self.asset_id = asset_id


class FixtureParameterOverridesInvalidError(ValueError):
    """`register_fixture`'s parameter_overrides dict fails the
    Assembly's parameter_overrides_schema validation.

    Subclasses ValueError so it satisfies the
    `validate_values_against_schema(error_class=...)` parameter type
    (the shared validator only accepts ValueError subclasses).
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Assembly parameter_overrides invalid: {reason}")
        self.reason = reason


class AssemblyRolePresentsAsAlreadyError(Exception):
    """`role_id` is already in the Assembly's `presents_as` set.

    Strict-not-idempotent: re-adding the same Role surfaces this
    rather than no-op. Mirrors `FamilyRolePresentsAsAlreadyError`
    (3B) and the wider Equipment-BC `add_*` convention.
    """

    def __init__(self, assembly_id: UUID, role_id: UUID) -> None:
        super().__init__(
            f"Assembly {assembly_id} already presents as Role {role_id} (strict-not-idempotent)"
        )
        self.assembly_id = assembly_id
        self.role_id = role_id


class AssemblyRolePresentsAsNotPresentError(Exception):
    """`role_id` is not in the Assembly's `presents_as` set.

    Strict-not-idempotent on remove. Mirrors
    `FamilyRolePresentsAsNotPresentError` (3B).
    """

    def __init__(self, assembly_id: UUID, role_id: UUID) -> None:
        super().__init__(
            f"Assembly {assembly_id} does not present as Role {role_id} "
            "(strict-not-idempotent on remove)"
        )
        self.assembly_id = assembly_id
        self.role_id = role_id


class InvalidSubAssemblyLinkError(ValueError):
    """A SubAssemblyLink is structurally malformed.

    Failure mode: `content_hash` is empty or whitespace-only. A link
    MUST pin the exact version of the child blueprint it references;
    an empty pin cannot identify a revision. Mapped to HTTP 400 by the
    BC exception handler.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid SubAssemblyLink: {reason}")
        self.reason = reason


class SubAssemblySlotNameConflictError(ValueError):
    """A SubAssemblyLink's slot_name collides with another named
    position in the same Assembly.

    Every named position in an Assembly (a `required_slots` slot or a
    `required_sub_assemblies` link) shares one slot-name namespace,
    because `register_fixture` keys the union of leaf slots by name
    when it expands a sub-assembly into the parent. A collision is a
    typo or design mistake internal to the Assembly definition, caught
    at construction. Mapped to HTTP 400.
    """

    def __init__(self, slot_name: str, reason: str) -> None:
        super().__init__(f"SubAssemblyLink slot_name {slot_name!r} conflicts: {reason}")
        self.slot_name = slot_name
        self.reason = reason


class SubAssemblyNotFoundForAssemblyError(Exception):
    """A `sub_assembly_id` referenced by a SubAssemblyLink does not
    resolve to a defined Assembly.

    Handler-side projection check at define_assembly / version_assembly
    time; mirrors `FamilyNotFoundForAssemblyError`. Maps to 404.
    """

    def __init__(self, sub_assembly_id: UUID) -> None:
        super().__init__(f"Sub-assembly {sub_assembly_id} not found")
        self.sub_assembly_id = sub_assembly_id


class SubAssemblyContentHashMismatchError(Exception):
    """A SubAssemblyLink's pinned `content_hash` does not match the
    referenced Assembly's current content_hash.

    The link pins the EXACT child revision it was authored against
    (snapshot semantics): adopting a new child revision is a
    deliberate re-version of the parent, not silent drift. A stale pin
    surfaces here at define / version time. Maps to 409.
    """

    def __init__(self, sub_assembly_id: UUID, *, pinned: str, current: str | None) -> None:
        super().__init__(
            f"Sub-assembly {sub_assembly_id} content_hash pin {pinned!r} "
            f"does not match current {current!r}"
        )
        self.sub_assembly_id = sub_assembly_id
        self.pinned = pinned
        self.current = current


class SubAssemblyCycleError(Exception):
    """A SubAssemblyLink would make an Assembly reference itself.

    Direct self-reference only for now (`sub_assembly_id` equals the
    Assembly's own id). Deeper A->B->A cycle detection is deferred
    until a second composing level lands (rule-of-three); the pilot
    nests one level (Microscope -> Optics). Maps to 400.
    """

    def __init__(self, assembly_id: UUID) -> None:
        super().__init__(f"Assembly {assembly_id} cannot reference itself as a sub-assembly")
        self.assembly_id = assembly_id


class SubAssemblyNestingTooDeepError(ValueError):
    """A SubAssemblyLink points at a child that is itself a composite.

    One composing level is supported: `register_fixture` expands a
    parent's sub-assemblies into a single flat union of leaf slots, and
    refuses any child that declares its own `required_sub_assemblies`.
    Authoring (`define_assembly` / `version_assembly`) enforces the same
    limit so that a defined Assembly is always instantiable rather than
    failing only at the end of the install-then-register choreography.
    Because a non-leaf child is refused here, an A->B->A indirect cycle
    is also impossible for the two-node case (B would need its own
    sub-assembly link back to A, which makes B non-leaf and rejects it).
    Deeper nesting is deferred until a real case lands (rule-of-three);
    the pilot nests one level (Microscope -> Optics). Maps to 400.
    """

    def __init__(self, sub_assembly_id: UUID) -> None:
        super().__init__(
            f"Sub-assembly {sub_assembly_id} declares its own sub-assemblies; "
            "nesting beyond one level is not yet supported"
        )
        self.sub_assembly_id = sub_assembly_id


@bounded_name(max_length=ASSEMBLY_NAME_MAX_LENGTH, error_class=InvalidAssemblyNameError)
@dataclass(frozen=True)
class AssemblyName:
    """A trimmed-bounded-text VO for the Assembly's display name.

    1-200 chars after trimming. Non-unique; the UUID is the storage
    identity and the content_hash is the structural fingerprint.
    """

    value: str


@bounded_name(max_length=SLOT_NAME_MAX_LENGTH, error_class=InvalidSlotNameError)
@dataclass(frozen=True)
class SlotName:
    """A trimmed-bounded-text VO for a TemplateSlot's slot_name.

    1-100 chars after trimming. Bound mirrors Wire port-name to keep
    a single max-length convention across slot-keyed shapes.
    """

    value: str


@dataclass(frozen=True)
class TemplateSlot:
    """One slot in an Assembly's composition blueprint.

    `slot_name` is the canonical slot identity within this Assembly
    (string, 1-100 chars). `required_family_ids` is the non-empty set
    of FamilyIds any instantiated Asset must include at least one of.
    `cardinality` says how many Assets can fill this slot
    (Exactly1 / ZeroOrOne / OneOrMore / ZeroOrMore). `default_settings`
    and `default_placement` are optional template defaults applied
    at instantiation unless overridden.

    `default_settings` validation against the intersection of all
    required_family_ids' settings schemas runs at define_assembly time
    (handler-side, not in __post_init__) because it requires loading
    Family records. The VO's __post_init__ only enforces structural
    well-formedness.
    """

    slot_name: SlotName
    required_family_ids: frozenset[UUID]
    cardinality: SlotCardinality
    default_settings: dict[str, Any] | None = None
    default_placement: Placement | None = None

    def __post_init__(self) -> None:
        # Defensive: cardinality is annotated as SlotCardinality but
        # nothing in Python stops a caller from passing a raw string
        # at construction. Catching it here surfaces a typed domain
        # error rather than a downstream AttributeError on .value.
        if not isinstance(self.cardinality, SlotCardinality):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise InvalidSlotCardinalityError(str(self.cardinality))
        if not self.required_family_ids:
            raise InvalidTemplateSlotError(
                f"TemplateSlot {self.slot_name.value!r} requires at least one Family"
            )

    def __hash__(self) -> int:
        # TemplateSlot is frozen but its `default_settings` field is a
        # dict (unhashable by Python default). Required because every
        # Assembly carries `required_slots: frozenset[TemplateSlot]`.
        # Hash canonicalizes the dict portion via stdlib json sort-keys
        # to give a stable, deterministic hash independent of insertion
        # order; full-record __eq__ stays dataclass-generated.
        settings_key = (
            json.dumps(self.default_settings, sort_keys=True, separators=(",", ":"))
            if self.default_settings is not None
            else None
        )
        return hash(
            (
                self.slot_name,
                self.required_family_ids,
                self.cardinality,
                settings_key,
                self.default_placement,
            )
        )


@dataclass(frozen=True)
class TemplateWire:
    """A typed slot-to-slot connection in an Assembly's blueprint.

    Tuple `(source_slot_name, source_port_name, target_slot_name,
    target_port_name)` describes one connection. The 4-tuple IS the
    identity; `frozenset[TemplateWire]` deduplicates on the tuple.

    Mirrors `Wire` (the Plan-tier signal-routing VO) in shape but
    keys by slot_name strings rather than Asset UUIDs because an
    Assembly cannot reference Assets that do not exist yet at
    template-definition time.

    Per-port conformance rules (deferred, NOT enforced today, neither
    here nor at register_fixture):
      - source port must have `direction=OUTPUT`
      - target port must have `direction=INPUT`
      - `source_port.signal_type == target_port.signal_type`
      - target port is the destination of at most one Wire (fan-in
        forbidden); fan-out (one source to many targets) is allowed
    These belong to a future read-side projection
    (`AssemblyConformanceMismatch`); enforced whole-experiment routing
    lives in `Plan.wiring`, keyed by concrete Asset UUIDs.

    `__post_init__` enforces structural shape only: each of the four
    string fields trims and bounds 1-100 chars, and the degenerate
    full-loop case (same slot AND same port on both endpoints) is
    rejected. Self-slot wires with different port names are allowed
    (PandABox LUT pattern, mirroring the Plan invariant).

    Cross-wire closure (every slot_name must exist in the parent
    Assembly's `required_slots`) is enforced at the Assembly level
    via `WireReferencesUnknownSlotError`, not here.
    """

    source_slot_name: str
    source_port_name: str
    target_slot_name: str
    target_port_name: str

    def __post_init__(self) -> None:
        for label, value in (
            ("source_slot_name", self.source_slot_name),
            ("source_port_name", self.source_port_name),
            ("target_slot_name", self.target_slot_name),
            ("target_port_name", self.target_port_name),
        ):
            trimmed = value.strip()
            if not trimmed:
                raise InvalidWireSpecError(f"{label} cannot be empty after trimming")
            if len(trimmed) > WIRE_PORT_NAME_MAX_LENGTH:
                raise InvalidWireSpecError(
                    f"{label} must be 1-{WIRE_PORT_NAME_MAX_LENGTH} chars after trimming "
                    f"(got: {value!r})"
                )
            object.__setattr__(self, label, trimmed)
        if (
            self.source_slot_name == self.target_slot_name
            and self.source_port_name == self.target_port_name
        ):
            raise InvalidWireSpecError(
                f"degenerate full self-loop on slot {self.source_slot_name!r} "
                f"port {self.source_port_name!r}"
            )


@dataclass(frozen=True)
class SubAssemblyLink:
    """A version-pinned link from a parent Assembly to a child Assembly.

    Lets an Assembly be composed of smaller reusable Assemblies, not
    only of individual `TemplateSlot` parts. The parent declares: "in
    the named position `slot_name`, include the Assembly
    `sub_assembly_id`, pinned at `content_hash`." At `register_fixture`
    time the child's own leaf slots expand into the parent's slot set
    (the union), so the materialized Fixture still binds only concrete
    Assets.

    `slot_name` reuses the `SlotName` VO: a sub-assembly occupies a
    named position in the parent exactly as a `TemplateSlot` does, and
    the two share one slot-name namespace (a link's slot_name must not
    collide with a leaf slot's, enforced at the Assembly level via
    `SubAssemblySlotNameConflictError`).

    `content_hash` is SNAPSHOT, not live: it pins the exact child
    revision the parent was authored against. A later child re-version
    does NOT silently change the parent's identity; adopting it is a
    deliberate re-version of the parent, and a stale pin is caught at
    define / version time via `SubAssemblyContentHashMismatchError`.
    Because the pinned child hash is folded into the parent's own
    `content_hash`, the structural fingerprint chains: a change deep in
    the tree ripples upward one deliberate adoption at a time.

    Frozen and fully hashable (all three fields are hashable), so it
    lives directly in `Assembly.required_sub_assemblies:
    frozenset[SubAssemblyLink]` without a custom __hash__.
    """

    slot_name: SlotName
    sub_assembly_id: UUID
    content_hash: str

    def __post_init__(self) -> None:
        if not self.content_hash.strip():
            raise InvalidSubAssemblyLinkError(
                f"link in slot {self.slot_name.value!r} must pin a non-empty content_hash"
            )


@dataclass(frozen=True)
class Assembly:
    """Aggregate root: a reusable composition blueprint.

    `id` is the opaque UUID stream key; `name` is the human-readable
    AssemblyName. `presents_as_family_id` is the FamilyId the
    instantiated Assembly looks like to Method.needed_families and
    Plan binding (one Asset-shaped unit).

    `required_slots`, `required_wires`, and `required_sub_assemblies`
    together describe the composition: slots declare what kinds of
    Assets fill which roles, wires declare how those Assets connect,
    and sub-assembly links include whole child Assemblies (version-
    pinned) as named positions. All key by slot_name (not by Asset
    UUID) since Assets do not exist at template time.

    `parameter_overrides_schema` is an optional JSON Schema subset
    declaring the shape of parameter_overrides accepted at
    instantiation. `drawing` is the optional engineering reference.

    `status` transitions Defined -> Versioned (multiple times) ->
    Deprecated. `version` is an operator-curated label. `content_hash`
    is the SHA-256 hex fingerprint of the canonical subset
    `{name, presents_as_family_id, required_slots, required_wires,
    required_sub_assemblies, parameter_overrides_schema}` (excludes
    id / drawing / version / status, which are not structural identity
    per the design memo).

    `__post_init__` enforces internal closure: every TemplateWire's
    source_slot_name and target_slot_name MUST appear in
    `required_slots`, and each `required_sub_assemblies` link's
    slot_name must be unique across the blueprint (no collision with a
    leaf slot or another link). Cross-aggregate references (FamilyId /
    sub-assembly existence, content_hash pinning, schema validation)
    live in handler-side projection checks.
    """

    id: UUID
    name: AssemblyName
    presents_as_family_id: UUID
    required_slots: frozenset[TemplateSlot] = field(default_factory=frozenset[TemplateSlot])
    required_wires: frozenset[TemplateWire] = field(default_factory=frozenset[TemplateWire])
    required_sub_assemblies: frozenset[SubAssemblyLink] = field(
        default_factory=frozenset[SubAssemblyLink]
    )
    parameter_overrides_schema: dict[str, Any] | None = None
    drawing: Drawing | None = None
    status: AssemblyStatus = AssemblyStatus.DEFINED
    version: str | None = None
    content_hash: str | None = None
    presents_as: frozenset[RoleId] = field(default_factory=frozenset[RoleId])
    """Layer 3 sub-slice 3C: the set of global Role contracts this
    composed Assembly advertises (Lock 4 universal presents_as).
    Parallel mechanism to the scalar `presents_as_family_id`: 3C
    keeps the scalar (per anti-hook #6, one migration cycle), and
    layers `presents_as` alongside for Role-based binding via 3D's
    bind_plan_role role_kind path. Microscope-Assembly seeds
    `{Detector}` at scenario-fixture time.

    NOT included in `content_subset()` -- additive orthogonal-axis
    field, parallel to Family.settings_schema; adding or removing a
    Role advertisement does not produce a structurally-distinct
    Assembly identity.

    Affordance-superset check (Family.affordances >=
    Role.required_affordances) DEFERRED at 3C: Assembly affordances
    derive from the constituent Family union at register_fixture
    time, not Assembly template time, so the check belongs at the
    fixture-registration layer. Watch item logged."""

    def __post_init__(self) -> None:
        slot_names = {slot.slot_name.value for slot in self.required_slots}
        for wire in self.required_wires:
            if wire.source_slot_name not in slot_names:
                raise WireReferencesUnknownSlotError(wire.source_slot_name)
            if wire.target_slot_name not in slot_names:
                raise WireReferencesUnknownSlotError(wire.target_slot_name)
        seen_sub_assembly_names: set[str] = set()
        for link in self.required_sub_assemblies:
            link_name = link.slot_name.value
            if link_name in slot_names:
                raise SubAssemblySlotNameConflictError(
                    link_name, reason="already a required_slots slot_name"
                )
            if link_name in seen_sub_assembly_names:
                raise SubAssemblySlotNameConflictError(
                    link_name, reason="duplicate sub-assembly slot_name"
                )
            seen_sub_assembly_names.add(link_name)

    def content_subset(self) -> dict[str, object]:
        """Canonical content subset hashed into `content_hash`.

        Pins identity per `project_content_addressed_identity_design`:
        `name + presents_as_family_id + required_slots + required_wires +
        required_sub_assemblies + parameter_overrides_schema`. Excluded:
        `id` (identity, not
        content), `status` and `version` (lifecycle, derived in evolver
        from event type and version label), `drawing` (operator-
        curatorial metadata per the design memo's content_hash
        composition lock), `content_hash` itself (cannot self-contain).

        Delegates to `canonical_assembly_subset` so the helper used by
        `compute_assembly_content_hash` (raw-args path) and this
        method (state path) materialize the same shape. Field
        addition lands in ONE place; drift between the two paths
        becomes structurally impossible.
        """
        return canonical_assembly_subset(
            name=self.name,
            presents_as_family_id=self.presents_as_family_id,
            required_slots=self.required_slots,
            required_wires=self.required_wires,
            required_sub_assemblies=self.required_sub_assemblies,
            parameter_overrides_schema=self.parameter_overrides_schema,
        )


def canonical_assembly_subset(
    *,
    name: "AssemblyName | str",
    presents_as_family_id: UUID,
    required_slots: frozenset[TemplateSlot],
    required_wires: frozenset[TemplateWire],
    required_sub_assemblies: frozenset[SubAssemblyLink],
    parameter_overrides_schema: dict[str, object] | None,
) -> dict[str, object]:
    """Materialize the canonical content subset of an Assembly.

    Single source of truth for the structural-identity body. Called by
    both `Assembly.content_subset()` (state path) and
    `compute_assembly_content_hash` (raw-args path); the round-trip
    equivalence between the two is pinned in tests.

    Slots render as a list of dicts sorted by slot_name; wires render
    as sorted 4-tuples-of-strings; sub-assembly links render as dicts
    (slot_name + sub_assembly_id + child content_hash) sorted by
    slot_name, for canonical-sort determinism. UUIDs render as
    strings. Adding a new identity-bearing field requires editing this
    one function plus the content_hash differs-test corpus.
    """
    name_value = name.value if isinstance(name, AssemblyName) else name
    return {
        "name": name_value,
        "presents_as_family_id": str(presents_as_family_id),
        "required_slots": sorted(
            (
                {
                    "slot_name": slot.slot_name.value,
                    "required_family_ids": sorted(str(f) for f in slot.required_family_ids),
                    "cardinality": slot.cardinality.value,
                    "default_settings": slot.default_settings,
                    "default_placement": (
                        canonical_placement_subset(slot.default_placement)
                        if slot.default_placement is not None
                        else None
                    ),
                }
                for slot in required_slots
            ),
            key=lambda d: str(d["slot_name"]),
        ),
        "required_wires": sorted(
            (
                wire.source_slot_name,
                wire.source_port_name,
                wire.target_slot_name,
                wire.target_port_name,
            )
            for wire in required_wires
        ),
        "required_sub_assemblies": sorted(
            (
                {
                    "slot_name": link.slot_name.value,
                    "sub_assembly_id": str(link.sub_assembly_id),
                    "content_hash": link.content_hash,
                }
                for link in required_sub_assemblies
            ),
            key=lambda d: str(d["slot_name"]),
        ),
        "parameter_overrides_schema": parameter_overrides_schema,
    }


def canonical_placement_subset(placement: Placement) -> dict[str, object]:
    """Canonical dict form of a Placement for content_hash inclusion.

    Distinct from `placement_to_payload` (which is the JSON-storage
    codec on the Placement VO module): the canonical-subset form
    excludes nothing today but reserves the freedom to drop or rename
    fields without disturbing the at-rest event schema.
    """
    return {
        "x": placement.x,
        "y": placement.y,
        "z": placement.z,
        "rx": placement.rx,
        "ry": placement.ry,
        "rz": placement.rz,
        "parent_frame_id": str(placement.parent_frame_id),
        "reference_surface": placement.reference_surface.value,
        "tol_x": placement.tol_x,
        "tol_y": placement.tol_y,
        "tol_z": placement.tol_z,
        "tol_rx": placement.tol_rx,
        "tol_ry": placement.tol_ry,
        "tol_rz": placement.tol_rz,
        "units": placement.units.value,
    }
