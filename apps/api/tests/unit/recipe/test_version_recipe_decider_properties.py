"""Property-based tests for `version_recipe.decide` (Recipe BC).

Complements the example-based `test_version_recipe_decider.py` with
universal claims across generated inputs. The decider is a pure
multi-source-state transition

    (state, command, now) -> list[RecipeVersioned]

with source set `{Defined, Versioned} -> Versioned`.

Load-bearing properties:

  - state=None always raises `RecipeNotFoundError` carrying
    command.recipe_id.
  - The source-state partition is total over `RecipeStatus`: every
    status in {Defined, Versioned} emits exactly one `RecipeVersioned`
    (recipe_id=state.id, occurred_at=now); every other status raises
    `RecipeCannotVersionError` carrying the current status, so a future
    status value cannot silently fall through.
  - The emitted event's recipe_id is `state.id`, never
    command.recipe_id, and the version_tag is threaded from the command.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.recipe.aggregates.recipe import (
    RECIPE_VERSION_TAG_MAX_LENGTH,
    InvalidRecipeVersionTagError,
    Recipe,
    RecipeCannotVersionError,
    RecipeName,
    RecipeNotFoundError,
    RecipeSetpointStep,
    RecipeStatus,
    RecipeVersioned,
)
from cora.recipe.features.version_recipe import VersionRecipe, decide
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_VERSION_TAG = "v1"
_STEPS = (RecipeSetpointStep(address="dev:x", value=2.0),)

_VERSIONABLE_SOURCES = (RecipeStatus.DEFINED, RecipeStatus.VERSIONED)
_DISALLOWED_SOURCES = tuple(s for s in RecipeStatus if s not in frozenset(_VERSIONABLE_SOURCES))


def _state(*, recipe_id: UUID, status: RecipeStatus) -> Recipe:
    return Recipe(
        id=recipe_id,
        name=RecipeName("R"),
        capability_id=UUID(int=1),
        steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
        status=status,
    )


def _cmd(recipe_id: UUID, **overrides: object) -> VersionRecipe:
    base: dict[str, object] = dict(
        recipe_id=recipe_id,
        version_tag=_VERSION_TAG,
        steps=_STEPS,
    )
    base.update(overrides)
    return VersionRecipe(**base)  # type: ignore[arg-type]


@pytest.mark.unit
@given(recipe_id=st.uuids(), now=aware_datetimes())
def test_version_with_none_state_always_raises_not_found(
    recipe_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `RecipeNotFoundError` carrying command.recipe_id."""
    with pytest.raises(RecipeNotFoundError) as exc:
        decide(state=None, command=_cmd(recipe_id), now=now)
    assert exc.value.recipe_id == recipe_id


@pytest.mark.unit
@given(
    recipe_id=st.uuids(),
    source=st.sampled_from(_VERSIONABLE_SOURCES),
    now=aware_datetimes(),
)
def test_version_from_versionable_source_emits_single_event(
    recipe_id: UUID,
    source: RecipeStatus,
    now: datetime,
) -> None:
    """Defined and Versioned are versionable sources; each emits one RecipeVersioned."""
    events = decide(
        state=_state(recipe_id=recipe_id, status=source),
        command=_cmd(recipe_id),
        now=now,
    )
    assert events == [
        RecipeVersioned(
            recipe_id=recipe_id,
            version_tag=_VERSION_TAG,
            steps=_STEPS,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    recipe_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_version_from_disallowed_source_always_raises_cannot_version(
    recipe_id: UUID,
    source: RecipeStatus,
    now: datetime,
) -> None:
    """Any source outside {Defined, Versioned} raises, carrying the current status."""
    with pytest.raises(RecipeCannotVersionError) as exc:
        decide(
            state=_state(recipe_id=recipe_id, status=source),
            command=_cmd(recipe_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_recipe_id=st.uuids(),
    command_recipe_id=st.uuids(),
    now=aware_datetimes(),
)
def test_version_emits_event_with_state_id_not_command_recipe_id(
    state_recipe_id: UUID,
    command_recipe_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's recipe_id is state.id, not command.recipe_id."""
    assume(state_recipe_id != command_recipe_id)
    events = decide(
        state=_state(recipe_id=state_recipe_id, status=RecipeStatus.DEFINED),
        command=_cmd(command_recipe_id),
        now=now,
    )
    assert events[0].recipe_id == state_recipe_id


@pytest.mark.unit
@given(
    recipe_id=st.uuids(),
    version_tag=printable_ascii_text(max_size=RECIPE_VERSION_TAG_MAX_LENGTH),
    now=aware_datetimes(),
)
def test_version_emits_event_with_threaded_version_tag(
    recipe_id: UUID,
    version_tag: str,
    now: datetime,
) -> None:
    """A bounded non-whitespace tag is threaded onto the emitted event verbatim."""
    events = decide(
        state=_state(recipe_id=recipe_id, status=RecipeStatus.DEFINED),
        command=_cmd(recipe_id, version_tag=version_tag),
        now=now,
    )
    assert events[0].version_tag == version_tag


@pytest.mark.unit
@given(recipe_id=st.uuids(), now=aware_datetimes())
def test_version_with_whitespace_only_tag_raises_invalid_tag(
    recipe_id: UUID,
    now: datetime,
) -> None:
    """A whitespace-only version tag raises `InvalidRecipeVersionTagError`."""
    with pytest.raises(InvalidRecipeVersionTagError):
        decide(
            state=_state(recipe_id=recipe_id, status=RecipeStatus.DEFINED),
            command=_cmd(recipe_id, version_tag="   "),
            now=now,
        )


@pytest.mark.unit
@given(recipe_id=st.uuids(), now=aware_datetimes())
def test_version_is_pure_same_input_returns_equal_output(
    recipe_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _state(recipe_id=recipe_id, status=RecipeStatus.DEFINED)
    command = _cmd(recipe_id)
    first = decide(state=state, command=command, now=now)
    second = decide(state=state, command=command, now=now)
    assert first == second
