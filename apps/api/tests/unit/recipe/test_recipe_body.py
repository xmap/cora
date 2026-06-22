"""Unit tests for `cora.recipe.aggregates.recipe.body`: RecipeStep VOs + wire-format roundtrip."""

import pytest

from cora.recipe.aggregates.recipe import (
    BindingRef,
    CaptureRef,
    DuplicateRecipeCaptureError,
    InvalidRecipeStepShapeError,
    RecipeActionStep,
    RecipeCaptureStep,
    RecipeCheckStep,
    RecipeSetpointStep,
    UnboundRecipeBindingError,
    UnboundRecipeCaptureError,
    resolve_value,
    steps_from_dict,
    steps_to_dict,
    validate_capture_refs,
)


@pytest.mark.unit
def test_binding_ref_is_a_value_object() -> None:
    a = BindingRef("dwell")
    b = BindingRef("dwell")
    c = BindingRef("repetitions")
    assert a == b
    assert a != c
    assert hash(a) == hash(b)


@pytest.mark.unit
def test_recipe_setpoint_step_default_verify_false() -> None:
    step = RecipeSetpointStep(address="dev:rot:val", value=1.0)
    assert step.verify is False


@pytest.mark.unit
def test_recipe_setpoint_step_accepts_literal_and_binding_value() -> None:
    literal = RecipeSetpointStep(address="dev:rot:val", value=1.0)
    bound = RecipeSetpointStep(address="dev:rot:val", value=BindingRef("angle"))
    assert literal.value == 1.0
    assert isinstance(bound.value, BindingRef)


@pytest.mark.unit
def test_recipe_action_step_params_default_empty() -> None:
    step = RecipeActionStep(name="wait")
    assert step.params == {}


@pytest.mark.unit
def test_recipe_action_step_params_can_carry_binding_refs() -> None:
    step = RecipeActionStep(name="wait", params={"seconds": BindingRef("dwell")})
    assert isinstance(step.params["seconds"], BindingRef)


@pytest.mark.unit
def test_recipe_check_step_carries_criterion_dict() -> None:
    step = RecipeCheckStep(address="dev:rot:val", criterion={"kind": "equals", "expected": 1.0})
    assert step.criterion["kind"] == "equals"


@pytest.mark.unit
def test_to_dict_from_dict_roundtrip_preserves_setpoint_step_literal_value() -> None:
    steps = (RecipeSetpointStep(address="dev:rot:val", value=1.0, verify=True),)
    rebuilt = steps_from_dict(steps_to_dict(steps))
    assert rebuilt == steps


@pytest.mark.unit
def test_to_dict_from_dict_roundtrip_preserves_setpoint_binding_ref() -> None:
    steps = (RecipeSetpointStep(address="dev:rot:val", value=BindingRef("angle")),)
    rebuilt = steps_from_dict(steps_to_dict(steps))
    assert rebuilt == steps
    head = rebuilt[0]
    assert isinstance(head, RecipeSetpointStep)
    assert isinstance(head.value, BindingRef)


@pytest.mark.unit
def test_capture_ref_is_a_value_object() -> None:
    a = CaptureRef("home")
    b = CaptureRef("home")
    c = CaptureRef("out")
    assert a == b
    assert a != c


@pytest.mark.unit
def test_recipe_setpoint_step_accepts_capture_ref_value() -> None:
    step = RecipeSetpointStep(address="dev:sample:x", value=CaptureRef("home"))
    assert isinstance(step.value, CaptureRef)
    assert step.value.capture_name == "home"


@pytest.mark.unit
def test_resolve_value_passes_capture_ref_through_unchanged() -> None:
    """Expansion relies on this: a CaptureRef is NOT resolved at expansion time."""
    ref = CaptureRef("home")
    assert resolve_value(ref, {"home": 12.5}) is ref


@pytest.mark.unit
def test_to_dict_from_dict_roundtrip_preserves_capture_step() -> None:
    steps = (RecipeCaptureStep(address="dev:sample:x", capture_name="home"),)
    rebuilt = steps_from_dict(steps_to_dict(steps))
    assert rebuilt == steps


@pytest.mark.unit
def test_to_dict_from_dict_roundtrip_preserves_setpoint_capture_ref() -> None:
    steps = (RecipeSetpointStep(address="dev:sample:x", value=CaptureRef("home")),)
    rebuilt = steps_from_dict(steps_to_dict(steps))
    assert rebuilt == steps
    head = rebuilt[0]
    assert isinstance(head, RecipeSetpointStep)
    assert isinstance(head.value, CaptureRef)
    assert head.value.capture_name == "home"


@pytest.mark.unit
def test_validate_capture_refs_accepts_capture_declared_before_use() -> None:
    steps = (
        RecipeCaptureStep(address="dev:sample:x", capture_name="home"),
        RecipeSetpointStep(address="dev:sample:x", value=20.0),
        RecipeSetpointStep(address="dev:sample:x", value=CaptureRef("home")),
    )
    validate_capture_refs(steps)  # does not raise


@pytest.mark.unit
def test_validate_capture_refs_rejects_forward_or_missing_reference() -> None:
    steps = (RecipeSetpointStep(address="dev:sample:x", value=CaptureRef("home")),)
    with pytest.raises(UnboundRecipeCaptureError, match="home"):
        validate_capture_refs(steps)


@pytest.mark.unit
def test_validate_capture_refs_rejects_use_before_its_own_capture() -> None:
    """A CaptureRef must reference a capture EARLIER in the sequence, not later."""
    steps = (
        RecipeSetpointStep(address="dev:sample:x", value=CaptureRef("home")),
        RecipeCaptureStep(address="dev:sample:x", capture_name="home"),
    )
    with pytest.raises(UnboundRecipeCaptureError):
        validate_capture_refs(steps)


@pytest.mark.unit
def test_validate_capture_refs_rejects_duplicate_capture_name() -> None:
    steps = (
        RecipeCaptureStep(address="dev:sample:x", capture_name="home"),
        RecipeCaptureStep(address="dev:sample:x", capture_name="home"),
    )
    with pytest.raises(DuplicateRecipeCaptureError, match="home"):
        validate_capture_refs(steps)


@pytest.mark.unit
def test_to_dict_from_dict_roundtrip_preserves_action_step_with_mixed_params() -> None:
    steps = (
        RecipeActionStep(
            name="wait",
            params={"seconds": BindingRef("dwell"), "label": "settle"},
        ),
    )
    rebuilt = steps_from_dict(steps_to_dict(steps))
    assert rebuilt == steps


@pytest.mark.unit
def test_to_dict_from_dict_roundtrip_preserves_check_step() -> None:
    steps = (
        RecipeCheckStep(
            address="dev:rot:val",
            criterion={"kind": "equals", "expected": 1.0},
        ),
    )
    rebuilt = steps_from_dict(steps_to_dict(steps))
    assert rebuilt == steps


@pytest.mark.unit
def test_to_dict_from_dict_roundtrip_preserves_multi_step_sequence() -> None:
    steps = (
        RecipeSetpointStep(address="dev:rot:val", value=BindingRef("angle")),
        RecipeActionStep(name="acquire", params={"dwell": BindingRef("dwell")}),
        RecipeCheckStep(address="dev:rot:val", criterion={"kind": "equals", "expected": 1.0}),
    )
    rebuilt = steps_from_dict(steps_to_dict(steps))
    assert rebuilt == steps


@pytest.mark.unit
def test_from_dict_rejects_missing_steps_key() -> None:
    with pytest.raises(InvalidRecipeStepShapeError):
        steps_from_dict({})


@pytest.mark.unit
def test_from_dict_rejects_step_missing_kind() -> None:
    with pytest.raises(InvalidRecipeStepShapeError):
        steps_from_dict({"steps": [{"address": "x"}]})


@pytest.mark.unit
def test_from_dict_rejects_unknown_step_kind() -> None:
    with pytest.raises(InvalidRecipeStepShapeError) as exc:
        steps_from_dict({"steps": [{"kind": "wait"}]})
    assert "unknown" in str(exc.value).lower()


@pytest.mark.unit
def test_from_dict_rejects_setpoint_missing_address() -> None:
    with pytest.raises(InvalidRecipeStepShapeError):
        steps_from_dict({"steps": [{"kind": "setpoint", "value": 1.0}]})


@pytest.mark.unit
def test_from_dict_returns_empty_tuple_when_steps_list_empty() -> None:
    """body.from_dict does NOT enforce non-emptiness; Recipe.__post_init__ does."""
    rebuilt = steps_from_dict({"steps": []})
    assert rebuilt == ()


@pytest.mark.unit
def test_resolve_value_returns_literal_unchanged() -> None:
    assert resolve_value(1.0, {}) == 1.0


@pytest.mark.unit
def test_resolve_value_returns_mapped_value_for_binding_ref() -> None:
    assert resolve_value(BindingRef("dwell"), {"dwell": 2.5}) == 2.5


@pytest.mark.unit
def test_resolve_value_raises_when_binding_name_missing() -> None:
    with pytest.raises(UnboundRecipeBindingError) as exc:
        resolve_value(BindingRef("dwell"), {})
    assert exc.value.name == "dwell"
