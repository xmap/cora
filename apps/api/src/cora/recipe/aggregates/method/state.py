"""Method aggregate state, value objects, status enum, and domain errors.

`Method` is the abstract recipe — the technique class as published
by the vendor or scientific community. Examples: "X-ray Fluorescence
Mapping", "Step Tomography", "Ptychography". Equipment-agnostic
(refers to `Family` ids only, not specific Asset instances).

Per the BC map's recipe ladder, Method ≈ ISA-88 General Recipe. The
facility's adapted version lives in `Practice`, and the
concrete Asset binding lives in `Plan`.


Minimal Method:
  - `id` + `name`
  - `needed_family_ids: frozenset[UUID]` — the Family ids this
    Method requires. Composable: a "Fly Tomography" Method has
    needed_family_ids = {Tomography_id, FlyScan_id}. At Plan
    binding time, the operator picks an Asset whose
    families ⊇ method.needed_family_ids.
  - `status` (defaults `Defined`).

`Versioned` and `Deprecated` transitions land in the lifecycle
slices. Description / owner / additional facets defer to enrichment.

## Needed_family_ids: eventual-consistency stance

The decider does NOT verify each Family id refers to a real
Family stream in the event store. Same precedent as Trust's
Conduit zone refs and Asset parent refs. Typos produce
"dangling" Methods; downstream Plan binding is where the
mismatch will surface (Asset can't satisfy the requirement). For
day-one ergonomics this is fine; structural validation can be
layered on at the API boundary later if pilot demand emerges.

Empty `needed_family_ids` is allowed (a Method that needs no
specific equipment family — rare but operationally valid for
purely procedural Methods like "Sample Cleaning").

## Status as enum-in-state, derived-from-event-type-in-evolver

`MethodStatus` is a `StrEnum` so the values would serialize
naturally as JSON-friendly strings IF carried in an event payload.
Today they aren't: state holds the enum (typed) and the evolver
derives the new status from the event TYPE — same precedent as
`FamilyStatus`, `SubjectStatus`, `AssetLifecycle`.

## Eighth bounded-name VO

`MethodName` is the **eighth** trimmed-bounded-name VO after
`ActorName`, `ZoneName`, `ConduitName`, `PolicyName`, `SubjectName`,
`FamilyName`, `AssetName`. The shared trim+length-check logic was
hoisted to `cora.shared.bounded_text.validate_bounded_text`
once the 10th VO (PlanName) landed; MethodName now calls that
helper while keeping its own frozen dataclass type and per-aggregate
error class. See the helper module's docstring for the design
rationale.

## Frozensets in state, lists in payloads

`needed_family_ids` is `frozenset[UUID]` in domain state
(deduplicated, hashable, set-membership in O(1) for Plan-binding
checks) and `list[UUID]` in event payloads (JSON-friendly, sorted
for determinism). Same precedent as Trust's Policy
`permitted_principal_ids` / `permitted_commands`. The evolver bridges
the two. Sorting in `to_payload` keeps the persisted bytes
deterministic — same logical family set, same payload, same
idempotency hash.

## Positional role tagging: required_roles

The Method-side `required_roles: frozenset[RoleRequirement]` field
plus the `RoleRequirement` + `PortRequirement` + `RoleName` VOs
encode the positional role-tagging vocabulary. The Function-aspect
gap (IEC 81346 `=`) was the motivating audit finding: two Cameras
in one Method (one DETECTOR, one SAMPLE_MONITOR) cannot be
disambiguated by `needed_family_ids` alone, which is a
`frozenset[UUID]` with set-membership semantics. Each
`RoleRequirement` carries a Method-local role name, the Family the
bound Asset must satisfy, a set of port requirements, and an
optional flag. Plan-side role bindings and the
`PlanWireRoleEndpointMismatchError` invariant (which closes the
role-table-vs-wire-graph divergence) live in the Plan aggregate.
See [[project-method-required-roles-design]] for the full design
lock and [[project-equipment-isa-gap-research]] for the
Function-aspect gap context.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from cora.equipment.aggregates.asset import (
    PORT_NAME_MAX_LENGTH,
    PORT_SIGNAL_TYPE_MAX_LENGTH,
    PortDirection,
)
from cora.shared.bounded_text import bounded_name
from cora.shared.scope_markers import Annotated, DeferredVocabulary

METHOD_NAME_MAX_LENGTH = 200
METHOD_VERSION_TAG_MAX_LENGTH = 50
# needed_supplies element bounds. Mirrors Supply.kind shape
# (cora.supply.aggregates.supply.state.SUPPLY_KIND_MAX_LENGTH = 50)
# so per-element validation in the Method decider stays consistent
# with what Supply itself accepts at register_supply time. See
# [[project_supply_design]] §"Method.needed_supplies consumer"
# for the design lock.
METHOD_NEEDED_SUPPLY_KIND_MAX_LENGTH = 50
# RoleName bound. Method-local labels for positional role-tagging
# (IEC 81346 Function aspect; see [[project-method-required-roles-design]]
# and [[project-equipment-isa-gap-research]]). Free-string within the
# Method scope; uniqueness enforced by the add_method_required_role
# decider, not the VO. 50-char ceiling matches `RoleKind`-style
# vocabulary precedent and stays well under the 200-char name-length
# ceiling used by aggregate-display-name VOs.
ROLE_NAME_MAX_LENGTH = 50
# PortRequirement field bounds mirror the AssetPort VO in
# `cora.equipment.aggregates.asset` so a port the Method requires can
# never exceed what the Asset itself permits. The constants are
# re-exported by name from this module so slice authors can `from
# cora.recipe.aggregates.method import ROLE_PORT_NAME_MAX_LENGTH`
# without dragging the equipment.asset namespace into Method slice
# files.
ROLE_PORT_NAME_MAX_LENGTH = PORT_NAME_MAX_LENGTH
ROLE_PORT_SIGNAL_TYPE_MAX_LENGTH = PORT_SIGNAL_TYPE_MAX_LENGTH


class MethodStatus(StrEnum):
    """The Method's lifecycle state.

    Transitions land per-slice:
      - Defined -> Versioned        (version_method)
      - (Defined | Versioned) -> Deprecated   (deprecate_method)

    `Defined` is the genesis state set by `define_method`. The enum
    values are PascalCase strings (matching the BC-map status
    vocabulary) so log lines and DTOs read naturally without
    additional mapping.
    """

    DEFINED = "Defined"
    VERSIONED = "Versioned"
    DEPRECATED = "Deprecated"


class InvalidMethodNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Method name must be 1-{METHOD_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class MethodAlreadyExistsError(Exception):
    """Attempted to define a method whose stream already has events."""

    def __init__(self, method_id: UUID) -> None:
        super().__init__(f"Method {method_id} already exists")
        self.method_id = method_id


class MethodNotFoundError(Exception):
    """Attempted an operation on a method whose stream has no events."""

    def __init__(self, method_id: UUID) -> None:
        super().__init__(f"Method {method_id} not found")
        self.method_id = method_id


class MethodCannotVersionError(Exception):
    """Attempted to version a method not in `Defined` or `Versioned`.

    Multi-source guard: `version_method` accepts both `Defined`
    (first revision) and `Versioned` (subsequent revisions —
    operators bump v1 → v2 → v3 over time as the recipe's
    parameters or step list are refined). Only `Deprecated` is
    rejected (you can't revise a deprecated method — un-deprecate
    first if you want to bring it back, though that slice doesn't
    exist today).

    Mirrors `FamilyCannotVersionError` shape and semantics
    (Equipment BC). Same deliberate divergence from strict-not-
    idempotent: re-versioning with the same tag succeeds and emits a
    fresh event (re-attestation is a legitimate audit moment).
    Pinned by tests/unit/recipe/test_version_method_decider.py.
    """

    def __init__(self, method_id: UUID, current_status: "MethodStatus") -> None:
        super().__init__(
            f"Method {method_id} cannot be versioned: currently in status "
            f"{current_status.value}, version requires "
            f"{MethodStatus.DEFINED.value} or {MethodStatus.VERSIONED.value}"
        )
        self.method_id = method_id
        self.current_status = current_status


class MethodCannotDeprecateError(Exception):
    """Attempted to deprecate a method not in `Defined` or `Versioned`.

    Multi-source guard: `deprecate_method` accepts both `Defined`
    (deprecating before any revisions) and `Versioned` (deprecating
    a revised recipe). Re-deprecating an already-`Deprecated` method
    raises (strict-not-idempotent). Mirrors
    `FamilyCannotDeprecateError` shape.

    Existing Plans / Practices that reference this Method are NOT
    automatically invalidated. Deprecation is advisory at the BC
    layer; future Plan-side enrichment may surface a warning at
    bind-time when referencing a deprecated Method.
    """

    def __init__(self, method_id: UUID, current_status: "MethodStatus") -> None:
        super().__init__(
            f"Method {method_id} cannot be deprecated: currently in status "
            f"{current_status.value}, deprecate requires "
            f"{MethodStatus.DEFINED.value} or {MethodStatus.VERSIONED.value}"
        )
        self.method_id = method_id
        self.current_status = current_status


class InvalidMethodNeededSuppliesError(ValueError):
    """One of the supplied needed_supplies kind strings is empty,
    whitespace-only, or too long.

    Validated at the API boundary via Pydantic per-element
    `min_length=1, max_length=50`, AND defensively at the decider via
    this error so direct in-process callers (sagas, tests) get the
    same protection. The diagnostic carries the offending element.

    Per-element bound mirrors `InvalidSupplyKindError` from the Supply
    BC (the kind is the abstract label; Method's needed_supplies
    references kind values that Supply registrations carry). See
    [[project_supply_design]] §"Method.needed_supplies consumer" for
    the design lock + asymmetry rationale (frozenset[str] on Method
    vs frozenset[UUID] for needed_family_ids: Supply is INSTANCE-aggregate
    per facility, sharing a `kind` label; Family is TYPE-aggregate,
    one global definition referenced by UUID).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Method needed_supplies kind must be 1-{METHOD_NEEDED_SUPPLY_KIND_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidMethodVersionTagError(ValueError):
    """The supplied version tag is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error so direct in-process
    callers (sagas, tests) get the same protection. Same precedent as
    `InvalidFamilyVersionTagError` (Equipment BC) and
    `InvalidMethodNameError`.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Method version tag must be 1-{METHOD_VERSION_TAG_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


@bounded_name(max_length=METHOD_NAME_MAX_LENGTH, error_class=InvalidMethodNameError)
@dataclass(frozen=True)
class MethodName:
    """Display name for a method. Trimmed; 1-200 chars.

    Eighth occurrence of the trimmed-bounded-name VO pattern. Uses
    the shared `bounded_name` decorator (see
    `cora.shared.bounded_text`).
    """

    value: str


class InvalidRoleNameError(ValueError):
    """The supplied role_name is empty, whitespace-only, or too long.

    Part of the positional role-tagging workstream. Role names are
    Method-local free strings (1-50 chars after trimming); uniqueness
    is enforced by the `add_method_required_role` decider, not by the
    VO. See [[project-method-required-roles-design]] for the design
    lock and [[project-equipment-isa-gap-research]] for the
    Function-aspect gap context.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Method role name must be 1-{ROLE_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidPortRequirementError(ValueError):
    """The supplied port requirement has an empty/whitespace-only or
    too-long `port_name` or `signal_type`.

    Mirrors `InvalidAssetPortNameError` and
    `InvalidAssetPortSignalTypeError` from the Equipment BC. A port
    requirement Method-side can never exceed what an Asset.ports entry
    permits at register_asset time, so the bounds are shared via the
    re-exported `ROLE_PORT_NAME_MAX_LENGTH` and
    `ROLE_PORT_SIGNAL_TYPE_MAX_LENGTH` constants.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid port requirement: {reason}")
        self.reason = reason


@bounded_name(max_length=ROLE_NAME_MAX_LENGTH, error_class=InvalidRoleNameError)
@dataclass(frozen=True)
class RoleName:
    """A Method-local positional role label. Trimmed; 1-50 chars.

    Names roles within a single Method scope (for example, `"detector"`,
    `"sample_monitor"`, `"axis"`). Cross-Method consistency (operators
    using the same label for the same role across Methods) is a docs
    concern, not a kernel invariant. See
    [[project-method-required-roles-design]] §"Open questions resolved".
    """

    value: str


@dataclass(frozen=True)
class PortRequirement:
    """A port the Asset bound to a role MUST expose.

    Tuple `(port_name, direction, signal_type)`. `port_name` is the
    exact (case-sensitive, after trimming) port name the bound Asset
    is expected to carry on its `ports` set. Glob/regex matching is
    deferred per [[project-method-required-roles-design]] §"Open
    questions resolved". `direction` reuses the closed `PortDirection`
    enum from Equipment BC's Asset aggregate so a port the Method
    requires is shape-comparable to the Asset.ports the Plan validates
    against at bind-time.

    The VO itself trims and bounds-checks the strings; uniqueness of
    `port_name` within a single role's `required_ports` is structural
    (frozenset semantics: identical (port_name, direction, signal_type)
    tuples collapse). Cross-aggregate validation (the bound Asset has
    matching ports) lives in the Plan decider.
    """

    port_name: str
    direction: PortDirection
    signal_type: str

    def __post_init__(self) -> None:
        trimmed_name = self.port_name.strip()
        if not trimmed_name or len(trimmed_name) > ROLE_PORT_NAME_MAX_LENGTH:
            raise InvalidPortRequirementError(
                f"port_name must be 1-{ROLE_PORT_NAME_MAX_LENGTH} chars after trimming "
                f"(got: {self.port_name!r})"
            )
        trimmed_signal = self.signal_type.strip()
        if not trimmed_signal or len(trimmed_signal) > ROLE_PORT_SIGNAL_TYPE_MAX_LENGTH:
            raise InvalidPortRequirementError(
                f"signal_type must be 1-{ROLE_PORT_SIGNAL_TYPE_MAX_LENGTH} chars after "
                f"trimming (got: {self.signal_type!r})"
            )
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed values.
        object.__setattr__(self, "port_name", trimmed_name)
        object.__setattr__(self, "signal_type", trimmed_signal)


class RoleRequirementBindingDuplicateError(ValueError):
    """RoleRequirement has BOTH `role_kind` and `family_id` set.

    Per [[project-role-aggregate-design]] Lock 5: exactly one of
    `role_kind` (global Role contract; federation-portable path) or
    `family_id` (anatomical escape hatch; slice-1 path) must be
    present. Both-set signals operator confusion: the bind would be
    ambiguous about which satisfaction path to take.

    Subclasses ValueError so it satisfies VO-error conventions
    (mirrors `InvalidRoleNameError` posture).
    """

    def __init__(
        self,
        role_name: "RoleName",
        role_kind: UUID,
        family_id: UUID,
    ) -> None:
        super().__init__(
            f"RoleRequirement {role_name.value!r} has BOTH role_kind "
            f"{role_kind} AND family_id {family_id}; exactly one must "
            "be set (XOR invariant per role-aggregate-design Lock 5)"
        )
        self.role_name = role_name
        self.role_kind = role_kind
        self.family_id = family_id


class InvalidRoleRequirementTargetError(ValueError):
    """RoleRequirement has NEITHER `role_kind` nor `family_id` set.

    Per [[project-role-aggregate-design]] Lock 5 XOR invariant: a
    naked `role_name` without a binding target is ambiguous about
    what Asset satisfies. Subclasses ValueError so it satisfies VO-
    error conventions.
    """

    def __init__(self, role_name: "RoleName") -> None:
        super().__init__(
            f"RoleRequirement {role_name.value!r} has NEITHER role_kind "
            "nor family_id; exactly one must be set (XOR invariant per "
            "role-aggregate-design Lock 5)"
        )
        self.role_name = role_name


@dataclass(frozen=True)
class RoleRequirement:
    """A named positional role slot the Method declares.

    Tuple `(role_name, role_kind, family_id, required_ports, optional)`.

    `role_name` is the Method-local label (`RoleName` VO).

    `role_kind` is the global Role contract id this slot targets
    (per [[project-role-aggregate-design]] Lock 5; Layer 3 sub-slice
    3D). Federation-portable path: any Asset whose Family.presents_as
    contains role_kind AND whose Family.affordances superset
    Role.required_affordances (Lock 17 ANY-single-family disjunction)
    satisfies. Bare `UUID` (not `RoleId` NewType) per cross-BC
    convention: avoids Recipe -> Equipment NewType import; symmetric
    with `family_id: UUID`.

    `family_id` is the Family the Asset bound to this role must
    satisfy via direct family-id membership (anatomical escape
    hatch). KEPT after 3D for backward compatibility with slice-1
    Methods (anti-hook #6: removal is a separate slice gated on the
    "6 months on main + zero new family_id-only RoleRequirements"
    trigger).

    ## XOR invariant

    Exactly one of `role_kind` / `family_id` must be set. Both-set
    raises `RoleRequirementBindingDuplicateError`; neither-set
    raises `InvalidRoleRequirementTargetError`. The decider's
    handler also fail-fast resolves `role_kind` via RoleLookup
    before threading into the decider so callers see
    RoleNotFoundError rather than a satisfaction-side failure.

    `required_ports` is the set of ports the bound Asset must expose
    for this role; empty means "pure Asset-binding role, no port
    contract." Non-empty means the
    `PlanWireRoleEndpointMismatchError` invariant requires any Wire
    whose endpoint port is named here to terminate at the Asset bound
    to THIS role.

    `optional` is False by default; a True role may be omitted from a
    Plan's role_bindings without triggering Plan-side
    `PlanRoleNotBoundError`.

    Uniqueness of `role_name` within a single Method's `required_roles`
    is enforced by the `add_method_required_role` decider, not by the
    VO.
    """

    role_name: RoleName
    role_kind: UUID | None = None
    family_id: UUID | None = None
    required_ports: frozenset[PortRequirement] = field(default_factory=frozenset[PortRequirement])
    optional: bool = False

    def __post_init__(self) -> None:
        # XOR invariant: exactly one of role_kind / family_id is set.
        # Both-set + neither-set both surface as dedicated errors so
        # the operator response distinguishes the two confusions.
        if self.role_kind is not None and self.family_id is not None:
            raise RoleRequirementBindingDuplicateError(
                role_name=self.role_name,
                role_kind=self.role_kind,
                family_id=self.family_id,
            )
        if self.role_kind is None and self.family_id is None:
            raise InvalidRoleRequirementTargetError(role_name=self.role_name)


class MethodRoleNameAlreadyDeclaredError(Exception):
    """Attempted to add a required role whose name is already declared
    on the Method.

    Strict-not-idempotent: same precedent as
    `AssetOwnerAlreadyPresentError` and `AssetCannotAddPortError`. The
    diagnostic carries both `method_id` and the offending `role_name`
    so the operator error response can disambiguate which role
    conflicted.
    """

    def __init__(self, method_id: UUID, role_name: "RoleName") -> None:
        super().__init__(
            f"Method {method_id} already has required role {role_name.value!r}; "
            "add_method_required_role is strict-not-idempotent"
        )
        self.method_id = method_id
        self.role_name = role_name


class MethodRoleNameNotFoundError(Exception):
    """Attempted to remove a required role whose name is not declared
    on the Method.

    Mirror of `MethodRoleNameAlreadyDeclaredError`. Strict-not-
    idempotent: a second remove (or a remove of an unknown role) hits
    this rather than silently no-opping.
    """

    def __init__(self, method_id: UUID, role_name: "RoleName") -> None:
        super().__init__(
            f"Method {method_id} does not have required role {role_name.value!r}; nothing to remove"
        )
        self.method_id = method_id
        self.role_name = role_name


class MethodCannotMutateRequiredRolesError(Exception):
    """Attempted to add/remove a required role on a Method not in
    `Defined` status.

    Mirrors `MethodCannotVersionError` shape. Required-roles mutations
    are restricted to the `Defined` status: a `Versioned` Method has an
    attested content_hash that covers `required_roles`, and a
    `Deprecated` Method is out of use entirely. The error message
    carries the current status for diagnostic clarity. Symmetric across
    `add_method_required_role` and `remove_method_required_role` per
    [[project-method-required-roles-design]] §"Slices".
    """

    def __init__(self, method_id: UUID, current_status: "MethodStatus") -> None:
        super().__init__(
            f"Method {method_id} cannot mutate required roles: currently in status "
            f"{current_status.value}, required-role mutations require "
            f"{MethodStatus.DEFINED.value}"
        )
        self.method_id = method_id
        self.current_status = current_status


@dataclass(frozen=True)
class Method:
    """Aggregate root: an abstract technique-class recipe.

    `needed_family_ids` is a frozenset of Family ids the Method
    requires. Eventual-consistency stance: existence is not verified
    at decide time; mismatch surfaces at Plan binding.

    `version` is the operator-supplied label of the most recent
    `version_method` call (None until first version). State always
    holds the latest tag — past tags live in the event stream as
    `MethodVersioned` events. No `current_` prefix because state by
    definition holds current values (same convention as `status`,
    `name`). Free-text validated at API boundary + defensively in the
    decider; no VO. Default None keeps MethodDefined-only legacy
    streams folding cleanly (additive-state pattern). Mirrors
    Family's `version` semantics (Equipment BC): preserved
    across deprecation as an audit signal of the last revision before
    deprecation.

    `parameters_schema` is the optional JSON Schema (Draft 2020-12,
    constrained subset) declaring the shape of parameter dicts that
    Plans and Runs carry for this Method. Defaults to
    None for legacy Methods (additive-state pattern); None means
    "this Method declares no parameter contract, accept any dict".
    Distinct from `{}` (empty schema, "operator explicitly said no
    parameters"). Subset shared with Family.settings_schema via
    `cora.shared.json_schema_subset`. See
    [[project_run_parameters_design]] for the full parameter-family layout.
    """

    id: UUID
    name: MethodName
    needed_family_ids: frozenset[UUID] = field(default_factory=frozenset[UUID])
    status: MethodStatus = MethodStatus.DEFINED
    version: str | None = None
    # content_hash captures the SHA-256 of the canonical body bytes for
    # the most recently versioned content subset (`name +
    # parameters_schema + capability_id + needed_family_ids +
    # needed_supplies`). None until first MethodVersioned (Defined-only
    # streams have no attested revision yet) AND for pre-rollout legacy
    # MethodVersioned events that predate the content-hash field
    # (additive-state pattern; same posture as `version`, `capability_id`).
    # Preserved across MethodDeprecated and MethodParametersSchemaUpdated:
    # the hash represents the LAST ATTESTED revision, so post-rollout
    # schema updates intentionally leave the hash pointing at the prior
    # version — see [[project_content_addressed_identity_design]].
    content_hash: str | None = None
    parameters_schema: dict[str, Any] | None = field(default=None)
    # Method.capability_id points to the universal Capability
    # template (Recipe BC) this Method realizes as a Method-shaped
    # executor. REQUIRED at define_method now; defaults None at the
    # STATE level for evolver-back-compat with older streams (additive-
    # state pattern; same shape as Method.parameters_schema).
    # Distinct from `needed_family_ids` (hardware compatibility, what
    # Family classes the Method needs available), both fields stay,
    # answering DIFFERENT questions per [[project-capability-aggregate-design]]
    # see [[project-capability-aggregate-design]] watch item 10. The cross-BC validation that
    # `Method.parameters_schema ⊂ Capability.parameters_schema` runs at
    # define_method time via the capability_loader port (STRICT per
    # [[project-asset-settings-design]] cross-BC anchor).
    capability_id: UUID | None = field(default=None)
    # needed_supplies references Supply.kind STRINGS (not
    # UUIDs). Asymmetric with needed_family_ids (frozenset[UUID]) by
    # design: Family is a TYPE registry (one global definition,
    # referenced by UUID); Supply is an INSTANCE aggregate (multiple
    # per facility, each with its own availability state, sharing a
    # `kind` label). Methods are facility-portable so they reference
    # the abstract kind, not a per-facility instance UUID. Defaults
    # to empty frozenset (additive-state pattern; legacy
    # MethodDefined-only streams fold cleanly via payload.get default).
    # See [[project_supply_design]] §"Method.needed_supplies consumer"
    # for the full design lock.
    #
    # Carries a `DeferredVocabulary[SupplyKind]` marker per
    # [[project_structural_scope_design]] §"Marker convention": the
    # bare-str element type graduates to a typed `SupplyKind(StrEnum)`
    # in LOCKSTEP with Supply.kind when Supply.kind Watch item 4 fires.
    # See `cora.shared.scope_markers` for the marker shape.
    needed_supplies: Annotated[
        frozenset[str],
        DeferredVocabulary(
            target_name="SupplyKind",
            trigger_doc="Supply.kind Watch item 4 trigger per project-structural-scope-design",
        ),
    ] = field(default_factory=frozenset[str])
    # needed_assembly_ids references Assembly aggregates (Equipment BC)
    # by UUID. Declares "this Method needs a specific composition
    # blueprint" (e.g., the Microscope fixture), not just N
    # independent Assets of the Families in needed_family_ids. Plan
    # binding consults this set at bind time: each id in
    # Method.needed_assembly_ids must be materialized as a Fixture among
    # the Plan's Assets, where Fixture.assembly_id matches. Affordance-cover (Capability) check is
    # unchanged because Assembly.presents_as provides the Role contracts
    # the Capability binds against. Defaults to empty
    # frozenset (additive-state pattern; legacy MethodDefined-only
    # streams fold cleanly via payload.get default). See
    # [[project-assembly-aggregate-design]] Locks section for the cross-BC
    # contract.
    needed_assembly_ids: frozenset[UUID] = field(default_factory=frozenset[UUID])
    # required_roles declares the Method's positional role slots
    # (IEC 81346 Function aspect). Each `RoleRequirement` carries a
    # Method-local role_name + the Family the bound Asset must satisfy
    # + a set of port requirements + an optional flag. Defaults empty
    # so legacy MethodDefined-only streams fold cleanly via the
    # additive-state pattern. Plan-side role bindings enforce
    # 1-1 binding per non-optional role + port-coverage; the Method
    # aggregate only owns the declaration vocabulary.
    # Identity within the set is structural (frozenset of
    # RoleRequirement); role_name uniqueness is enforced at the
    # decider (add_method_required_role rejects duplicates). See
    # [[project-method-required-roles-design]] for the full lock and
    # [[project-equipment-isa-gap-research]] for the Function-aspect
    # gap context.
    required_roles: frozenset[RoleRequirement] = field(default_factory=frozenset[RoleRequirement])

    def content_subset(self) -> dict[str, object]:
        """Canonical content subset hashed into MethodVersioned.content_hash.

        Pins identity per [[project_content_addressed_identity_design]]:
        `name + parameters_schema + capability_id + needed_family_ids +
        needed_supplies + needed_assembly_ids`. Identity-bearing fields
        excluded: `id` (identity, not content); `status` and `version`
        (lifecycle, derived in evolver from event type and version_tag).
        UUIDs render as strings (json-serializable); frozensets render
        as sorted lists (canonical_body_bytes would sort either way but
        the explicit materialization keeps "what's hashed" readable as
        a spec, not a black-box dump). Lives on the aggregate so any
        future field addition forces an explicit decision about whether
        it participates in content identity (anti-hook #10) at the same
        site as the field itself; deciders and drift-detection helpers
        call this rather than re-listing the subset.
        """
        return {
            "name": self.name.value,
            "parameters_schema": self.parameters_schema,
            "capability_id": str(self.capability_id) if self.capability_id is not None else None,
            "needed_family_ids": sorted(str(f) for f in self.needed_family_ids),
            "needed_supplies": sorted(self.needed_supplies),
            "needed_assembly_ids": sorted(str(a) for a in self.needed_assembly_ids),
            # required_roles participates in the content hash so a
            # MethodVersioned event attests to the declared role slots
            # alongside parameters_schema / needed_family_ids / etc.
            # Sort by role_name for byte-stable persistence; each
            # entry materializes as a JSON-friendly dict (role_name,
            # XOR-target as str, sorted required_ports, optional).
            # required_ports inside each role sort by port_name +
            # direction for deterministic serialization.
            #
            # role_kind (Layer 3 sub-slice 3D) is conditionally
            # rendered: only included when non-None. Preserves
            # slice-1 content_hash byte stability for Methods whose
            # RoleRequirements were authored before 3D (no spurious
            # `"role_kind": null` key in the canonical bytes). New
            # role_kind-based RoleRequirements canonically include
            # `role_kind` and omit `family_id` per the XOR
            # invariant.
            "required_roles": sorted(
                (_canonical_role_requirement(role) for role in self.required_roles),
                key=lambda r: str(r["role_name"]),
            ),
        }


def _canonical_role_requirement(role: RoleRequirement) -> dict[str, object]:
    """Canonical JSON-friendly dict for one RoleRequirement.

    Lifted to module scope so the conditional-render rule for
    `role_kind` lives in ONE place. Per [[project-role-aggregate-
    design]] sub-slice 3D content_subset gate: `role_kind` only
    appears in the canonical bytes when non-None, preserving slice-1
    content_hash byte stability for Methods whose required_roles
    were all family_id-based.

    The XOR invariant on RoleRequirement guarantees exactly one of
    role_kind / family_id is set, so the conditional logic here
    cannot produce an ambiguous bytes-shape: a role_kind-based VO
    omits `family_id` (renders null), a family_id-based VO omits
    `role_kind` from the dict entirely.
    """
    body: dict[str, object] = {
        "role_name": role.role_name.value,
        "family_id": str(role.family_id) if role.family_id is not None else None,
        "required_ports": sorted(
            (
                {
                    "port_name": port.port_name,
                    "direction": port.direction.value,
                    "signal_type": port.signal_type,
                }
                for port in role.required_ports
            ),
            key=lambda p: (p["port_name"], p["direction"]),
        ),
        "optional": role.optional,
    }
    if role.role_kind is not None:
        body["role_kind"] = str(role.role_kind)
    return body


class MethodCapabilityExecutorMismatchError(Exception):
    """Method.capability_id points at a Capability whose executor_shapes
    do not include Method (cross-BC guard).

    Mapped to HTTP 409. Surfaces when define_method binds to a
    Capability that only declares ExecutorShape.PROCEDURE.
    """

    def __init__(self, method_id: UUID, capability_id: UUID) -> None:
        super().__init__(
            f"Method {method_id} cannot bind to Capability {capability_id}: "
            "Capability.executor_shapes does not include Method"
        )
        self.method_id = method_id
        self.capability_id = capability_id


class MethodParametersNotSubsetError(ValueError):
    """Method.parameters_schema is not a subset of the bound
    Capability.parameters_schema.

    Mapped to HTTP 409. Raised by `update_method_parameters_schema`'s
    decider when the operator submits a parameters_schema that widens
    the Capability's contract — for example introduces a property the
    Capability doesn't declare, narrows a type, drops a Capability-
    required field, or widens an enum/minimum/maximum/pattern/unit
    constraint. Pinned per STRICT-by-default posture from
    [[project_schema_validated_values_pattern]] +
    [[project_asset_settings_design]] cross-BC anchor.

    `reason` is a descriptive string with the offending JSON Pointer
    so operators can pinpoint the conflict (for example,
    `properties.energy.maximum`).
    """

    def __init__(self, method_id: UUID, capability_id: UUID, reason: str) -> None:
        super().__init__(
            f"Method {method_id} parameters_schema is not a subset of "
            f"Capability {capability_id} parameters_schema: {reason}"
        )
        self.method_id = method_id
        self.capability_id = capability_id
        self.reason = reason
