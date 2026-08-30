"""Pure decider for the `VersionRecipe` command.

Multi-source-state transition: `Defined | Versioned -> Versioned`.
Both Defined (first revision) and Versioned (subsequent revisions)
are valid sources; only Deprecated is rejected.

Re-attestation: calling version_recipe with the same version_tag +
same steps both succeed and emit a `RecipeVersioned` event each
time. Re-attestation is a legitimate audit moment ("the operator
re-confirmed v2 on date X"); the multi-source Versioned -> Versioned
transition permits the operation structurally. Same precedent as
`version_capability` / `version_method`.

Invariants:
  - State must not be None -> RecipeNotFoundError
  - command.version_tag must be 1-50 chars after trimming
    -> InvalidRecipeVersionTagError
  - command.steps must be non-empty (re-asserted via Recipe construction)
    -> EmptyRecipeStepsError
  - State.status must be in {Defined, Versioned}
    -> RecipeCannotVersionError(current_status=...)
"""

from datetime import datetime

from cora.recipe.aggregates.recipe import (
    RECIPE_VERSION_TAG_MAX_LENGTH,
    InvalidRecipeVersionTagError,
    Recipe,
    RecipeCannotVersionError,
    RecipeNotFoundError,
    RecipeStatus,
    RecipeVersioned,
)
from cora.recipe.features.version_recipe.command import VersionRecipe

_VERSIONABLE_STATUSES: tuple[RecipeStatus, ...] = (
    RecipeStatus.DEFINED,
    RecipeStatus.VERSIONED,
)


def decide(
    state: Recipe | None,
    command: VersionRecipe,
    *,
    now: datetime,
) -> list[RecipeVersioned]:
    """Decide the events produced by versioning an existing Recipe."""
    if state is None:
        raise RecipeNotFoundError(command.recipe_id)
    trimmed = command.version_tag.strip()
    if not trimmed or len(trimmed) > RECIPE_VERSION_TAG_MAX_LENGTH:
        raise InvalidRecipeVersionTagError(command.version_tag)
    if state.status not in _VERSIONABLE_STATUSES:
        raise RecipeCannotVersionError(state.id, current_status=state.status)
    # Re-assert the non-empty-steps invariant via Recipe construction
    # before any event is emitted.
    Recipe(
        id=state.id,
        name=state.name,
        capability_id=state.capability_id,
        steps=command.steps,
        closing_steps=command.closing_steps,
    )
    return [
        RecipeVersioned(
            recipe_id=state.id,
            version_tag=trimmed,
            steps=command.steps,
            occurred_at=now,
            closing_steps=command.closing_steps,
        )
    ]
