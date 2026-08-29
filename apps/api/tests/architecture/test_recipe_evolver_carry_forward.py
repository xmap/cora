"""Architecture fitness: every non-genesis arm of the Recipe evolver MUST
carry all additive state fields through from prior state.

`Procedure` and `Run` have this guard; `Recipe` did not, so a new field on
the aggregate would be silently wiped to its default by the `RecipeVersioned`
and `RecipeDeprecated` arms on the next replay with nothing failing. The only
coverage was hand-parametrized behaviour tests in
`tests/unit/recipe/test_recipe_evolver.py`, which catch exactly the arms
someone remembered to write a case for.

That matters more than the current arm count suggests. Both non-genesis arms
rebuild `Recipe(...)` field by field, and the aggregate is the authoring
surface for conduct step lists, so it is where an additive field lands next.
The sibling bug class is already documented in this tree: a hand-copied field
list in the Conductor's wrapper terminals dropped `substrate_writes`, and both
step serializers dropped `CheckStep.timeout_s`, in both cases with a green
suite.

## What is checked

For every `case <EventName>(...):` arm in `evolve` that builds a
`return Recipe(...)`:

  - the genesis arm (`RecipeDefined`) is exempt: it writes or defaults
    every field at initial-state construction.
  - every other arm MUST pass `<field>=prior.<field>` for each field,
    UNLESS the arm is a declared per-field writer (it legitimately sets
    that field from the event).

Only `status` is treated as structural: each arm exists to change it. `id`,
`name` and `capability_id` are genuine carry-forwards here and are checked as
such, which is stricter than the Procedure twin.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from cora.recipe.aggregates.recipe.state import Recipe

_REPO_ROOT = Path(__file__).resolve().parents[4]
_EVOLVER_PATH = (
    _REPO_ROOT / "apps" / "api" / "src" / "cora" / "recipe" / "aggregates" / "recipe" / "evolver.py"
)

_GENESIS_ARM = "RecipeDefined"

#: Carry-forward fields and the arms that legitimately WRITE each. A field
#: mapped to an empty frozenset must be threaded from `prior` by every
#: non-genesis arm.
_WRITER_ARMS_PER_FIELD: dict[str, frozenset[str]] = {
    "id": frozenset(),
    "name": frozenset(),
    "capability_id": frozenset(),
    # A new version replaces the step list wholesale; that IS the event.
    "steps": frozenset({"RecipeVersioned"}),
    "version": frozenset({"RecipeVersioned"}),
    "replaced_by_recipe_id": frozenset({"RecipeDeprecated"}),
}

#: Set directly by every arm, because changing it is why the arm exists.
_STRUCTURAL_FIELDS = frozenset({"status"})


def _arm_event_type_name(case_node: ast.match_case) -> str | None:
    pattern = case_node.pattern
    if isinstance(pattern, ast.MatchClass) and isinstance(pattern.cls, ast.Name):
        return pattern.cls.id
    return None


def _return_recipe_kwargs(case_node: ast.match_case) -> dict[str, ast.expr] | None:
    """Kwargs from the `return Recipe(...)` call in this arm, or None when the
    arm constructs no Recipe (a passthrough preserves every field)."""
    for stmt in ast.walk(case_node):
        if (
            isinstance(stmt, ast.Return)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Name)
            and stmt.value.func.id == "Recipe"
        ):
            return {kw.arg: kw.value for kw in stmt.value.keywords if kw.arg is not None}
    return None


def _is_prior_attribute_access(node: ast.expr, field: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == field
        and isinstance(node.value, ast.Name)
        and node.value.id == "prior"
    )


def _find_evolve_match_cases() -> list[ast.match_case]:
    tree = ast.parse(_EVOLVER_PATH.read_text(encoding="utf-8"))
    evolve_func = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "evolve"),
        None,
    )
    assert evolve_func is not None, "Could not locate `evolve` in the Recipe evolver"
    match_stmt = next((n for n in evolve_func.body if isinstance(n, ast.Match)), None)
    assert match_stmt is not None, "Could not locate `match event:` in `evolve`"
    return list(match_stmt.cases)


@pytest.mark.architecture
def test_carry_forward_field_registry_covers_every_recipe_field() -> None:
    """`_WRITER_ARMS_PER_FIELD` must enumerate every non-structural field on
    the Recipe dataclass.

    Without this the guard below silently narrows to the fields someone
    remembered to list, so a new additive field is unchecked from the moment
    it lands and any arm that drops it passes clean. Registering a new field
    is the forcing function: it makes the author decide, per arm, between
    carrying it forward and writing it.
    """
    actual = {f.name for f in dataclasses.fields(Recipe)}
    registered = set(_WRITER_ARMS_PER_FIELD) | _STRUCTURAL_FIELDS
    unregistered = actual - registered
    stale = registered - actual
    assert not unregistered, (
        "Recipe gained field(s) the carry-forward guard does not range over, "
        "so the guard is blind to them:\n"
        + "\n".join(f"  - {f}" for f in sorted(unregistered))
        + "\n\nAdd each to `_WRITER_ARMS_PER_FIELD` (empty frozenset when no arm "
        "writes it), or to `_STRUCTURAL_FIELDS` when every arm sets it directly."
    )
    assert not stale, "The carry-forward guard names field(s) Recipe no longer has:\n" + "\n".join(
        f"  - {f}" for f in sorted(stale)
    )


@pytest.mark.architecture
def test_recipe_evolver_non_genesis_arms_carry_all_additive_fields() -> None:
    """Every non-genesis Recipe-constructing arm threads each field as
    `<field>=prior.<field>` unless it is a declared writer of that field."""
    violations: list[str] = []
    for case in _find_evolve_match_cases():
        event_name = _arm_event_type_name(case)
        if event_name is None:
            continue  # wildcard `case _:` (assert_never guard)
        if event_name == _GENESIS_ARM:
            continue  # genesis writes / defaults every field
        kwargs = _return_recipe_kwargs(case)
        if kwargs is None:
            continue  # passthrough arm; preserves every field
        for field, writer_arms in _WRITER_ARMS_PER_FIELD.items():
            if event_name in writer_arms:
                continue
            value = kwargs.get(field)
            if value is None:
                violations.append(
                    f"  - {event_name}: missing `{field}=prior.{field}` kwarg in Recipe(...)"
                )
                continue
            if not _is_prior_attribute_access(value, field):
                violations.append(
                    f"  - {event_name}: `{field}=...` is not "
                    f"`prior.{field}` (got `{ast.unparse(value)}`)"
                )
    assert not violations, (
        "Recipe evolver arms drop a state field on replay.\n"
        + "\n".join(violations)
        + "\n\nThread the field from `prior`, or declare the arm a writer of it "
        "in `_WRITER_ARMS_PER_FIELD`."
    )
