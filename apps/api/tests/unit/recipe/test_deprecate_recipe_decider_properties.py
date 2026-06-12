"""Property-based tests for `deprecate_recipe.decide` (Recipe BC).

Complements the example-based `test_deprecate_recipe_decider.py` with
universal claims across generated inputs. The decider is a pure
multi-source FSM transition

    (state, command, now) -> list[RecipeDeprecated]

Load-bearing properties:

  - state=None always raises `RecipeNotFoundError` carrying
    command.recipe_id.
  - The source-state partition is total over `RecipeStatus`: only
    `Defined` and `Versioned` emit exactly one `RecipeDeprecated`
    (recipe_id=state.id, occurred_at=now); every other status raises
    `RecipeCannotDeprecateError` carrying the current status, so a
    future status value cannot silently fall through.
  - The emitted event's recipe_id is `state.id`, never
    `command.recipe_id`; replaced_by_recipe_id is threaded from the
    command.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.recipe.aggregates.recipe import (
    Recipe,
    RecipeCannotDeprecateError,
    RecipeDeprecated,
    RecipeName,
    RecipeNotFoundError,
    RecipeSetpointStep,
    RecipeStatus,
)
from cora.recipe.features import deprecate_recipe
from cora.recipe.features.deprecate_recipe import DeprecateRecipe
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_CAPABILITY_ID = UUID(int=1)

_DEPRECATABLE_SOURCES = (RecipeStatus.DEFINED, RecipeStatus.VERSIONED)
_DISALLOWED_SOURCES = tuple(s for s in RecipeStatus if s not in frozenset(_DEPRECATABLE_SOURCES))


def _recipe(*, recipe_id: UUID, status: RecipeStatus) -> Recipe:
    return Recipe(
        id=recipe_id,
        name=RecipeName("R"),
        capability_id=_CAPABILITY_ID,
        steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
        status=status,
    )


@pytest.mark.unit
@given(recipe_id=st.uuids(), now=aware_datetimes())
def test_deprecate_with_none_state_always_raises_not_found(
    recipe_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `RecipeNotFoundError` carrying command.recipe_id."""
    with pytest.raises(RecipeNotFoundError) as exc:
        deprecate_recipe.decide(
            state=None,
            command=DeprecateRecipe(recipe_id=recipe_id),
            now=now,
        )
    assert exc.value.recipe_id == recipe_id


@pytest.mark.unit
@given(
    recipe_id=st.uuids(),
    source=st.sampled_from(_DEPRECATABLE_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_from_deprecatable_source_emits_single_event(
    recipe_id: UUID,
    source: RecipeStatus,
    now: datetime,
) -> None:
    """Defined and Versioned each emit exactly one RecipeDeprecated."""
    events = deprecate_recipe.decide(
        state=_recipe(recipe_id=recipe_id, status=source),
        command=DeprecateRecipe(recipe_id=recipe_id),
        now=now,
    )
    assert events == [RecipeDeprecated(recipe_id=recipe_id, occurred_at=now)]


@pytest.mark.unit
@given(
    recipe_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_from_disallowed_source_always_raises_cannot_deprecate(
    recipe_id: UUID,
    source: RecipeStatus,
    now: datetime,
) -> None:
    """Any source outside {Defined, Versioned} raises, carrying current status."""
    with pytest.raises(RecipeCannotDeprecateError) as exc:
        deprecate_recipe.decide(
            state=_recipe(recipe_id=recipe_id, status=source),
            command=DeprecateRecipe(recipe_id=recipe_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_recipe_id=st.uuids(),
    command_recipe_id=st.uuids(),
    source=st.sampled_from(_DEPRECATABLE_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_emits_event_with_state_id_not_command_recipe_id(
    state_recipe_id: UUID,
    command_recipe_id: UUID,
    source: RecipeStatus,
    now: datetime,
) -> None:
    """The emitted event's recipe_id is state.id, not command.recipe_id."""
    assume(state_recipe_id != command_recipe_id)
    events = deprecate_recipe.decide(
        state=_recipe(recipe_id=state_recipe_id, status=source),
        command=DeprecateRecipe(recipe_id=command_recipe_id),
        now=now,
    )
    assert events[0].recipe_id == state_recipe_id


@pytest.mark.unit
@given(
    recipe_id=st.uuids(),
    successor_id=st.uuids(),
    source=st.sampled_from(_DEPRECATABLE_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_emits_event_threading_replaced_by_recipe_id(
    recipe_id: UUID,
    successor_id: UUID,
    source: RecipeStatus,
    now: datetime,
) -> None:
    """A supplied successor pointer is threaded onto the emitted event."""
    events = deprecate_recipe.decide(
        state=_recipe(recipe_id=recipe_id, status=source),
        command=DeprecateRecipe(
            recipe_id=recipe_id,
            replaced_by_recipe_id=successor_id,
        ),
        now=now,
    )
    assert events[0].replaced_by_recipe_id == successor_id


@pytest.mark.unit
@given(
    recipe_id=st.uuids(),
    name=printable_ascii_text(max_size=8),
    now=aware_datetimes(),
)
def test_deprecate_is_pure_same_input_returns_equal_events(
    recipe_id: UUID,
    name: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    assume(name.strip() != "")
    state = Recipe(
        id=recipe_id,
        name=RecipeName(name),
        capability_id=_CAPABILITY_ID,
        steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
        status=RecipeStatus.DEFINED,
    )
    command = DeprecateRecipe(recipe_id=recipe_id)
    first = deprecate_recipe.decide(state=state, command=command, now=now)
    second = deprecate_recipe.decide(state=state, command=command, now=now)
    assert first == second
