"""A check step's deadline must reach the determinism hash.

`RecipeCheckStep.timeout_s` documents that it "rides expansion and the
determinism hash like any other authored value, so a recipe whose deadline
changed is a different recipe". `steps_to_wire` dropped it, so two recipes
differing only in their deadline hashed identically and a re-expansion could
not tell them apart.

The field is emitted only when set, so every recipe authored before it
existed keeps its exact prior wire form and its pinned `steps_hash` stays
valid. These pin both halves: the deadline is visible when present, and
invisible when absent.
"""

from __future__ import annotations

import hashlib

import pytest

from cora.operation._recipe_expansion import canonical_json_bytes, expand, steps_to_wire
from cora.recipe.aggregates.recipe.body import RecipeCheckStep

_CRITERION = {"kind": "equals", "expected": "ON"}


def _hash(steps: tuple[RecipeCheckStep, ...]) -> str:
    return hashlib.sha256(canonical_json_bytes(steps_to_wire(expand(steps, {})))).hexdigest()


@pytest.mark.unit
def test_steps_to_wire_carries_a_check_deadline_into_the_hashed_form() -> None:
    wire = steps_to_wire(
        expand((RecipeCheckStep(address="2bmb:m1.DMOV", criterion=_CRITERION, timeout_s=60.0),), {})
    )

    assert wire[0]["timeout_s"] == 60.0


@pytest.mark.unit
def test_steps_to_wire_omits_the_deadline_key_when_a_check_has_none() -> None:
    """Absence keeps the wire form byte-identical to what every pre-deadline
    recipe already hashed, so no pinned expansion is invalidated."""
    wire = steps_to_wire(
        expand((RecipeCheckStep(address="2bmb:m1.DMOV", criterion=_CRITERION),), {})
    )

    assert "timeout_s" not in wire[0]


@pytest.mark.unit
def test_two_recipes_differing_only_in_deadline_hash_differently() -> None:
    """The property the docstring promises: a changed deadline is a changed
    recipe. This was false, and a resumed conduct re-ran the check with no
    wait at all."""
    slow = (RecipeCheckStep(address="2bmb:m1.DMOV", criterion=_CRITERION, timeout_s=60.0),)
    quick = (RecipeCheckStep(address="2bmb:m1.DMOV", criterion=_CRITERION, timeout_s=5.0),)

    assert _hash(slow) != _hash(quick)


@pytest.mark.unit
def test_a_deadlineless_check_hashes_the_same_as_it_always_did() -> None:
    """Pins the migration claim directly: the hash of a check with no deadline
    is the hash of the three-key wire form that predates the field."""
    steps = (RecipeCheckStep(address="2bmb:m1.DMOV", criterion=_CRITERION),)
    legacy_form = [{"kind": "check", "address": "2bmb:m1.DMOV", "criterion": _CRITERION}]

    assert _hash(steps) == hashlib.sha256(canonical_json_bytes(legacy_form)).hexdigest()
