"""Capability aggregate state, status enum, errors, and value objects.

`Capability` is the UNIVERSAL DECLARATIVE TEMPLATE at the operations
layer: WHAT a class of operation does, asset-independent, executor-
agnostic. Examples: `cora.capability.continuous_rotation_sweep`,
`cora.capability.energy_change`, `cora.capability.alignment_focus`.
Per [[project-capability-research]] Round 3, Capability sits ABOVE
heterogeneous executor shapes (`Method`-chain for science,
`Procedure`-direct for ceremony per 10c) and declares which executor
kinds may implement it via `executor_shapes`. Method (Recipe BC) and
Procedure (Operation BC) carry `capability_id` FKs pointing back at
this aggregate.

Distinct from Equipment BC's `Family` aggregate:
- `Family` is the device-class abstraction (RotaryStage / Camera /
  Scintillator). Carries an `Affordance` set declaring what the
  device CAN DO at the physics layer.
- `Capability` (this aggregate) is the operations-layer template
  that says what a Method or Procedure realizes operationally.
  Carries `required_affordances` declaring the Family.affordance
  contract any implementer must satisfy.

The two-aggregate split was the core lock of
[[project-capability-research]] Round 1+2: equipment classification
vs operations template are orthogonal axes (ISA-88 Physical Model
vs Procedural Control Model precedent). The Family-side anchor for
the same orthogonality lives at [[project-family-affordance-design]]
watch item 10 (Equipment.Family rename freed the word "Capability"
for this aggregate).


Genesis + FSM (Defined → Versioned → Deprecated, matching
Method/Plan/Practice/Family precedent). 4 slices: `define_capability`,
`version_capability`, `deprecate_capability`, `get_capability`.
ExecutorShape ships with Capability. The trajectory / PaNET /
plan_signature granularity facets are deferred when pilot demands.

## Status as enum-in-state, derived-from-event-type-in-evolver

`CapabilityStatus` is a `StrEnum` so the values would serialize
naturally as JSON-friendly strings IF carried in event payloads.
Today they aren't: state holds the enum (typed) and the evolver
derives status from the event TYPE — same precedent as `SubjectStatus`
/ `FamilyStatus` / `ActorDeactivated → active=False`.

## Code namespace + name as separate VOs

`CapabilityCode` is the machine-readable namespaced identifier
(`cora.capability.flyscan`); `CapabilityName` is the human display
label ("FlyScan Tomography"). Both validated as bounded text via the
shared `validate_bounded_text` helper. Code namespace is enforced at
write time per [[project-capability-research]] anti-hook 14.

## Declarative contract fields

- `required_affordances: frozenset[Affordance]` — REQUIRED at define
  time per Pattern P. Empty set valid (parameter-driven Capabilities
  like `energy_change` may have no affordance requirement).
- `parameters_schema: dict | None`: optional JSON Schema declaring
  the parameter contract. Method.parameters_schema MUST validate as
  subset at define_method time per STRICT cross-BC anchor.
- `executor_shapes: frozenset[ExecutorShape]` — REQUIRED non-empty
  at define time. Closed v1 enum {Method, Procedure}. A Capability
  with no executor shapes has no operational meaning; decider
  raises `InvalidExecutorShapesError` on empty input.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from cora.equipment.aggregates.family import Affordance
from cora.recipe.aggregates.capability.executor_shape import ExecutorShape
from cora.shared.bounded_text import bounded_name

CAPABILITY_CODE_MAX_LENGTH = 200
CAPABILITY_NAME_MAX_LENGTH = 200
CAPABILITY_DESCRIPTION_MAX_LENGTH = 2000
CAPABILITY_VERSION_TAG_MAX_LENGTH = 50
CAPABILITY_CODE_NAMESPACE_PREFIX = "cora.capability."


class CapabilityStatus(StrEnum):
    """The Capability's lifecycle state.

    Transitions:
      - Defined -> Versioned        (version_capability)
      - (Defined | Versioned) -> Deprecated   (deprecate_capability)

    `Defined` is the genesis state set by `define_capability`. The enum
    values are PascalCase strings (matching the BC-map status
    vocabulary) so log lines and DTOs read naturally without
    additional mapping.
    """

    DEFINED = "Defined"
    VERSIONED = "Versioned"
    DEPRECATED = "Deprecated"


# ---------- Validation errors ----------


class InvalidCapabilityCodeError(ValueError):
    """The supplied code is empty, too long, or has the wrong namespace prefix.

    Codes must be namespaced under `cora.capability.*` (closed core)
    or `cora.capability.<facility>.*` (namespaced facility extension).
    Per [[project-capability-research]] anti-hook 14, ad-hoc
    facility codes without the namespace are rejected.
    """

    def __init__(self, value: str, reason: str) -> None:
        super().__init__(f"Invalid Capability code {value!r}: {reason}")
        self.value = value
        self.reason = reason


class InvalidCapabilityNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Capability name must be 1-{CAPABILITY_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidCapabilityDescriptionError(ValueError):
    """The supplied description is too long (0-2000 chars; None is valid)."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Capability description must be 0-{CAPABILITY_DESCRIPTION_MAX_LENGTH} chars after "
            f"trimming (got length: {len(value)})"
        )
        self.value = value


class InvalidCapabilityVersionTagError(ValueError):
    """The supplied version tag is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Capability version tag must be 1-{CAPABILITY_VERSION_TAG_MAX_LENGTH} chars after "
            f"trimming (got: {value!r})"
        )
        self.value = value


class InvalidExecutorShapesError(ValueError):
    """The supplied executor_shapes set is invalid.

    Empty set is rejected (a Capability with no executor kinds has
    no operational meaning per Locks). Unknown enum values caught
    by ExecutorShape construction.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Capability executor_shapes: {reason}")
        self.reason = reason


# ---------- Aggregate-level errors ----------


class CapabilityAlreadyExistsError(Exception):
    """Attempted to define a Capability whose stream already has events."""

    def __init__(self, capability_id: UUID) -> None:
        super().__init__(f"Capability {capability_id} already exists")
        self.capability_id = capability_id


class CapabilityNotFoundError(Exception):
    """Attempted an operation on a Capability whose stream has no events."""

    def __init__(self, capability_id: UUID) -> None:
        super().__init__(f"Capability {capability_id} not found")
        self.capability_id = capability_id


class CapabilityCannotVersionError(Exception):
    """Attempted to version a Capability not in `Defined` or `Versioned`.

    Multi-source guard: `version_capability` accepts both `Defined`
    (first revision) and `Versioned` (subsequent revisions). Only
    `Deprecated` is rejected.
    """

    def __init__(self, capability_id: UUID, current_status: "CapabilityStatus") -> None:
        super().__init__(
            f"Capability {capability_id} cannot be versioned: currently in status "
            f"{current_status.value}, version requires "
            f"{CapabilityStatus.DEFINED.value} or {CapabilityStatus.VERSIONED.value}"
        )
        self.capability_id = capability_id
        self.current_status = current_status


class CapabilityCannotDeprecateError(Exception):
    """Attempted to deprecate a Capability not in `Defined` or `Versioned`.

    Strict-not-idempotent: re-deprecating a Deprecated Capability raises.
    """

    def __init__(self, capability_id: UUID, current_status: "CapabilityStatus") -> None:
        super().__init__(
            f"Capability {capability_id} cannot be deprecated: currently in status "
            f"{current_status.value}, deprecate requires "
            f"{CapabilityStatus.DEFINED.value} or {CapabilityStatus.VERSIONED.value}"
        )
        self.capability_id = capability_id
        self.current_status = current_status


# ---------- Value objects ----------


def _validate_capability_code(value: str) -> str:
    """Validate code namespace + length. Returns trimmed value."""
    trimmed = value.strip()
    if not trimmed:
        raise InvalidCapabilityCodeError(value, "empty or whitespace-only")
    if len(trimmed) > CAPABILITY_CODE_MAX_LENGTH:
        raise InvalidCapabilityCodeError(
            value, f"length {len(trimmed)} exceeds max {CAPABILITY_CODE_MAX_LENGTH}"
        )
    if not trimmed.startswith(CAPABILITY_CODE_NAMESPACE_PREFIX):
        raise InvalidCapabilityCodeError(
            value, f"must start with {CAPABILITY_CODE_NAMESPACE_PREFIX!r}"
        )
    # Reject pure-prefix codes (no suffix segment)
    suffix = trimmed[len(CAPABILITY_CODE_NAMESPACE_PREFIX) :]
    if not suffix:
        raise InvalidCapabilityCodeError(value, "namespace prefix has no suffix")
    return trimmed


@dataclass(frozen=True)
class CapabilityCode:
    """Namespaced code identifying a Capability: `cora.capability.<segments>`.

    Closed core under `cora.capability.*`; per-deployment extensions
    nest under `cora.capability.<facility>.*` once a real cross-facility
    divergence demands it (per [[project-capability-research]]
    anti-hook 14, premature facility namespacing is anti-pattern).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = _validate_capability_code(self.value)
        object.__setattr__(self, "value", trimmed)


@bounded_name(max_length=CAPABILITY_NAME_MAX_LENGTH, error_class=InvalidCapabilityNameError)
@dataclass(frozen=True)
class CapabilityName:
    """Display name for a Capability. Trimmed; 1-200 chars."""

    value: str


def validate_capability_description(value: str | None) -> str | None:
    """Validate optional description; trims when present. None is valid."""
    if value is None:
        return None
    trimmed = value.strip()
    if len(trimmed) > CAPABILITY_DESCRIPTION_MAX_LENGTH:
        raise InvalidCapabilityDescriptionError(value)
    # Empty after trim is normalized to None (caller meant "no description")
    return trimmed or None


def validate_executor_shapes(shapes: frozenset[ExecutorShape]) -> frozenset[ExecutorShape]:
    """Validate executor_shapes is non-empty. Members already enforced by enum."""
    if not shapes:
        raise InvalidExecutorShapesError("must be non-empty")
    return shapes


# ---------- Aggregate root ----------


@dataclass(frozen=True)
class Capability:
    """Aggregate root: a universal operations-layer template.

    `code` is the namespaced machine-readable identifier; immutable
    across versions (rename = deprecate + new Capability with
    `replaced_by_capability_id` pointer; LOINC `MAP_TO` precedent).

    `version` is the operator-supplied label of the most recent
    `version_capability` call (None until first version). State holds
    the latest tag — past tags live in the event stream as
    `CapabilityVersioned` events.

    `required_affordances` (5j cross-BC): the Family.affordance
    contract any implementer must satisfy. REQUIRED at define time;
    empty frozenset valid + explicit. Replaced wholesale by
    version_capability.

    `parameters_schema` (optional JSON Schema): the declarative
    parameter contract. Method.parameters_schema (6g) MUST validate
    as subset at define_method time per [[project-asset-settings-design]]
    5g-c STRICT cross-BC anchor.

    `executor_shapes`: the closed-enum set of executor kinds that
    may implement this Capability. REQUIRED non-empty. Methods point
    here via Method.capability_id (6l); Procedures via
    Procedure.capability_id (10d). When binding, the executor's
    shape must be in this set.

    `replaced_by_capability_id`: pointer to a successor Capability
    when this one is deprecated with replacement. None on
    Deprecated-without-replacement and on Defined/Versioned.
    """

    id: UUID
    code: CapabilityCode
    name: CapabilityName
    status: CapabilityStatus = CapabilityStatus.DEFINED
    version: str | None = None
    description: str | None = None
    required_affordances: frozenset[Affordance] = field(default_factory=frozenset[Affordance])
    executor_shapes: frozenset[ExecutorShape] = field(default_factory=frozenset[ExecutorShape])
    parameters_schema: dict[str, Any] | None = None
    replaced_by_capability_id: UUID | None = None
