"""The `DefineRecipe` command, intent dataclass for this slice.

Carries the FULL declarative contract the caller controls:
operator-supplied name, capability_id (REQUIRED + immutable across
versions), and the templated `steps` tuple with embedded BindingRef
sentinels. Server-side concerns (new id, wall-clock timestamp,
correlation id, per-event ids) are injected by the handler from
infrastructure ports.

`capability_id` resolves cross-aggregate at handler time before the
decider runs; a missing Capability raises `CapabilityNotFoundError`
(re-used per anti-hook 18 of [[project-recipe-aggregate-design]]).
Every reachable `BindingRef.name` is validated against the loaded
Capability's `parameters_schema.properties` per the eager cross-BC
validation lock.

`steps` is REQUIRED non-empty; the Recipe aggregate's `__post_init__`
gate raises `EmptyRecipeStepsError` if the resulting evolver fold
would produce an empty step sequence.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.recipe.aggregates.recipe import RecipeStep


@dataclass(frozen=True)
class DefineRecipe:
    """Define a new Recipe against an existing Capability.

    `closing_steps` is additive and optional (default `()`); see
    `Recipe.closing_steps`.
    """

    name: str
    capability_id: UUID
    steps: tuple[RecipeStep, ...]
    closing_steps: tuple[RecipeStep, ...] = ()
