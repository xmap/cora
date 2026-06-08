"""Recipe aggregate state, status enum, errors, and value objects.

`Recipe` is the EXECUTABLE PARAMETERIZED STEP SEQUENCE at the
operations layer: a deployment-bound, ordered tuple of templated
steps that, once an operator supplies parameter bindings, expands
into a flat list of `Step`s the Operation BC Conductor walks. Each
Recipe references one `Capability` via `capability_id`; that
Capability declares the contract (parameters_schema, required
affordances, executor shapes) the Recipe realizes.

Per [[project-recipe-aggregate-design]] (the 5th aggregate added to
Recipe BC after [[capability-naming-split-lock]]), Recipe sits BESIDE
Capability rather than absorbing Method/Plan: Method (technique-class
contract) and Plan (Asset-bound binding) keep their roles; Recipe
carries the body that previously squatted on `Capability.template_body`.

Distinct from siblings:
- `Capability` declares the operations-layer contract: code, name,
  required affordances, parameters_schema, executor shapes. Slow-changing
  namespaced declaration.
- `Recipe` (this aggregate) is the deployment-specific executable body:
  capability_id + ordered tuple of typed step VOs with embedded
  BindingRef sentinels. Iterates faster than Capability.
- `Method` is the technique-class contract (the science-side declaration).
- `Plan` is the Asset-bound binding (Plan.wires + Plan.default_parameters).

Genesis + FSM `Defined -> Versioned -> Deprecated`, matching
Capability/Method/Plan/Practice/Family precedent. Slice verbs:
`define_recipe`, `version_recipe`, `deprecate_recipe`, `get_recipe`.

## Status as enum-in-state, derived-from-event-type-in-evolver

`RecipeStatus` is a `StrEnum` so the values would serialize naturally
as JSON-friendly strings IF carried in event payloads. Today they
aren't: state holds the enum (typed) and the evolver derives status
from the event TYPE, same precedent as `CapabilityStatus` /
`FamilyStatus` / `MethodStatus`.

## Non-emptiness invariant on `steps`

A Recipe without steps has no operational meaning (expansion would
produce zero work). `Recipe.__post_init__` raises `EmptyRecipeStepsError`
when `steps` is empty. The invariant is carried by Recipe construction
and re-runs every time the evolver folds a `RecipeDefined` or
`RecipeVersioned` event into a `Recipe(...)` call. The retired
worktree `TemplateBody` wrapper VO that previously enforced this is
not reintroduced; Recipe owns the invariant directly.

## Immutable capability_id

`Recipe.capability_id` is REQUIRED at define_recipe time and IMMUTABLE
across `version_recipe`: re-binding a Recipe to a different Capability
is forbidden. Operators wanting a different binding author a new
Recipe. Mirrors `Method.capability_id` immutability.

## No `description` field

Intentional divergence from the Capability mirror. Per anti-hook 17 in
[[project-recipe-aggregate-design]]: human annotation belongs on
Capability (the contract), not on Recipe (the executable derivative).
A Recipe is identified by `capability_id + name`.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cora.recipe.aggregates.recipe.body import RecipeStep
from cora.shared.bounded_text import bounded_name

RECIPE_NAME_MAX_LENGTH = 200
RECIPE_VERSION_TAG_MAX_LENGTH = 50


class RecipeStatus(StrEnum):
    """The Recipe's lifecycle state.

    Transitions:
      - Defined -> Versioned        (version_recipe)
      - (Defined | Versioned) -> Deprecated   (deprecate_recipe)

    `Defined` is the genesis state set by `define_recipe`. PascalCase
    string values match the BC-map status vocabulary so log lines and
    DTOs read naturally without additional mapping.
    """

    DEFINED = "Defined"
    VERSIONED = "Versioned"
    DEPRECATED = "Deprecated"


class InvalidRecipeNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Recipe name must be 1-{RECIPE_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidRecipeVersionTagError(ValueError):
    """The supplied version tag is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Recipe version tag must be 1-{RECIPE_VERSION_TAG_MAX_LENGTH} chars after "
            f"trimming (got: {value!r})"
        )
        self.value = value


class EmptyRecipeStepsError(Exception):
    """`Recipe.steps` is empty.

    Enforced inside `Recipe.__post_init__` so the gate fires both at
    write time (deciders and handlers) and at fold time (evolver
    construction on replay). A Recipe with zero steps has no
    operational meaning; expansion would produce no work.

    Family: `Invalid<X>`. HTTP 400 (domain-invariant error from
    `__post_init__`, not a Pydantic-boundary parse failure). The 422
    reservation is for boundary parse errors only.
    """

    def __init__(self) -> None:
        super().__init__("Recipe.steps must be non-empty")


class RecipeAlreadyExistsError(Exception):
    """Attempted to define a Recipe whose stream already has events."""

    def __init__(self, recipe_id: UUID) -> None:
        super().__init__(f"Recipe {recipe_id} already exists")
        self.recipe_id = recipe_id


class RecipeNotFoundError(Exception):
    """Attempted an operation on a Recipe whose stream has no events."""

    def __init__(self, recipe_id: UUID) -> None:
        super().__init__(f"Recipe {recipe_id} not found")
        self.recipe_id = recipe_id


class RecipeVersionNotFoundError(Exception):
    """A `load_recipe_at_version` lookup found the Recipe stream but no
    `RecipeVersioned` event whose `version_tag` matches the pinned tag.

    Distinct from `RecipeNotFoundError` (stream wholly absent). Raised
    by `load_recipe_at_version` when the caller pins a tag that is
    absent from the Recipe history; surfaced as HTTP 404 since the
    requested resource (the version) does not exist.
    """

    def __init__(self, recipe_id: UUID, version_tag: str) -> None:
        super().__init__(
            f"Recipe {recipe_id} has no RecipeVersioned event with version_tag {version_tag!r}"
        )
        self.recipe_id = recipe_id
        self.version_tag = version_tag


class RecipeCannotVersionError(Exception):
    """Attempted to version a Recipe whose status is `Deprecated`.

    Multi-source guard: `version_recipe` accepts `Defined | Versioned`.
    Re-versioning with the same tag SUCCEEDS and emits the event
    (re-attestation is a legitimate audit moment, matching
    `version_capability` / `version_method` precedent).
    """

    def __init__(self, recipe_id: UUID, current_status: "RecipeStatus") -> None:
        super().__init__(
            f"Recipe {recipe_id} cannot be versioned: currently in status "
            f"{current_status.value}, version requires "
            f"{RecipeStatus.DEFINED.value} or {RecipeStatus.VERSIONED.value}"
        )
        self.recipe_id = recipe_id
        self.current_status = current_status


class RecipeCannotDeprecateError(Exception):
    """Attempted to deprecate a Recipe whose status is `Deprecated`.

    Strict-not-idempotent: re-deprecating a Deprecated Recipe raises.
    """

    def __init__(self, recipe_id: UUID, current_status: "RecipeStatus") -> None:
        super().__init__(
            f"Recipe {recipe_id} cannot be deprecated: currently in status "
            f"{current_status.value}, deprecate requires "
            f"{RecipeStatus.DEFINED.value} or {RecipeStatus.VERSIONED.value}"
        )
        self.recipe_id = recipe_id
        self.current_status = current_status


@bounded_name(max_length=RECIPE_NAME_MAX_LENGTH, error_class=InvalidRecipeNameError)
@dataclass(frozen=True)
class RecipeName:
    """Display name for a Recipe. Trimmed; 1-200 chars."""

    value: str


@dataclass(frozen=True)
class Recipe:
    """Aggregate root: a deployment-bound executable step sequence.

    `capability_id` is REQUIRED at define time and IMMUTABLE across
    versions. Re-binding a Recipe to a different Capability is
    forbidden; operators create a new Recipe instead.

    `steps` is the ordered tuple of templated `RecipeStep` instances,
    each potentially carrying `BindingRef` sentinels resolved against
    operator-supplied bindings at expansion time. Replaced wholesale
    by `version_recipe`; non-empty enforced in `__post_init__`.

    `version` is the operator-supplied label of the most recent
    `version_recipe` call (None until first version). State holds the
    latest tag; past tags live in the event stream as `RecipeVersioned`
    events. `version_tag` carries no UNIQUE constraint; re-tagging is
    allowed (re-attestation is a legitimate audit moment per
    `version_capability`/`version_method` precedent). Replay determinism
    comes from first-match-from-head tag-string lookup via
    `load_recipe_at_version`; the earlier `RecipeVersioned` binds the
    earlier `RecipeExpansionRecorded` by construction (the later
    re-tagging cannot retroactively change which version was pinned).
    See [[project-run-procedure-replay-design]] Locks.

    `replaced_by_recipe_id`: pointer to a successor Recipe when this
    one is deprecated with replacement. None on
    Deprecated-without-replacement and on Defined/Versioned. LOINC
    `MAP_TO` precedent matching `Capability.replaced_by_capability_id`.
    """

    id: UUID
    name: RecipeName
    capability_id: UUID
    steps: tuple[RecipeStep, ...]
    status: RecipeStatus = RecipeStatus.DEFINED
    version: str | None = None
    replaced_by_recipe_id: UUID | None = None

    def __post_init__(self) -> None:
        if not self.steps:
            raise EmptyRecipeStepsError
