"""Unit tests for the `deprecate_recipe` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.recipe.aggregates.recipe import (
    Recipe,
    RecipeCannotDeprecateError,
    RecipeDeprecated,
    RecipeName,
    RecipeNotFoundError,
    RecipeSetpointStep,
    RecipeStatus,
)
from cora.recipe.features.deprecate_recipe import DeprecateRecipe, decide
from cora.shared.deprecation import DeprecationReason

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)


def _state(status: RecipeStatus = RecipeStatus.DEFINED) -> Recipe:
    return Recipe(
        id=uuid4(),
        name=RecipeName("R"),
        capability_id=uuid4(),
        steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_recipe_deprecated_when_state_defined() -> None:
    state = _state(RecipeStatus.DEFINED)
    events = decide(
        state=state,
        command=DeprecateRecipe(reason=DeprecationReason.SUPERSEDED, recipe_id=state.id),
        now=_NOW,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, RecipeDeprecated)
    assert event.recipe_id == state.id
    assert event.replaced_by_recipe_id is None


@pytest.mark.unit
def test_decide_emits_recipe_deprecated_when_state_versioned() -> None:
    state = _state(RecipeStatus.VERSIONED)
    succ = uuid4()
    events = decide(
        state=state,
        command=DeprecateRecipe(
            reason=DeprecationReason.SUPERSEDED, recipe_id=state.id, replaced_by_recipe_id=succ
        ),
        now=_NOW,
    )
    assert events[0].replaced_by_recipe_id == succ


@pytest.mark.unit
def test_decide_raises_not_found_when_state_none() -> None:
    rid = uuid4()
    with pytest.raises(RecipeNotFoundError) as exc:
        decide(
            state=None,
            command=DeprecateRecipe(reason=DeprecationReason.SUPERSEDED, recipe_id=rid),
            now=_NOW,
        )
    assert exc.value.recipe_id == rid


@pytest.mark.unit
def test_decide_raises_cannot_deprecate_when_already_deprecated() -> None:
    """Strict-not-idempotent: re-deprecating raises."""
    state = _state(RecipeStatus.DEPRECATED)
    with pytest.raises(RecipeCannotDeprecateError) as exc:
        decide(
            state=state,
            command=DeprecateRecipe(reason=DeprecationReason.SUPERSEDED, recipe_id=state.id),
            now=_NOW,
        )
    assert exc.value.current_status == RecipeStatus.DEPRECATED
