"""Pure decider for the `DefineRecipe` command.

Pure function: given the current Recipe state (None for a fresh
stream) and a `DefineRecipe` command, returns the events to append.
No I/O, no awaits, no side effects. The handler performs the
cross-aggregate Capability load + BindingRef integrity check BEFORE
invoking this decider; the decider receives only the validated
result.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports.

Invariants:
  - State must be None (recipe stream must be fresh)
    -> RecipeAlreadyExistsError
  - command.name must be 1-200 chars after trimming
    -> InvalidRecipeNameError (Recipe.__post_init__-adjacent
       boundary; raised by RecipeName VO construction)
  - command.steps must be non-empty
    -> EmptyRecipeStepsError (Recipe.__post_init__ gate)
"""

from datetime import datetime
from uuid import UUID

from cora.recipe.aggregates.recipe import (
    Recipe,
    RecipeAlreadyExistsError,
    RecipeDefined,
    RecipeName,
)
from cora.recipe.features.define_recipe.command import DefineRecipe


def decide(
    state: Recipe | None,
    command: DefineRecipe,
    *,
    now: datetime,
    new_id: UUID,
) -> list[RecipeDefined]:
    """Decide the events produced by defining a new Recipe."""
    if state is not None:
        raise RecipeAlreadyExistsError(state.id)
    name = RecipeName(command.name)  # validates 1-200 chars
    # Re-construct Recipe through the aggregate to fire the
    # EmptyRecipeStepsError invariant before any event is emitted.
    Recipe(
        id=new_id,
        name=name,
        capability_id=command.capability_id,
        steps=command.steps,
        closing_steps=command.closing_steps,
    )
    return [
        RecipeDefined(
            recipe_id=new_id,
            name=name.value,
            capability_id=command.capability_id,
            steps=command.steps,
            occurred_at=now,
            closing_steps=command.closing_steps,
        )
    ]
