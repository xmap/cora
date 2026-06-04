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
hoisted to `cora.infrastructure.bounded_text.validate_bounded_text`
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
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from cora.infrastructure.bounded_text import validate_bounded_text

METHOD_NAME_MAX_LENGTH = 200
METHOD_VERSION_TAG_MAX_LENGTH = 50
# needed_supplies element bounds. Mirrors Supply.kind shape
# (cora.supply.aggregates.supply.state.SUPPLY_KIND_MAX_LENGTH = 50)
# so per-element validation in the Method decider stays consistent
# with what Supply itself accepts at register_supply time. See
# [[project_supply_design]] §"Method.needed_supplies consumer"
# for the design lock.
METHOD_NEEDED_SUPPLY_KIND_MAX_LENGTH = 50


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


@dataclass(frozen=True)
class MethodName:
    """Display name for a method. Trimmed; 1-200 chars.

    Eighth occurrence of the trimmed-bounded-name VO pattern. Uses
    the shared `validate_bounded_text` helper (see
    `cora.infrastructure.bounded_text`).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=METHOD_NAME_MAX_LENGTH,
            error_class=InvalidMethodNameError,
        )
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


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
    `cora.infrastructure.json_schema_subset`. See
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
    needed_supplies: frozenset[str] = field(default_factory=frozenset[str])
    # needed_assembly_ids references Assembly aggregates (Equipment BC)
    # by UUID. Declares "this Method needs a specific composition
    # blueprint" (e.g., the MCTOptics microscope fixture), not just N
    # independent Assets of the Families in needed_family_ids. Plan
    # binding consults this set at bind time: each id in
    # Method.needed_assembly_ids must be materialized as a Fixture among
    # the Plan's Assets, where Fixture.assembly_id matches. Affordance-cover (Capability) check is
    # unchanged because Assembly.presents_as_family_id provides the
    # Family-typed unit the Capability binds against. Defaults to empty
    # frozenset (additive-state pattern; legacy MethodDefined-only
    # streams fold cleanly via payload.get default). See
    # [[project-assembly-aggregate-design]] Locks section for the cross-BC
    # contract.
    needed_assembly_ids: frozenset[UUID] = field(default_factory=frozenset[UUID])

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
        }


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
