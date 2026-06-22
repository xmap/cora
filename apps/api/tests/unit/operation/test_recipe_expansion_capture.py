"""Unit tests for capture-step / CaptureRef handling in the recipe expander.

`expand` bridges Recipe BC templates to Conductor `Step`s. A
`RecipeCaptureStep` becomes a `CaptureStep`; a `CaptureRef` setpoint value
rides through UNRESOLVED (unlike a `BindingRef`, which is substituted at
expansion). `steps_to_wire` must serialize both deterministically so the
determinism hash is stable across re-expansion.
"""

from __future__ import annotations

import hashlib

import pytest

from cora.operation._recipe_expansion import canonical_json_bytes, expand, steps_to_wire
from cora.operation.conductor import CaptureStep, SetpointStep
from cora.recipe.aggregates.recipe.body import (
    CaptureRef,
    RecipeCaptureStep,
    RecipeSetpointStep,
)


@pytest.mark.unit
def test_expand_maps_recipe_capture_step_to_capture_step() -> None:
    steps = (RecipeCaptureStep(address="dev:sample:x", capture_name="home"),)
    expanded = expand(steps, {})
    assert expanded == (CaptureStep(address="dev:sample:x", capture_name="home"),)


@pytest.mark.unit
def test_expand_passes_capture_ref_setpoint_value_through_unresolved() -> None:
    """A CaptureRef survives expansion (resolved later by the Conductor)."""
    steps = (RecipeSetpointStep(address="dev:sample:x", value=CaptureRef("home")),)
    expanded = expand(steps, {})
    head = expanded[0]
    assert isinstance(head, SetpointStep)
    assert head.value == CaptureRef("home")


@pytest.mark.unit
def test_steps_to_wire_hash_is_stable_for_capture_steps() -> None:
    """Re-expanding the same capture recipe yields a byte-identical hash."""
    steps = (
        RecipeCaptureStep(address="dev:sample:x", capture_name="home"),
        RecipeSetpointStep(address="dev:sample:x", value=20.0),
        RecipeSetpointStep(address="dev:sample:x", value=CaptureRef("home")),
    )

    def _hash() -> str:
        return hashlib.sha256(canonical_json_bytes(steps_to_wire(expand(steps, {})))).hexdigest()

    assert _hash() == _hash()


@pytest.mark.unit
def test_steps_to_wire_encodes_capture_ref_as_a_sentinel_not_a_bare_value() -> None:
    """The CaptureRef wire form is distinct from any literal, so the hash can't alias."""
    wire = steps_to_wire(expand((RecipeSetpointStep(address="d:x", value=CaptureRef("home")),), {}))
    assert wire[0]["value"] == {"__capture__": "home"}
