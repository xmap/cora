"""The `RecipeStep` union must stay in sync with the Conductor's `Step` union.

Pins three parallel declarations against drift:

  - `cora.recipe.aggregates.recipe.body.RecipeStep` arms (the templated
    step VOs operators author inside a Recipe)
  - `cora.operation.conductor.Step` arms (the bound step VOs the
    Conductor walks)
  - `cora.operation._recipe_expansion._expand_step` dispatch arms (the
    function that translates each `RecipeStep` to its bound `Step` at
    register_procedure_from_recipe time)

A new RecipeStep variant (say, `RecipeWaitStep`) added without a
matching `Step` arm OR without a matching `_expand_step` dispatch
arm would silently miss the kind at expansion time, with no CI
signal. This test catches the divergence at fitness time.

The third assertion is conditional: the `_recipe_expansion` module
lands in a downstream commit (see project_recipe_aggregate_design).
Until then the dispatch-coverage check is skipped via
`pytest.importorskip`; the arity + name-parity gates provide
sufficient structural coverage in the meantime.
"""

import inspect
from typing import get_args

import pytest

from cora.operation import conductor as _conductor_module
from cora.recipe.aggregates.recipe import body as _recipe_body


@pytest.mark.architecture
def test_recipe_step_union_arity_matches_conductor_step_union() -> None:
    """Both unions have the same number of arms.

    A new RecipeStep variant or Conductor Step variant added without
    a matching arm on the other side lands here. Currently both unions
    carry 3 arms (Setpoint / Action / Check).
    """
    recipe_arms = get_args(_recipe_body.RecipeStep)
    conductor_arms = get_args(_conductor_module.Step)
    assert len(recipe_arms) == len(conductor_arms), (
        f"RecipeStep union has {len(recipe_arms)} arms but Conductor.Step has "
        f"{len(conductor_arms)} arms. The two declarations must stay one-to-one "
        f"or expansion will silently skip the new kind."
    )


@pytest.mark.architecture
def test_recipe_prefix_strip_matches_step_arm_names() -> None:
    """Every `Recipe<X>Step` arm has a matching `<X>Step` arm in the Conductor union.

    Strips the `Recipe` prefix from each arm class name and asserts
    the unprefixed name appears in `Conductor.Step`. A new
    `RecipeFooBarStep` added without a matching Conductor `FooBarStep`
    lands here.
    """
    recipe_names = {arm.__name__ for arm in get_args(_recipe_body.RecipeStep)}
    conductor_names = {arm.__name__ for arm in get_args(_conductor_module.Step)}
    stripped = {name.removeprefix("Recipe") for name in recipe_names}
    missing = stripped - conductor_names
    assert not missing, (
        f"RecipeStep arms {sorted(recipe_names)} strip to {sorted(stripped)}; "
        f"Conductor.Step declares {sorted(conductor_names)}. Missing arms in "
        f"Conductor.Step: {sorted(missing)}."
    )


@pytest.mark.architecture
def test_recipe_expansion_dispatches_every_recipe_step_arm() -> None:
    """Every `RecipeStep` arm has a matching dispatch path in `_recipe_expansion`.

    The expansion module translates each `RecipeStep` arm into its
    bound `Step` form. A new RecipeStep variant added without a
    dispatch arm in `_expand_step` would silently skip the kind at
    expansion. Until the expansion module is authored the check is
    SKIPPED (the union arity + name parity gates above cover the
    structural shape).
    """
    expansion_module = pytest.importorskip(
        "cora.operation._recipe_expansion._expand",
        reason="recipe-expansion module not present yet; dispatch-coverage check pending",
    )
    recipe_arms = get_args(_recipe_body.RecipeStep)
    expander = getattr(expansion_module, "_expand_step", None)
    assert expander is not None, (
        "cora.operation._recipe_expansion._expand is missing the _expand_step dispatch helper; "
        "the expansion module must export it so this fitness can verify dispatch coverage."
    )
    source = inspect.getsource(expander)
    missing = [arm.__name__ for arm in recipe_arms if arm.__name__ not in source]
    assert not missing, (
        f"_recipe_expansion._expand_step source omits dispatch for RecipeStep arms: "
        f"{sorted(missing)}. Add an isinstance arm per missing variant."
    )
