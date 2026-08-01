"""Pure decider for the `DeprecateRecipe` command.

Multi-source-state transition: `Defined | Versioned -> Deprecated`.
Re-deprecating a Deprecated Recipe raises (strict-not-idempotent).

`replaced_by_recipe_id` (when supplied) points at a successor Recipe.
Eventual-consistency: the target id is NOT verified cross-stream at
decider time (same precedent as `Capability.replaced_by_capability_id`).

Invariants:
  - State must not be None -> RecipeNotFoundError
  - State.status must be in {Defined, Versioned}
    -> RecipeCannotDeprecateError(current_status=...)
"""

from datetime import datetime

from cora.recipe.aggregates.recipe import (
    Recipe,
    RecipeCannotDeprecateError,
    RecipeDeprecated,
    RecipeNotFoundError,
    RecipeStatus,
)
from cora.recipe.features.deprecate_recipe.command import DeprecateRecipe

_DEPRECATABLE_STATUSES: tuple[RecipeStatus, ...] = (
    RecipeStatus.DEFINED,
    RecipeStatus.VERSIONED,
)


def decide(
    state: Recipe | None,
    command: DeprecateRecipe,
    *,
    now: datetime,
) -> list[RecipeDeprecated]:
    """Decide the events produced by deprecating an existing Recipe."""
    if state is None:
        raise RecipeNotFoundError(command.recipe_id)
    if state.status not in _DEPRECATABLE_STATUSES:
        raise RecipeCannotDeprecateError(state.id, current_status=state.status)
    return [
        RecipeDeprecated(
            recipe_id=state.id,
            reason=command.reason.value,
            replaced_by_recipe_id=command.replaced_by_recipe_id,
            occurred_at=now,
        )
    ]
