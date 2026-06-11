"""Plan aggregate state, value objects, status enum, and domain errors.

`Plan` is the recipe ladder's binding layer (ISA-88 Master/Control
Recipe analog). A Plan binds a `Practice` (which itself adapts a
`Method` for a site) to a specific set of `Asset` instances at the
facility. Plan is what `Run` ultimately executes.

Per the BC map's recipe ladder: Method (≈ General Recipe, equipment-
agnostic) → Practice (≈ Site Recipe, facility-localized) → Plan
(≈ Master/Control Recipe, equipment-bound) → Run (≈ batch execution).

## Aggregate scope

Plan state:
  - `id` + `name`
  - `practice_id: UUID` — the Practice this Plan binds (eventual-
    consistency ref; existence verified at handler-load time, not
    in the decider)
  - `asset_ids: frozenset[UUID]` — the Assets this Plan is bound
    to (multi-asset binding; gate-review Q3)
  - `status: PlanStatus` (Defined → Versioned → Deprecated FSM)
  - `version: str | None` — operator-supplied label of the most
    recent `version_plan` call (None until first version)

Field addition follows the additive convention: the `version`
field landed when the first mutating event (`PlanVersioned`)
arrived, not speculatively. Same precedent as Method and Practice.

Audit data captured at bind time (`method_id`, snapshots of the
Method's needed_family_ids and each bound Asset's families)
lives in the `PlanDefined` event payload only — NOT in state.
Slim Aggregate principle (gate-review Q4): state holds only what
future deciders need to validate invariants. version_plan and
deprecate_plan don't re-validate families, so the snapshots
stay payload-only.

Additional facets defer to a later sub-phase if pilot demand emerges:
  - `wiring` (which Asset.ports are connected to what; depends on
    Asset.ports landing first, currently deferred)
  - calibrations
  - per-Plan parameter overrides

## Cross-aggregate validation at bind time (gate-review Q5)

The `define_plan` handler pre-loads Practice, Method (via
`practice.method_id`), and each bound Asset, then hands the loaded
entities to the pure decider as a `PlanBindingContext`. The decider
treats them as opaque domain data and validates:

  - Practice not Deprecated → `PlanBoundPracticeDeprecatedError`
  - Method not Deprecated → `PlanBoundMethodDeprecatedError`
  - No bound Asset is Decommissioned → `PlanAssetDecommissionedError`
  - `union(asset.family_ids) ⊇ method.needed_family_ids` →
    `PlanFamiliesNotSatisfiedError`

Handler-side load misses become `PracticeNotFoundError` /
`MethodNotFoundError` / `AssetNotFoundError` (defined on the
respective aggregates) before reaching the decider. The four
errors above are Plan-domain errors specific to "you tried to bind
to something whose state forbids binding"; they live in this
module.

This is the first decider in the codebase that takes cross-
aggregate state as input. The pattern is documented in
CONTRIBUTING.md as the canonical approach for cross-validating
deciders. Second instance shipped in `start_run` with
`RunStartContext` of the same shape.

## Status as enum-in-state, derived-from-event-type-in-evolver

Same precedent as Method and Practice and Family.
The lifecycle mirrors theirs: Defined → Versioned →
Deprecated. Approval/governance is a separate concern handled by
the future Decision BC with `RecipeApproval` context (gate-review
Q2).

## Tenth bounded-name VO + helper extraction

`PlanName` is the **tenth** bounded-name VO. The Family gate-review
parked extraction at "first per-VO divergence OR ~10 instances".
We hit 10 with no divergence pressure, so the trim+length-check
helper got hoisted to `cora.shared.bounded_text.validate_bounded_text`
(see that module's docstring). PlanName uses the helper from day
one; the prior 9 VOs were refactored in the same hoist commit.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from cora.recipe.aggregates.method import RoleName
from cora.shared.bounded_text import bounded_name

PLAN_NAME_MAX_LENGTH = 200
PLAN_VERSION_TAG_MAX_LENGTH = 50
WIRE_PORT_NAME_MAX_LENGTH = 100  # mirrors PORT_NAME_MAX_LENGTH on AssetPort


class PlanStatus(StrEnum):
    """The Plan's lifecycle state.

    Mirrors Method's and Practice's lifecycle (and Family's).
    Transitions land per-slice:
      - Defined -> Versioned        (version_plan)
      - (Defined | Versioned) -> Deprecated  (deprecate_plan)

    `Defined` is the genesis state set by `define_plan`. The enum
    values are PascalCase strings (matching the BC-map status
    vocabulary) so log lines and DTOs read naturally without
    additional mapping.
    """

    DEFINED = "Defined"
    VERSIONED = "Versioned"
    DEPRECATED = "Deprecated"


class InvalidPlanNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Plan name must be 1-{PLAN_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class PlanAssetsRequiredError(ValueError):
    """A Plan must bind at least one Asset.

    Raised by `define_plan` when the `asset_ids` argument is empty;
    gate-review locked the non-empty asset binding as a domain
    invariant.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Plan asset binding invalid: {reason}")
        self.reason = reason


class PlanAlreadyExistsError(Exception):
    """Attempted to define a plan whose stream already has events."""

    def __init__(self, plan_id: UUID) -> None:
        super().__init__(f"Plan {plan_id} already exists")
        self.plan_id = plan_id


class PlanNotFoundError(Exception):
    """Attempted an operation on a plan whose stream has no events."""

    def __init__(self, plan_id: UUID) -> None:
        super().__init__(f"Plan {plan_id} not found")
        self.plan_id = plan_id


class PlanBoundPracticeDeprecatedError(Exception):
    """Attempted to bind a Plan to a Deprecated Practice.

    Per gate-review Q5: Practice/Method deprecation is advisory at
    the inner layer (Practice itself doesn't reject operations when
    deprecated), but Plan binding rejects deprecated upstream
    recipes — you can't make a new binding against a tombstoned
    template. Mapped to HTTP 409 (state-conflict family).
    """

    def __init__(self, practice_id: UUID) -> None:
        super().__init__(f"Cannot bind Plan to Practice {practice_id}: Practice is Deprecated")
        self.practice_id = practice_id


class PlanBoundMethodDeprecatedError(Exception):
    """Attempted to bind a Plan whose Practice references a Deprecated Method.

    Mirrors `PlanBoundPracticeDeprecatedError` shape. Mapped to HTTP 409.
    """

    def __init__(self, method_id: UUID) -> None:
        super().__init__(f"Cannot bind Plan to Method {method_id}: Method is Deprecated")
        self.method_id = method_id


class PlanAssetDecommissionedError(Exception):
    """Attempted to bind a Plan to one or more Decommissioned Assets.

    Plans are forward-looking bindings; binding to a decommissioned
    Asset is structurally inconsistent (the Asset cannot be
    re-activated from Decommissioned per the Asset FSM). Carries
    the list of offending asset_ids for diagnostics. Mapped to HTTP 409.
    """

    def __init__(self, asset_ids: list[UUID]) -> None:
        super().__init__(
            f"Cannot bind Plan: the following Assets are Decommissioned: "
            f"{[str(a) for a in asset_ids]}"
        )
        self.asset_ids = asset_ids


class PlanCannotVersionError(Exception):
    """Attempted to version a plan not in `Defined` or `Versioned`.

    Multi-source guard: `version_plan` accepts both `Defined` (first
    revision) and `Versioned` (subsequent revisions — operators bump
    v1 → v2 → v3 over time). Only `Deprecated` is rejected (you
    can't revise a deprecated plan).

    Per-transition error class — same naming convention as
    `MethodCannotVersionError` (Recipe BC), `PracticeCannotVersionError`
    (Recipe BC), `FamilyCannotVersionError` (Equipment BC).
    Mapped to HTTP 409.
    """

    def __init__(self, plan_id: UUID, current_status: "PlanStatus") -> None:
        super().__init__(
            f"Plan {plan_id} cannot be versioned: currently in status "
            f"{current_status.value}, version requires "
            f"{PlanStatus.DEFINED.value} or {PlanStatus.VERSIONED.value}"
        )
        self.plan_id = plan_id
        self.current_status = current_status


class PlanCannotDeprecateError(Exception):
    """Attempted to deprecate a plan not in `Defined` or `Versioned`.

    Multi-source guard. Re-deprecating an already-`Deprecated` plan
    raises (strict-not-idempotent). Mirrors
    `PracticeCannotDeprecateError` / `MethodCannotDeprecateError`
    shape. Mapped to HTTP 409.
    """

    def __init__(self, plan_id: UUID, current_status: "PlanStatus") -> None:
        super().__init__(
            f"Plan {plan_id} cannot be deprecated: currently in status "
            f"{current_status.value}, deprecate requires "
            f"{PlanStatus.DEFINED.value} or {PlanStatus.VERSIONED.value}"
        )
        self.plan_id = plan_id
        self.current_status = current_status


class InvalidPlanDefaultParametersError(ValueError):
    """The supplied Plan default_parameters dict failed validation
    against the owning Method's parameters_schema.

    Strict when Method.parameters_schema is None: non-empty defaults
    are rejected (Method declares no contract; operators wanting
    parameter-less Methods declare `parameters_schema={}` explicitly).
    When the schema IS declared, the merged defaults must conform per
    jsonschema-rs Draft 2020-12. Mapped to HTTP 400 by the recipe BC's
    exception handler. Mirrors the Asset.settings "no Capabilities + non-empty
    settings → reject" cross-BC anchor; see
    [[project_schema_validated_values_pattern]].
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Plan default_parameters: {reason}")
        self.reason = reason


class InvalidPlanVersionTagError(ValueError):
    """The supplied version tag is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error so direct in-process
    callers (sagas, tests) get the same protection. Same precedent as
    InvalidPracticeVersionTagError / InvalidMethodVersionTagError /
    InvalidFamilyVersionTagError. Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Plan version tag must be 1-{PLAN_VERSION_TAG_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


class PlanFamiliesNotSatisfiedError(Exception):
    """The bound Assets' families don't cover the Method's needs.

    Carries the missing family ids — those required by the
    Method but not present in any bound Asset's `family_ids`.
    Mapped to HTTP 409 (state-conflict family; the binding is
    structurally invalid given current Asset state).

    Per gate-review Q3: check is on each bound Asset's OWN
    family_ids (no hierarchy traversal). Operators model
    Asset.family_ids at whatever granularity makes sense (Assembly
    level for composed devices, Device level for leaves) and bind
    the Assets that actually carry the needed families.
    """

    def __init__(self, missing_family_ids: frozenset[UUID]) -> None:
        super().__init__(
            f"Plan families not satisfied: bound Assets are missing "
            f"families {sorted(str(c) for c in missing_family_ids)}"
        )
        self.missing_family_ids = missing_family_ids


class PlanAffordancesNotSatisfiedError(Exception):
    """The bound Assets' Family.affordances don't cover the
    Method.capability.required_affordances contract.

    Cross-BC affordance-cover guard. Layered on top of the
    family-id check (PlanFamiliesNotSatisfiedError): even when
    every needed Family is present, the union of those Families'
    `affordances` must still cover the bound Method's
    `capability.required_affordances` contract. Mapped to HTTP 409
    (same state-conflict family as the prior check).

    Carries the missing affordances as a sorted tuple of their
    string values (Affordance is a StrEnum) so the diagnostic is
    stable across runs and human-readable in HTTP responses.

    Skipped entirely when Method has no `capability_id` (additive
    transition window). The strict mode will REQUIRE capability_id on
    DefineMethod per Pattern P, at which point this guard always runs.
    """

    def __init__(self, missing_affordances: frozenset[str]) -> None:
        super().__init__(
            f"Plan affordances not satisfied: bound Assets' Family.affordances "
            f"miss {sorted(missing_affordances)}"
        )
        self.missing_affordances = missing_affordances


@bounded_name(max_length=PLAN_NAME_MAX_LENGTH, error_class=InvalidPlanNameError)
@dataclass(frozen=True)
class PlanName:
    """Display name for a plan. Trimmed; 1-200 chars.

    Tenth occurrence of the trimmed-bounded-name VO pattern. Uses
    the shared `bounded_name` decorator (see
    `cora.shared.bounded_text`). The decorator preserves per-VO
    distinctness (separate frozen dataclass type, separate error
    class) while removing the trim+length-check duplication that
    had accumulated across 10 aggregates.
    """

    value: str


@dataclass(frozen=True)
class Plan:
    """Aggregate root: a Practice bound to specific Asset instances.

    `practice_id` is the Practice this Plan binds (eventual-
    consistency ref). `asset_ids` is the set of Assets this Plan
    binds (multi-asset; at least one required, validated at decide
    time). `status` defaults to `Defined`.

    `version` is the operator-supplied label of the most recent
    `version_plan` call (None until first version). State always
    holds the latest tag — past tags live in the event stream as
    `PlanVersioned` events. No `current_` prefix because state by
    definition holds current values (same convention as `status`,
    `name`). Free-text validated at API boundary + defensively in
    the decider; no VO. Default None keeps legacy PlanDefined-
    only streams folding cleanly (additive-state pattern). Mirrors
    Method/Practice/Family `version` semantics: preserved across
    deprecation as an audit signal of the last revision before
    deprecation.

    `method_id` is the Method ultimately implemented by this Plan
    (originally captured in PlanDefined.method_id payload as audit-
    only data; promoted to state because the
    `update_plan_default_parameters` decider needs it to look up
    `Method.parameters_schema` for validation). Legacy PlanDefined
    streams fold cleanly: the evolver reads `method_id` from the
    payload field that was present from day one. Default-defaults to
    a sentinel via the constructor; in practice every well-formed
    stream sets it explicitly via PlanDefined. Mirrors the
    "state holds what future deciders need" precedent in the
    docstring above.

    `default_parameters: dict[str, Any]` is the
    operator-set defaults for parameters that downstream Runs
    merge with their per-run overrides. Validated against
    the owning Method's `parameters_schema` at decide time
    (STRICT when Method declares no schema: non-empty defaults
    rejected; operators wanting "no parameters" Methods declare
    `parameters_schema={}` explicitly. Mirrors Asset.settings's
    "no Capabilities + non-empty settings → reject" anchor; see
    [[project_run_parameters_design]] §audit-correction).
    Defaults to empty dict for legacy Plans (additive-state pattern).
    The full dict is persisted; PATCH semantics handled by the slice
    via RFC 7396 `merge_patch`. Mirrors `Asset.settings` shape.

    `wires: frozenset[Wire]` is the typed graph of port-
    to-port connections between bound Assets. Each `Wire` carries
    a 4-tuple identifying source/target ports across two Assets.
    Mutated via `add_plan_wire` / `remove_plan_wire` slices (mirrors
    Asset.ports's add/remove_asset_port pattern). Direction is enforced
    (source=OUTPUT, target=INPUT), `signal_type` must match exactly,
    fan-out allowed (one source port → many target ports), fan-in
    forbidden (one target port = at most one incoming Wire). See
    [[project_plan_wiring_design]] for the locked design memo.
    Defaults to empty frozenset for legacy Plans (additive-state
    pattern).

    `content_hash: str | None` is the SHA-256 (64-char lowercase hex)
    of the canonical body bytes for this Plan revision's content
    subset (`name + method_id + practice_id + asset_ids +
    default_parameters + wires`), captured by the version_plan
    decider per the non-determinism principle and folded by the
    evolver from MethodVersioned PlanVersioned event payloads. None
    for legacy Plans that never reached Versioned status and for
    pre-rollout PlanVersioned events that landed before the
    content-hash field was added (additive-state pattern per
    [[project_content_addressed_identity_design]]).

    PRESERVATION semantics across non-version transitions:
      - PlanDeprecated preserves content_hash (the hash represents
        the LAST ATTESTED revision and stays a valid equivalence
        anchor for the deprecated binding).
      - PlanDefaultParametersUpdated preserves content_hash (Bazel
        input/output split semantics: schema-side updates between
        Versioned events leave the hash pointing at the prior
        attested revision; the drift between current
        default_parameters and the hashed snapshot IS the intended
        signal that the Plan has uncommitted changes).
      - PlanWireAdded / PlanWireRemoved preserve content_hash (same
        Bazel input/output split rationale: wiring is a
        content-bearing field, so changes between Versioned events
        leave the hash dangling against the prior revision; operators
        re-version to anchor a new hash).
    """

    id: UUID
    name: PlanName
    practice_id: UUID
    asset_ids: frozenset[UUID]
    status: PlanStatus = PlanStatus.DEFINED
    version: str | None = None
    method_id: UUID | None = None
    default_parameters: dict[str, Any] = field(default_factory=dict[str, Any])
    wires: frozenset["Wire"] = field(default_factory=frozenset["Wire"])
    content_hash: str | None = None
    # role_bindings declares which Asset fills each of the bound
    # Method's required_roles (positional role-tagging; IEC 81346
    # Function aspect). Each `RoleBinding` is a (role_name,
    # asset_id) pair; uniqueness within the set is keyed on role_name
    # (enforced by the bind_plan_role decider, not the VO). The
    # role_name links to a `RoleRequirement` declared on the Plan's
    # Method (state.method_id). Empty by default; legacy PlanDefined-
    # only streams fold cleanly via the additive-state pattern. See
    # [[project-plan-role-bindings-design]] for the full design lock
    # and [[project-method-required-roles-design]] for the upstream
    # vocabulary.
    role_bindings: frozenset["RoleBinding"] = field(default_factory=frozenset["RoleBinding"])

    def content_subset(self) -> dict[str, object]:
        """Canonical content subset hashed into PlanVersioned.content_hash.

        Pins identity per [[project_content_addressed_identity_design]]:
        `name + method_id + practice_id + asset_ids + default_parameters
        + wires`. Excluded: `id` (identity, not content); `status` and
        `version` (lifecycle, derived in evolver from event type and
        version_tag); `content_hash` itself (a Plan's content cannot
        contain its own hash). UUIDs render as strings (json-serializable),
        frozensets render as sorted lists (canonical_body_bytes would sort
        either way but explicit materialization keeps the subset readable
        as a spec). Wires render as sorted 4-tuples-of-strings to give
        determinism over the rendered tuple form (anti-hook #12). method_id
        is Optional in state (additive-state default for legacy Plans) but
        always concrete for any Plan that has reached Versioned status,
        because PlanDefined carries it; rendered as None when absent.
        Lives on the aggregate so any future field addition forces an
        explicit decision about whether it participates in content
        identity (anti-hook #10) at the same site as the field itself.
        """
        return {
            "name": self.name.value,
            "method_id": str(self.method_id) if self.method_id is not None else None,
            "practice_id": str(self.practice_id),
            "asset_ids": sorted(str(a) for a in self.asset_ids),
            "default_parameters": self.default_parameters,
            "wires": sorted(
                (
                    str(w.source_asset_id),
                    w.source_port_name,
                    str(w.target_asset_id),
                    w.target_port_name,
                )
                for w in self.wires
            ),
            # role_bindings participates in content identity:
            # rendered as a sorted list of (role_name, asset_id)
            # tuples for byte-stable serialization (matches the wires
            # sort convention).
            "role_bindings": sorted(
                (b.role_name.value, str(b.asset_id)) for b in self.role_bindings
            ),
        }


class InvalidWireError(ValueError):
    """A Wire's source / target port name is empty, whitespace-only,
    or exceeds the configured max length after trimming.

    Mirrors `InvalidAssetPortNameError`. Mapped to HTTP 400 by
    the recipe BC's exception handler. Validation runs in the Wire
    VO's `__post_init__` so the route's Pydantic body keeps these
    to 422 by catching them at the boundary; deciders raise this
    when they construct a Wire from operator-supplied components.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Wire port name must be 1-{WIRE_PORT_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class Wire:
    """A typed port-to-port connection between two bound Assets.

    Tuple `(source_asset_id, source_port_name, target_asset_id,
    target_port_name)` describes one connection. The 4-tuple IS the
    identity; `frozenset[Wire]` deduplicates on the tuple.

    `source` / `target` labels match OPC UA SourceNode/TargetNode
    + Argo Workflows dependency direction (clearer than `from`/`to`,
    avoids collision with `PortDirection.{INPUT, OUTPUT}` that the
    `out`/`in` labels would create).

    Validation rules enforced at the decider level (NOT here):
      - source port must have `direction=OUTPUT`
      - target port must have `direction=INPUT`
      - `source_port.signal_type == target_port.signal_type` (exact match)
      - both endpoint asset_ids must be in the Plan's `asset_ids` set
      - both endpoint port_names must exist on their respective Asset.ports
      - target port can be the destination of at most one Wire (fan-in
        forbidden); fan-out (one source → many targets) is allowed
      - self-loops allowed iff `source_port_name != target_port_name`

    `__post_init__` validates only structural shape (port-name lengths
    + canonicalization via trim); the cross-aggregate validations
    above need a `PlanWireContext` and live in the slice deciders.

    See [[project_plan_wiring_design]] for the locked design memo.
    """

    source_asset_id: UUID
    source_port_name: str
    target_asset_id: UUID
    target_port_name: str

    def __post_init__(self) -> None:
        trimmed_source = self.source_port_name.strip()
        if not trimmed_source or len(trimmed_source) > WIRE_PORT_NAME_MAX_LENGTH:
            raise InvalidWireError(self.source_port_name)
        trimmed_target = self.target_port_name.strip()
        if not trimmed_target or len(trimmed_target) > WIRE_PORT_NAME_MAX_LENGTH:
            raise InvalidWireError(self.target_port_name)
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install canonicalized names.
        object.__setattr__(self, "source_port_name", trimmed_source)
        object.__setattr__(self, "target_port_name", trimmed_target)


class PlanWireAlreadyExistsError(Exception):
    """Attempted to add a Wire that's already in the Plan's wire set.

    Strict-not-idempotent (mirrors AssetPort `add_asset_port`). Mapped to
    HTTP 409. Operators get clear feedback rather than a silent
    no-op so re-running a partially-applied template surface the
    duplicate.
    """

    def __init__(self, wire: Wire) -> None:
        super().__init__(
            f"Wire {_wire_diagnostic(wire)} is already in this Plan's wire set "
            "(strict-not-idempotent; remove the existing wire first if you mean "
            "to replace it)"
        )
        self.wire = wire


class PlanWireNotFoundError(Exception):
    """Attempted to remove a Wire that's not in the Plan's wire set.

    Strict-not-idempotent (symmetric with `PlanWireAlreadyExistsError`).
    Mapped to HTTP 404 (the target resource — this specific Wire — is
    not in the collection).
    """

    def __init__(self, wire: Wire) -> None:
        super().__init__(
            f"Wire {_wire_diagnostic(wire)} is not in this Plan's wire set "
            "(strict-not-idempotent; cannot remove a wire that does not exist)"
        )
        self.wire = wire


class PlanWireTargetAlreadyConnectedError(Exception):
    """The target port is already wired (fan-in is forbidden).

    Each `(target_asset_id, target_port_name)` pair can be the
    destination of at most one Wire (consensus across IEC 61131-3,
    IEC 61499 data arcs, PandABox mux, areaDetector NDArrayPort).
    Carries the existing Wire so operators can see what blocks the
    new add. Mapped to HTTP 409.

    Policy not physics: when fan-in is genuinely needed, introduce
    a `Combiner` Family Asset with N inputs + 1 output and wire
    through it. See [[project_plan_wiring_design]].
    """

    def __init__(self, attempted: Wire, existing: Wire) -> None:
        super().__init__(
            f"Cannot add wire {_wire_diagnostic(attempted)}: target port is "
            f"already wired by {_wire_diagnostic(existing)} (fan-in forbidden)"
        )
        self.attempted = attempted
        self.existing = existing


class PlanWireAssetNotBoundError(Exception):
    """A Wire references an Asset that's not in the Plan's `asset_ids` set.

    Both endpoints of every Wire MUST reference Assets bound by the
    Plan. Carries the offending asset_ids for diagnostics. Mapped
    to HTTP 409 (state-conflict family; the wire is structurally
    invalid given current Plan binding).
    """

    def __init__(self, wire: Wire, missing_asset_ids: list[UUID]) -> None:
        super().__init__(
            f"Cannot add wire {_wire_diagnostic(wire)}: the following endpoint "
            f"Assets are not bound by this Plan: "
            f"{[str(a) for a in missing_asset_ids]} (bind the Asset first via "
            "Plan re-definition, OR pick an Asset already bound)"
        )
        self.wire = wire
        self.missing_asset_ids = missing_asset_ids


class PlanWirePortNotFoundError(Exception):
    """A Wire references a port name that doesn't exist on its endpoint Asset.

    Strict forward-reference: Plan.wires rejects if either endpoint
    port doesn't currently exist on the bound Asset. Operators must
    add the port to the Asset via `add_asset_port` BEFORE wiring
    against it. The same dependency-aware ordering applies to
    removal: remove the wire BEFORE removing the port (PostgreSQL FK
    shape; see [[project_plan_wiring_design]] §hot-swap procedure).

    Carries the offending port references as `(asset_id, port_name,
    direction_role)` triples where `direction_role` is "source" or
    "target". Mapped to HTTP 409.
    """

    def __init__(self, wire: Wire, missing: list[tuple[UUID, str, str]]) -> None:
        details = ", ".join(
            f"{role}={asset_id}:{port_name!r}" for asset_id, port_name, role in missing
        )
        super().__init__(
            f"Cannot add wire {_wire_diagnostic(wire)}: the following port "
            f"references don't exist on their endpoint Assets: {details} "
            "(add the port to the Asset first via add_asset_port, OR pick "
            "a port already declared)"
        )
        self.wire = wire
        self.missing = missing


class PlanWireDirectionMismatchError(Exception):
    """A Wire's source port is not OUTPUT, or its target port is not INPUT.

    Direction is enforced (universal across IEC 61131-3, IEC 61499,
    SysML, PandABox, EPICS, NiFi, LabVIEW). Carries the actual
    directions seen for diagnostics. Mapped to HTTP 409.
    """

    def __init__(
        self,
        wire: Wire,
        actual_source_direction: str,
        actual_target_direction: str,
    ) -> None:
        super().__init__(
            f"Cannot add wire {_wire_diagnostic(wire)}: source must be "
            f"OUTPUT (got {actual_source_direction!r}), target must be "
            f"INPUT (got {actual_target_direction!r})"
        )
        self.wire = wire
        self.actual_source_direction = actual_source_direction
        self.actual_target_direction = actual_target_direction


class PlanWireSignalTypeMismatchError(Exception):
    """A Wire's source and target ports have different `signal_type` values.

    Exact-match required (matches IEC 61131-3 wire-type rules and
    LabVIEW G's broken-wire-on-mismatch). Carries both signal_types
    for diagnostics. Mapped to HTTP 409. If conversion is needed,
    add an explicit "converter" Asset; do not bake coercion into
    wire validation.
    """

    def __init__(
        self,
        wire: Wire,
        source_signal_type: str,
        target_signal_type: str,
    ) -> None:
        super().__init__(
            f"Cannot add wire {_wire_diagnostic(wire)}: source signal_type "
            f"{source_signal_type!r} does not match target signal_type "
            f"{target_signal_type!r} (exact match required)"
        )
        self.wire = wire
        self.source_signal_type = source_signal_type
        self.target_signal_type = target_signal_type


class PlanPseudoAxisArityMismatchError(Exception):
    """A PseudoAxis Asset has a wire count that disagrees with the rule arity.

    The count of incoming wires targeting the PseudoAxis Asset's INPUT
    ports must equal the constituent arity declared by its
    `partition_rule`. `Affine` and `LookupTable` declare 1. `Aggregation`
    and `CompositePartition` declare the rule's `constituent_count`.
    `SolverReference` declares no arity (the external solver owns the
    kinematics signature) and is exempt from this check.

    Raised by the Plan-bind fan-out validator after a candidate wire is
    accepted as structurally valid; rejection here means the new wire
    would leave the PseudoAxis Asset under- or over-wired against its
    own partition rule. Mapped to HTTP 409.
    """

    def __init__(
        self,
        pseudoaxis_asset_id: UUID,
        expected_constituent_count: int,
        actual_input_wire_count: int,
        rule_kind: str,
    ) -> None:
        super().__init__(
            f"PseudoAxis Asset {pseudoaxis_asset_id} has "
            f"{actual_input_wire_count} incoming wire(s) on its INPUT ports "
            f"but its {rule_kind} partition rule expects "
            f"{expected_constituent_count} constituent(s) "
            "(add or remove wires until counts match, OR update the "
            "partition rule to a different arity)"
        )
        self.pseudoaxis_asset_id = pseudoaxis_asset_id
        self.expected_constituent_count = expected_constituent_count
        self.actual_input_wire_count = actual_input_wire_count
        self.rule_kind = rule_kind


class PlanPseudoAxisFanoutSignalTypeMismatchError(Exception):
    """A PseudoAxis Asset receives wires carrying more than one signal_type.

    All constituents feeding a single PseudoAxis Asset's INPUT ports must
    share the same source-side `signal_type` so the partition rule
    operates over a single dimensional intent. Mixed types (for example
    "mm" and "deg" sources fanning into one Aggregation rule) indicate
    operator error at Plan-bind time, not a soft warning.

    Carries the full set of distinct signal_types observed on the
    incoming wires so the operator can see the diversity at a glance.
    Mapped to HTTP 409.
    """

    def __init__(
        self,
        pseudoaxis_asset_id: UUID,
        signal_types: frozenset[str],
        rule_kind: str,
    ) -> None:
        rendered = sorted(signal_types)
        super().__init__(
            f"PseudoAxis Asset {pseudoaxis_asset_id} receives wires whose "
            f"source ports carry mixed signal_types {rendered!r} under its "
            f"{rule_kind} partition rule (all constituents must share one "
            "signal_type; reconcile source ports or pick consistent "
            "constituents)"
        )
        self.pseudoaxis_asset_id = pseudoaxis_asset_id
        self.signal_types = signal_types
        self.rule_kind = rule_kind


class PlanPseudoAxisOutputCardinalityError(Exception):
    """A PseudoAxis Asset has a non-one OUTPUT-direction port count.

    PseudoAxis is a virtual axis with exactly one virtual output by
    design (the partition rule decomposes ONE commanded value into N
    constituent setpoints). Operators registering 0 or >= 2 OUTPUT ports
    on a PseudoAxis Asset have a structural mismatch between port
    declaration and Family semantics; the Plan-bind validator surfaces
    it here so the violation is caught before any Run starts. Mapped to
    HTTP 409.
    """

    def __init__(
        self,
        pseudoaxis_asset_id: UUID,
        output_port_count: int,
    ) -> None:
        super().__init__(
            f"PseudoAxis Asset {pseudoaxis_asset_id} declares "
            f"{output_port_count} OUTPUT port(s) but PseudoAxis Assets MUST "
            "declare exactly 1 OUTPUT port (the virtual axis output); "
            "reconcile the port declarations on the Asset"
        )
        self.pseudoaxis_asset_id = pseudoaxis_asset_id
        self.output_port_count = output_port_count


class PlanWireSelfLoopError(Exception):
    """A Wire connects a port to itself (same asset_id AND same port_name).

    Self-loops between DIFFERENT ports on the same Asset are allowed
    (PandABox LUT block self-feedback pattern). Self-loops where
    source and target ports are identical are rejected as a
    degenerate case.
    """

    def __init__(self, wire: Wire) -> None:
        super().__init__(
            f"Cannot add wire {_wire_diagnostic(wire)}: source and target "
            "are the same port (self-loops on a single port are degenerate; "
            "use two distinct ports on the same Asset for legitimate "
            "feedback patterns)"
        )
        self.wire = wire


def _wire_diagnostic(wire: Wire) -> str:
    """Compact human-readable Wire renderer for error messages."""
    return (
        f"({wire.source_asset_id}:{wire.source_port_name!r} -> "
        f"{wire.target_asset_id}:{wire.target_port_name!r})"
    )


# ---------- role_bindings (Plan-side positional role-tagging) ----------


@dataclass(frozen=True)
class RoleBinding:
    """A binding from a Method.required_role's name to a specific Asset.

    Tuple `(role_name, asset_id)`. The role_name references a
    `RoleRequirement` declared on the Plan's Method (state.method_id);
    the asset_id MUST be one of the Plan's bound asset_ids. The
    `bind_plan_role` decider enforces both invariants plus port-coverage
    against the role's required_ports. See
    [[project-plan-role-bindings-design]] for the lock.

    Identity within `Plan.role_bindings` is structural via tuple
    equality; uniqueness of `role_name` is enforced at the decider
    (not the VO), so two RoleBindings with the same role_name pointing
    at different assets would collide structurally only if their
    asset_ids matched too. The decider's strict-not-idempotent guard
    catches the role_name-collision case before that ambiguity matters.
    """

    role_name: RoleName
    asset_id: UUID


class PlanRoleAlreadyBoundError(Exception):
    """Attempted to bind a role_name that's already in the Plan's role_bindings.

    Strict-not-idempotent: same precedent as
    `PlanWireAlreadyExistsError` and
    `MethodRoleNameAlreadyDeclaredError`. The diagnostic carries the
    Plan id and the offending role_name.
    """

    def __init__(self, plan_id: UUID, role_name: "RoleName") -> None:
        super().__init__(
            f"Plan {plan_id} already binds role {role_name.value!r}; "
            "bind_plan_role is strict-not-idempotent (unbind first if "
            "you mean to rebind)"
        )
        self.plan_id = plan_id
        self.role_name = role_name


class PlanRoleNotBoundError(Exception):
    """Attempted to unbind a role_name that isn't in the Plan's role_bindings.

    Strict-not-idempotent: a second unbind raises rather than silently
    no-opping. Operators wire freely before binding; `add_plan_wire`
    does NOT raise this error when the role is unbound (the wire stands
    on its own port-shape validity). The role-table-vs-wire-graph
    closure lives in `bind_plan_role.decide`, which scans
    `state.wires` and rejects a bind that would diverge from an existing
    wire's endpoint Asset (raises `PlanWireRoleEndpointMismatchError`,
    not this class).

    Mapped to HTTP 409.
    """

    def __init__(self, plan_id: UUID, role_name: "RoleName") -> None:
        super().__init__(
            f"Plan {plan_id} does not bind role {role_name.value!r}; nothing to unbind"
        )
        self.plan_id = plan_id
        self.role_name = role_name


class PlanRoleNameNotDeclaredError(Exception):
    """Attempted to bind a role_name that isn't declared on the Plan's
    Method's required_roles.

    Plan.role_bindings entries MUST correspond to a `RoleRequirement`
    declared on `Method.required_roles`. Operator typos or stale role
    names surface here at the bind boundary. Mapped to HTTP 409.
    """

    def __init__(self, plan_id: UUID, method_id: UUID, role_name: "RoleName") -> None:
        super().__init__(
            f"Plan {plan_id} cannot bind role {role_name.value!r}: that role "
            f"is not declared on Method {method_id}'s required_roles "
            "(declare the role on the Method first via "
            "add_method_required_role, OR bind a role that exists)"
        )
        self.plan_id = plan_id
        self.method_id = method_id
        self.role_name = role_name


class PlanRoleAssetNotBoundError(Exception):
    """Attempted to bind a role to an Asset that isn't in the Plan's asset_ids.

    Mirror of `PlanWireAssetNotBoundError` for the role-binding side:
    every RoleBinding's asset_id MUST be in Plan.asset_ids. Carries
    both the role_name and the offending asset_id.
    """

    def __init__(self, plan_id: UUID, role_name: "RoleName", asset_id: UUID) -> None:
        super().__init__(
            f"Plan {plan_id} cannot bind role {role_name.value!r} to "
            f"Asset {asset_id}: that Asset is not in the Plan's asset_ids "
            "(bind the Asset first via Plan re-definition, OR pick an "
            "Asset already bound)"
        )
        self.plan_id = plan_id
        self.role_name = role_name
        self.asset_id = asset_id


class PlanRoleFamilyMismatchError(Exception):
    """The Asset bound to a role does not carry the role's required Family.

    The `RoleRequirement` on Method.required_roles declares which
    Family the bound Asset must satisfy. At bind time the decider
    loads the Asset and checks that `role.family_id in asset.family_ids`.
    Mapped to HTTP 409. Diagnostic carries the Plan, role, asset, and
    both Family sets for operator clarity.
    """

    def __init__(
        self,
        plan_id: UUID,
        role_name: "RoleName",
        asset_id: UUID,
        required_family_id: UUID,
        asset_family_ids: frozenset[UUID],
    ) -> None:
        super().__init__(
            f"Plan {plan_id} cannot bind role {role_name.value!r} to "
            f"Asset {asset_id}: role requires Family {required_family_id} "
            f"but Asset.family_ids = {sorted(str(f) for f in asset_family_ids)} "
            "(pick an Asset that carries the required Family, OR update "
            "the role's required Family on the Method)"
        )
        self.plan_id = plan_id
        self.role_name = role_name
        self.asset_id = asset_id
        self.required_family_id = required_family_id
        self.asset_family_ids = asset_family_ids


class PlanRoleFamilyNotResolvableError(Exception):
    """One of the bound Asset's family_ids does not resolve to a Family stream.

    Layer 3 sub-slice 3D: when `bind_plan_role` follows the role_kind
    path, the handler walks `Asset.family_ids` through
    `FamilyLookup.lookup` to gather candidate Family rows. A None
    result signals a stale or missing Family projection row, which
    is a load-side integrity problem rather than an operator authoring
    fault. Mapped to HTTP 409 (the role binding cannot be evaluated;
    the operator must fix the Family stream or pick a different Asset).
    """

    def __init__(
        self,
        plan_id: UUID,
        role_name: "RoleName",
        asset_id: UUID,
        missing_family_id: UUID,
    ) -> None:
        super().__init__(
            f"Plan {plan_id} cannot bind role {role_name.value!r} to "
            f"Asset {asset_id}: Family {missing_family_id} (on the "
            "Asset's family_ids) does not resolve via FamilyLookup "
            "(stale projection or unknown Family). Investigate the "
            "Family stream before retrying."
        )
        self.plan_id = plan_id
        self.role_name = role_name
        self.asset_id = asset_id
        self.missing_family_id = missing_family_id


class PlanRoleAssetCannotPresentError(Exception):
    """No Family on the bound Asset advertises the required Role contract.

    Layer 3 sub-slice 3D, ANY-single-family disjunction per Lock 17:
    the role_kind-path satisfaction check walks `Asset.family_ids` and
    accepts iff AT LEAST ONE Family both (a) declares `role_kind` in
    its `presents_as` AND (b) has `affordances` superset
    `Role.required_affordances`. If no single Family satisfies BOTH,
    this fires.

    Mapped to HTTP 409. Diagnostic carries the role, the Asset's
    Family ids, and the required Role's id so the operator can
    diagnose whether to widen Family.presents_as / Family.affordances
    or pick a different Asset.
    """

    def __init__(
        self,
        plan_id: UUID,
        role_name: "RoleName",
        asset_id: UUID,
        role_kind: UUID,
        asset_family_ids: frozenset[UUID],
    ) -> None:
        super().__init__(
            f"Plan {plan_id} cannot bind role {role_name.value!r} to "
            f"Asset {asset_id}: no Family on the Asset advertises Role "
            f"{role_kind} via presents_as with covering affordances. "
            f"Asset.family_ids = {sorted(str(f) for f in asset_family_ids)}; "
            "either add the Role to a Family's presents_as (and widen "
            "its affordances if needed) or pick an Asset whose Families "
            "already advertise the Role."
        )
        self.plan_id = plan_id
        self.role_name = role_name
        self.asset_id = asset_id
        self.role_kind = role_kind
        self.asset_family_ids = asset_family_ids


class PlanRolePortCoverageNotSatisfiedError(Exception):
    """The Asset bound to a role does not expose all of the role's
    required_ports.

    For each `PortRequirement` in `RoleRequirement.required_ports`,
    the bound Asset's `ports` set MUST contain a matching
    `(port_name, direction, signal_type)` triple. Strict exact match.
    Mapped to HTTP 409. Diagnostic carries the missing port triples
    so the operator can either add ports to the Asset or pick a
    different Asset.
    """

    def __init__(
        self,
        plan_id: UUID,
        role_name: "RoleName",
        asset_id: UUID,
        missing_ports: list[tuple[str, str, str]],
    ) -> None:
        details = ", ".join(
            f"({pname!r}, {direction}, {stype!r})" for pname, direction, stype in missing_ports
        )
        super().__init__(
            f"Plan {plan_id} cannot bind role {role_name.value!r} to "
            f"Asset {asset_id}: Asset does not expose the following "
            f"required port triples: {details} (add the missing ports "
            "via add_asset_port, OR pick an Asset that already exposes "
            "them)"
        )
        self.plan_id = plan_id
        self.role_name = role_name
        self.asset_id = asset_id
        self.missing_ports = missing_ports


class PlanWireRoleEndpointMismatchError(Exception):
    """A candidate Wire references a port that is named in a
    `RoleRequirement.required_ports` entry, but the wire's endpoint
    Asset does not match the Asset bound to that role.

    This is the structural closure that prevents the role-table and
    the wire-graph from diverging silently. Without it, an operator
    could bind role=DETECTOR to Camera-A while wiring Camera-B's
    image_out port into the primary-detector sink; both would pass
    validation, and the executor (which reads from the wire graph)
    would silently use Camera-B as the detector while role_bindings
    claims Camera-A. See [[project-plan-role-bindings-design]] for
    the rationale.

    Mapped to HTTP 409. Diagnostic carries the offending wire endpoint
    (source or target), the role whose port it claims, and the
    expected vs actual asset_ids.
    """

    def __init__(
        self,
        plan_id: UUID,
        wire: Wire,
        role_name: "RoleName",
        endpoint_role: str,
        expected_asset_id: UUID,
        actual_asset_id: UUID,
    ) -> None:
        super().__init__(
            f"Plan {plan_id} cannot add wire {_wire_diagnostic(wire)}: "
            f"the {endpoint_role} port matches role "
            f"{role_name.value!r}'s required_ports, but that role is "
            f"bound to Asset {expected_asset_id}, not the wire's "
            f"{endpoint_role} Asset {actual_asset_id} "
            "(rebind the role to match the wire, OR pick a wire that "
            "terminates at the role's bound Asset)"
        )
        self.plan_id = plan_id
        self.wire = wire
        self.role_name = role_name
        self.endpoint_role = endpoint_role
        self.expected_asset_id = expected_asset_id
        self.actual_asset_id = actual_asset_id


class PlanCannotMutateRoleBindingsError(Exception):
    """Attempted to bind / unbind a role on a Plan not in `Defined` status.

    Mirrors `MethodCannotMutateRequiredRolesError`.
    Versioned Plans have an attested content_hash that covers
    role_bindings; Deprecated Plans are out of use entirely. Mapped to
    HTTP 409. Symmetric across `bind_plan_role` and `unbind_plan_role`.
    """

    def __init__(self, plan_id: UUID, current_status: "PlanStatus") -> None:
        super().__init__(
            f"Plan {plan_id} cannot mutate role bindings: currently in "
            f"status {current_status.value}, role-binding mutations require "
            f"{PlanStatus.DEFINED.value}"
        )
        self.plan_id = plan_id
        self.current_status = current_status
