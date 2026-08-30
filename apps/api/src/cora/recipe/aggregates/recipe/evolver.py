"""Evolver: replay events to reconstruct Recipe state.

Status mapping per event type:
  - `RecipeDefined`    -> DEFINED   (genesis; version=None)
  - `RecipeVersioned`  -> VERSIONED (version=event.version_tag;
                                     steps REPLACE wholesale;
                                     name + capability_id PRESERVED)
  - `RecipeDeprecated` -> DEPRECATED (steps + capability_id + name
                                      PRESERVED for audit;
                                      replaced_by_recipe_id captured
                                      if supplied)

The mapping is hardcoded per match arm; the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `CapabilityVersioned` / `FamilyVersioned`.

## Replace vs preserve on each arm

- `RecipeVersioned` REPLACES `steps` AND `closing_steps` with the new
  event's tuples (a new version IS a new declaration, and a version
  can fix a broken closing step too). PRESERVES `name`,
  `capability_id`, and `replaced_by_recipe_id`.
- `RecipeDeprecated` PRESERVES all declarative fields (steps,
  closing_steps, capability_id, name, version) and ADDS the
  `replaced_by_recipe_id` pointer. Operators reading a deprecated
  Recipe still see what it declared (audit-critical).

Transition events applied to empty state raise ValueError via
`require_state`; they can never appear before `RecipeDefined` in a
well-formed stream.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.infrastructure.evolver import require_state
from cora.recipe.aggregates.recipe.events import (
    RecipeDefined,
    RecipeDeprecated,
    RecipeEvent,
    RecipeVersioned,
)
from cora.recipe.aggregates.recipe.state import (
    Recipe,
    RecipeName,
    RecipeStatus,
)


def evolve(state: Recipe | None, event: RecipeEvent) -> Recipe:
    """Apply one event to the current state."""
    match event:
        case RecipeDefined(
            recipe_id=recipe_id,
            name=name,
            capability_id=capability_id,
            steps=steps,
            closing_steps=closing_steps,
        ):
            _ = state  # genesis event; prior state ignored
            return Recipe(
                id=recipe_id,
                name=RecipeName(name),
                capability_id=capability_id,
                steps=steps,
                status=RecipeStatus.DEFINED,
                closing_steps=closing_steps,
            )
        case RecipeVersioned(version_tag=version_tag, steps=steps, closing_steps=closing_steps):
            prior = require_state(state, "RecipeVersioned")
            return Recipe(
                id=prior.id,
                name=prior.name,
                capability_id=prior.capability_id,
                steps=steps,
                status=RecipeStatus.VERSIONED,
                version=version_tag,
                replaced_by_recipe_id=prior.replaced_by_recipe_id,
                closing_steps=closing_steps,
            )
        case RecipeDeprecated(replaced_by_recipe_id=replaced_by_recipe_id):
            prior = require_state(state, "RecipeDeprecated")
            return Recipe(
                id=prior.id,
                name=prior.name,
                capability_id=prior.capability_id,
                steps=prior.steps,
                status=RecipeStatus.DEPRECATED,
                version=prior.version,
                replaced_by_recipe_id=replaced_by_recipe_id,
                closing_steps=prior.closing_steps,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[RecipeEvent]) -> Recipe | None:
    """Replay a stream of events from the empty initial state."""
    state: Recipe | None = None
    for event in events:
        state = evolve(state, event)
    return state
