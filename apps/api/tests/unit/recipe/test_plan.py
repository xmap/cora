"""PlanName VO + PlanStatus enum + transition error class tests."""

from uuid import uuid4

import pytest

from cora.recipe.aggregates.plan import (
    InvalidPlanNameError,
    InvalidPlanVersionTagError,
    PlanCannotDeprecateError,
    PlanCannotVersionError,
    PlanName,
    PlanStatus,
)

# ---------- PlanName VO ----------


@pytest.mark.unit
def test_plan_name_accepts_normal_string() -> None:
    name = PlanName("32-ID XRF FlyScan with Eiger + SampleStage")
    assert name.value == "32-ID XRF FlyScan with Eiger + SampleStage"


@pytest.mark.unit
def test_plan_name_trims_whitespace() -> None:
    name = PlanName("  32-ID XRF FlyScan  ")
    assert name.value == "32-ID XRF FlyScan"


@pytest.mark.unit
def test_plan_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidPlanNameError):
        PlanName("")


@pytest.mark.unit
def test_plan_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidPlanNameError):
        PlanName("   \t\n   ")


@pytest.mark.unit
def test_plan_name_rejects_too_long() -> None:
    with pytest.raises(InvalidPlanNameError):
        PlanName("a" * 201)


@pytest.mark.unit
def test_plan_name_accepts_max_length() -> None:
    name = PlanName("a" * 200)
    assert len(name.value) == 200


@pytest.mark.unit
def test_plan_name_is_frozen() -> None:
    name = PlanName("Standard FlyScan Plan")
    with pytest.raises(AttributeError):
        name.value = "Other"  # type: ignore[misc]


@pytest.mark.unit
def test_plan_name_uses_shared_bounded_name_decorator() -> None:
    """Pin: PlanName routes through the shared
    `cora.shared.bounded_text.bounded_name` decorator. A direct
    source inspection ensures we don't accidentally re-add the
    duplicated trim+length-check `__post_init__` ritual later."""
    import inspect

    from cora.recipe.aggregates.plan import state as plan_state

    src = inspect.getsource(plan_state)
    assert "@bounded_name(" in src
    assert "from cora.shared.bounded_text import bounded_name" in src
    assert not hasattr(PlanName, "__post_init__")


# ---------- PlanStatus enum ----------


@pytest.mark.unit
def test_plan_status_has_all_three_lifecycle_values() -> None:
    """Mirrors Method / Practice / Family lifecycle vocabulary
    (gate-review Q2: structural lifecycle only; approval lives in
    Decision BC)."""
    assert {s.value for s in PlanStatus} == {"Defined", "Versioned", "Deprecated"}


@pytest.mark.unit
def test_plan_status_values_are_pascal_case_strings() -> None:
    assert PlanStatus.DEFINED == "Defined"
    assert PlanStatus.VERSIONED == "Versioned"
    assert PlanStatus.DEPRECATED == "Deprecated"


@pytest.mark.unit
def test_plan_status_is_str_enum_for_natural_serialization() -> None:
    assert isinstance(PlanStatus.DEFINED, str)
    assert PlanStatus.DEFINED == "Defined"
    assert f"{PlanStatus.VERSIONED}" == "Versioned"


@pytest.mark.unit
def test_plan_status_can_be_constructed_from_string_value() -> None:
    for status in PlanStatus:
        assert PlanStatus(status.value) == status


# ---------- Transition error classes ----------


@pytest.mark.unit
def test_plan_cannot_version_error_carries_plan_id_and_current_status() -> None:
    plan_id = uuid4()
    err = PlanCannotVersionError(plan_id, current_status=PlanStatus.DEPRECATED)
    assert err.plan_id == plan_id
    assert err.current_status is PlanStatus.DEPRECATED
    msg = str(err)
    assert "Deprecated" in msg
    assert "Defined" in msg
    assert "Versioned" in msg


@pytest.mark.unit
def test_plan_cannot_deprecate_error_carries_plan_id_and_current_status() -> None:
    plan_id = uuid4()
    err = PlanCannotDeprecateError(plan_id, current_status=PlanStatus.DEPRECATED)
    assert err.plan_id == plan_id
    assert err.current_status is PlanStatus.DEPRECATED
    msg = str(err)
    assert "Deprecated" in msg
    assert "Defined" in msg
    assert "Versioned" in msg


@pytest.mark.unit
def test_invalid_plan_version_tag_error_carries_value() -> None:
    err = InvalidPlanVersionTagError("   ")
    assert err.value == "   "
    msg = str(err)
    assert "Plan version tag" in msg
    assert "1-50" in msg
