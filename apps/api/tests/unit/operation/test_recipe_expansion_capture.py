"""Unit tests for capture-step / CaptureRef handling in the recipe expander.

`expand` bridges Recipe BC templates to Conductor `Step`s. A
`RecipeCaptureStep` becomes a `CaptureStep`; a `CaptureRef` setpoint value, or
a `CaptureRef`/`SteeringRef` nested in a compute step's `parameters`, rides
through UNRESOLVED (unlike a `BindingRef`, which is substituted at
expansion). `steps_to_wire` must serialize all of these deterministically so
the determinism hash is stable across re-expansion.
"""

from __future__ import annotations

import hashlib

import pytest

from cora.operation._recipe_expansion import canonical_json_bytes, expand, steps_to_wire
from cora.operation.conductor import CaptureStep, ComputeStep, SetpointStep
from cora.recipe.aggregates.recipe.body import (
    CaptureRef,
    RecipeCaptureStep,
    RecipeComputeStep,
    RecipeSetpointStep,
    SteeringRef,
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


@pytest.mark.unit
def test_expand_passes_capture_ref_compute_parameter_through_unresolved() -> None:
    """A CaptureRef nested in a compute step's parameters survives expansion too."""
    steps = (
        RecipeComputeStep(
            command=("tomopy", "recon"),
            parameters={"rotation_center": CaptureRef("home")},
        ),
    )
    expanded = expand(steps, {})
    head = expanded[0]
    assert isinstance(head, ComputeStep)
    assert head.parameters == {"rotation_center": CaptureRef("home")}


@pytest.mark.unit
def test_expand_passes_steering_ref_compute_parameter_through_unresolved() -> None:
    """A SteeringRef nested in a compute step's parameters survives expansion too."""
    steps = (
        RecipeComputeStep(
            command=("tomopy", "recon"),
            parameters={"seed": SteeringRef("focus")},
        ),
    )
    expanded = expand(steps, {})
    head = expanded[0]
    assert isinstance(head, ComputeStep)
    assert head.parameters == {"seed": SteeringRef("focus")}


@pytest.mark.unit
def test_steps_to_wire_hash_is_stable_for_compute_parameter_capture_ref() -> None:
    """Re-expanding the same compute-parameter recipe yields a byte-identical hash."""
    steps = (
        RecipeCaptureStep(address="dev:sample:x", capture_name="home"),
        RecipeComputeStep(
            command=("tomopy", "recon"),
            parameters={"rotation_center": CaptureRef("home")},
        ),
    )

    def _hash() -> str:
        return hashlib.sha256(canonical_json_bytes(steps_to_wire(expand(steps, {})))).hexdigest()

    assert _hash() == _hash()


@pytest.mark.unit
def test_steps_to_wire_encodes_compute_parameter_capture_ref_as_a_sentinel() -> None:
    """The CaptureRef wire form inside parameters matches the setpoint-value sentinel shape."""
    steps = (
        RecipeComputeStep(
            command=("tomopy", "recon"),
            parameters={"rotation_center": CaptureRef("home"), "seed": SteeringRef("focus")},
        ),
    )
    wire = steps_to_wire(expand(steps, {}))
    assert wire[0]["parameters"] == {
        "rotation_center": {"__capture__": "home"},
        "seed": {"__steering__": "focus"},
    }


@pytest.mark.unit
def test_steps_to_wire_literal_only_compute_parameters_unchanged() -> None:
    """A literal-only parameters dict hashes byte-identical to before this feature.

    Backward-compat pin: no existing pinned steps_hash may be invalidated by
    the new per-value wire encoder.
    """
    steps = (RecipeComputeStep(command=("tomopy", "recon"), parameters={"algorithm": "sirt"}),)
    wire = steps_to_wire(expand(steps, {}))
    assert wire[0]["parameters"] == {"algorithm": "sirt"}
