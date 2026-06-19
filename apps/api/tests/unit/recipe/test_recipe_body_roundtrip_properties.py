"""Property-based tests for `cora.recipe.aggregates.recipe.body` wire-format roundtrip.

Pins three invariants:
  - `from_dict(to_dict(steps)) == steps` for arbitrary Hypothesis-generated
    RecipeStep tuples (idempotent roundtrip)
  - `Recipe.__post_init__` raises `EmptyRecipeStepsError` for empty tuples
    and succeeds for non-empty ones
  - `_BINDING_KEY`-distinguished wire serialization is canonical under
    shuffled-key dicts (the `__binding__` sentinel survives dict-key
    reordering)
"""

from uuid import uuid4

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from cora.recipe.aggregates.recipe import (
    BindingRef,
    EmptyRecipeStepsError,
    Recipe,
    RecipeActionStep,
    RecipeCheckStep,
    RecipeName,
    RecipeSetpointStep,
    RecipeStep,
    steps_from_dict,
    steps_to_dict,
)

_binding_or_literal = st.one_of(
    st.integers(min_value=-1000, max_value=1000),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.booleans(),
    st.text(min_size=1, max_size=20),
    st.builds(BindingRef, st.text(min_size=1, max_size=12)),
)

_setpoint_strategy = st.builds(
    RecipeSetpointStep,
    address=st.text(min_size=1, max_size=20),
    value=_binding_or_literal,
    verify=st.booleans(),
)

_action_strategy = st.builds(
    RecipeActionStep,
    name=st.text(min_size=1, max_size=20),
    params=st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=_binding_or_literal,
        max_size=4,
    ),
)

_check_strategy = st.builds(
    RecipeCheckStep,
    address=st.text(min_size=1, max_size=20),
    criterion=st.fixed_dictionaries(
        {
            "kind": st.sampled_from(["equals", "within_tolerance"]),
            "expected": st.floats(allow_nan=False, allow_infinity=False, width=32),
        }
    ),
)

_step_strategy = st.one_of(_setpoint_strategy, _action_strategy, _check_strategy)


@pytest.mark.unit
@settings(max_examples=100, deadline=2000)
@given(steps=st.lists(_step_strategy, min_size=1, max_size=10))
def test_body_roundtrip_is_idempotent(steps: list[RecipeStep]) -> None:
    steps_tuple = tuple(steps)
    rebuilt = steps_from_dict(steps_to_dict(steps_tuple))
    assert rebuilt == steps_tuple


@pytest.mark.unit
@settings(max_examples=50, deadline=2000)
@given(steps=st.lists(_step_strategy, min_size=1, max_size=5))
def test_recipe_post_init_accepts_any_nonempty_step_tuple(steps: list[RecipeStep]) -> None:
    Recipe(
        id=uuid4(),
        name=RecipeName("R"),
        capability_id=uuid4(),
        steps=tuple(steps),
    )


@pytest.mark.unit
def test_recipe_post_init_rejects_empty_step_tuple() -> None:
    with pytest.raises(EmptyRecipeStepsError):
        Recipe(id=uuid4(), name=RecipeName("R"), capability_id=uuid4(), steps=())


@pytest.mark.unit
@settings(max_examples=50, deadline=2000)
@given(
    name=st.text(min_size=1, max_size=20),
    bindings=st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=st.one_of(st.integers(), st.floats(allow_nan=False, allow_infinity=False)),
        max_size=4,
    ),
)
# Regression: a generated binding under the probe key `"x"` used to clobber
# the BindingRef and make the test assert against its own injected literal.
@example(name="0", bindings={"x": 0})
def test_binding_sentinel_survives_dict_key_reorder(name: str, bindings: dict[str, object]) -> None:
    """The `__binding__` sentinel must distinguish BindingRefs from literal dicts.

    A `{key: bindings}` value that happens to carry `__binding__` would
    be misread; the v1 contract forbids that key in literal payloads.
    """
    # Exclude both the `__binding__` sentinel (the contract forbids it in
    # literal payloads) AND the fixed probe key `"x"` that holds the
    # BindingRef: a generated `"x"` would clobber the probe via the spread
    # below, making the test assert against a literal it injected itself
    # rather than against the roundtrip.
    bindings_no_collision = {k: v for k, v in bindings.items() if k not in ("__binding__", "x")}
    step = RecipeActionStep(
        name=name,
        params={"x": BindingRef("p"), **bindings_no_collision},
    )
    rebuilt = steps_from_dict(steps_to_dict((step,)))
    assert isinstance(rebuilt[0], RecipeActionStep)
    assert isinstance(rebuilt[0].params["x"], BindingRef)
