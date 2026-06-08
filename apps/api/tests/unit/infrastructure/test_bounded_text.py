"""Unit tests for `cora.shared.bounded_text`.

Coverage:
  - `validate_bounded_text`: trim, empty rejection, over-length rejection,
    error_class receives ORIGINAL untrimmed value.
  - `bounded_name` decorator: happy path, trimming, empty-after-trim,
    over-length, isinstance distinction across decorations, dataclass
    eq/hash/repr preserved, frozen immutability preserved, user-defined
    `__post_init__` chains and sees the trimmed value, decoration-time
    guards for missing `@dataclass` and missing `value` field, decorator
    works at all currently-used MAX_LENGTH values, pattern matching via
    `__match_args__` survives, decorated class is still a dataclass.
"""

from dataclasses import FrozenInstanceError, dataclass, is_dataclass

import pytest

from cora.shared.bounded_text import bounded_name, validate_bounded_text

# ---------- validate_bounded_text (function) ----------


class _InvalidTextError(ValueError):
    def __init__(self, value: str) -> None:
        super().__init__(f"invalid: {value!r}")
        self.value = value


@pytest.mark.unit
def test_validate_bounded_text_returns_trimmed_value() -> None:
    assert validate_bounded_text("  foo  ", max_length=10, error_class=_InvalidTextError) == "foo"


@pytest.mark.unit
def test_validate_bounded_text_returns_input_when_no_whitespace() -> None:
    assert validate_bounded_text("foo", max_length=10, error_class=_InvalidTextError) == "foo"


@pytest.mark.unit
def test_validate_bounded_text_rejects_empty_string() -> None:
    with pytest.raises(_InvalidTextError) as excinfo:
        validate_bounded_text("", max_length=10, error_class=_InvalidTextError)
    assert excinfo.value.value == ""


@pytest.mark.unit
def test_validate_bounded_text_rejects_whitespace_only_with_original_value() -> None:
    with pytest.raises(_InvalidTextError) as excinfo:
        validate_bounded_text("   ", max_length=10, error_class=_InvalidTextError)
    assert excinfo.value.value == "   "


@pytest.mark.unit
def test_validate_bounded_text_rejects_over_length_with_original_value() -> None:
    over = "x" * 11
    with pytest.raises(_InvalidTextError) as excinfo:
        validate_bounded_text(over, max_length=10, error_class=_InvalidTextError)
    assert excinfo.value.value == over


@pytest.mark.unit
def test_validate_bounded_text_accepts_max_length_exactly() -> None:
    payload = "x" * 10
    assert validate_bounded_text(payload, max_length=10, error_class=_InvalidTextError) == payload


# ---------- bounded_name decorator: shared fixtures ----------


class InvalidPolicyNameError(ValueError):
    def __init__(self, value: str) -> None:
        super().__init__(f"Policy name must be 1-200 chars after trimming (got: {value!r})")
        self.value = value


class InvalidActorNameError(ValueError):
    def __init__(self, value: str) -> None:
        super().__init__(f"Actor name must be 1-100 chars after trimming (got: {value!r})")
        self.value = value


@bounded_name(max_length=200, error_class=InvalidPolicyNameError)
@dataclass(frozen=True)
class PolicyName:
    """Display name for a policy. Trimmed; 1-200 chars."""

    value: str


@bounded_name(max_length=100, error_class=InvalidActorNameError)
@dataclass(frozen=True)
class ActorName:
    """Display name for an actor. Trimmed; 1-100 chars."""

    value: str


# ---------- bounded_name: happy path + trimming ----------


@pytest.mark.unit
def test_bounded_name_happy_path_returns_dataclass_instance() -> None:
    assert PolicyName("foo") == PolicyName(value="foo")


@pytest.mark.unit
def test_bounded_name_trims_leading_and_trailing_whitespace() -> None:
    assert PolicyName("  foo  ").value == "foo"


@pytest.mark.unit
def test_bounded_name_trims_tabs_and_newlines() -> None:
    assert PolicyName("\tfoo\n").value == "foo"


@pytest.mark.unit
def test_bounded_name_preserves_internal_whitespace() -> None:
    assert PolicyName("  foo bar  ").value == "foo bar"


# ---------- bounded_name: rejection cases pass ORIGINAL value to error_class ----------


@pytest.mark.unit
def test_bounded_name_empty_string_raises_with_original_value() -> None:
    with pytest.raises(InvalidPolicyNameError) as excinfo:
        PolicyName("")
    assert excinfo.value.value == ""


@pytest.mark.unit
def test_bounded_name_whitespace_only_raises_with_original_untrimmed_value() -> None:
    with pytest.raises(InvalidPolicyNameError) as excinfo:
        PolicyName("   ")
    assert excinfo.value.value == "   "


@pytest.mark.unit
def test_bounded_name_over_length_raises_with_original_untrimmed_value() -> None:
    over = "x" * 201
    with pytest.raises(InvalidPolicyNameError) as excinfo:
        PolicyName(over)
    assert excinfo.value.value == over


@pytest.mark.unit
def test_bounded_name_over_length_after_trim_uses_trimmed_length_for_check() -> None:
    payload = "  " + "x" * 200 + "  "
    assert PolicyName(payload).value == "x" * 200


# ---------- bounded_name: isinstance + class identity ----------


@pytest.mark.unit
def test_bounded_name_isinstance_same_class_is_true() -> None:
    assert isinstance(PolicyName("x"), PolicyName)


@pytest.mark.unit
def test_bounded_name_isinstance_different_decorated_classes_distinct() -> None:
    assert not isinstance(PolicyName("x"), ActorName)
    assert not isinstance(ActorName("x"), PolicyName)


@pytest.mark.unit
def test_bounded_name_preserves_class_identity() -> None:
    """Decorator patches in place; PolicyName is the user-authored class."""
    assert PolicyName.__name__ == "PolicyName"
    assert PolicyName.__qualname__ == "PolicyName"
    assert "policy" in (PolicyName.__doc__ or "").lower()


# ---------- bounded_name: dataclass-synthesized dunders preserved ----------


@pytest.mark.unit
def test_bounded_name_equal_values_compare_equal() -> None:
    assert PolicyName("foo") == PolicyName("foo")


@pytest.mark.unit
def test_bounded_name_different_values_compare_unequal() -> None:
    assert PolicyName("foo") != PolicyName("bar")


@pytest.mark.unit
def test_bounded_name_cross_type_equality_is_false_even_for_same_value() -> None:
    assert PolicyName("x") != ActorName("x")


@pytest.mark.unit
def test_bounded_name_hash_works_and_matches_equal_values() -> None:
    assert hash(PolicyName("foo")) == hash(PolicyName("foo"))


@pytest.mark.unit
def test_bounded_name_instances_usable_as_dict_keys() -> None:
    d = {PolicyName("foo"): 1}
    assert d[PolicyName("foo")] == 1


@pytest.mark.unit
def test_bounded_name_repr_includes_class_name_and_field() -> None:
    rendered = repr(PolicyName("foo"))
    assert "PolicyName" in rendered
    assert "foo" in rendered


@pytest.mark.unit
def test_bounded_name_frozen_assignment_raises_frozen_instance_error() -> None:
    instance = PolicyName("x")
    with pytest.raises(FrozenInstanceError):
        instance.value = "mut"  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.unit
def test_bounded_name_decorated_class_is_still_a_dataclass() -> None:
    assert is_dataclass(PolicyName)


@pytest.mark.unit
def test_bounded_name_match_args_preserved_for_pattern_matching() -> None:
    assert PolicyName.__match_args__ == ("value",)
    matched = None
    match PolicyName("hello"):
        case PolicyName(value=v):
            matched = v
    assert matched == "hello"


# ---------- bounded_name: chaining with user-defined __post_init__ ----------


@pytest.mark.unit
def test_bounded_name_user_post_init_sees_trimmed_value() -> None:
    """Init-wrap stores trimmed value BEFORE the synthesized __init__ calls
    the user's __post_init__, so user code observes the canonical form.
    """
    observed: list[str] = []

    @bounded_name(max_length=100, error_class=InvalidPolicyNameError)
    @dataclass(frozen=True)
    class WithPostInit:
        value: str

        def __post_init__(self) -> None:
            observed.append(self.value)

    WithPostInit("  bar  ")
    assert observed == ["bar"]


# ---------- bounded_name: decoration-time guards ----------


@pytest.mark.unit
def test_bounded_name_raises_when_dataclass_decorator_is_missing() -> None:
    def define_without_dataclass() -> type:
        @bounded_name(max_length=10, error_class=InvalidPolicyNameError)
        class NotADataclass:
            value: str

        return NotADataclass

    with pytest.raises(TypeError, match="must be applied above @dataclass"):
        define_without_dataclass()


@pytest.mark.unit
def test_bounded_name_raises_when_decorator_order_is_reversed() -> None:
    """`@dataclass` below `@bounded_name` is the load-bearing mistake to
    catch: silently produces a non-validating class without the guard."""

    def define_reversed() -> type:
        @dataclass(frozen=True)
        @bounded_name(max_length=10, error_class=InvalidPolicyNameError)
        class Reversed:
            value: str

        return Reversed

    with pytest.raises(TypeError, match="must be applied above @dataclass"):
        define_reversed()


@pytest.mark.unit
def test_bounded_name_raises_when_value_field_is_missing() -> None:
    def define_without_value() -> type:
        @bounded_name(max_length=10, error_class=InvalidPolicyNameError)
        @dataclass(frozen=True)
        class NoValueField:
            name: str

        return NoValueField

    with pytest.raises(TypeError, match="requires a `value` field"):
        define_without_value()


# ---------- bounded_name: works at every currently-used MAX_LENGTH ----------


@pytest.mark.unit
@pytest.mark.parametrize("max_length", [50, 100, 200, 255, 2000])
def test_bounded_name_works_at_each_current_max_length(max_length: int) -> None:
    @bounded_name(max_length=max_length, error_class=InvalidPolicyNameError)
    @dataclass(frozen=True)
    class Sized:
        value: str

    payload = "x" * max_length
    assert Sized(payload).value == payload

    over = "x" * (max_length + 1)
    with pytest.raises(InvalidPolicyNameError):
        Sized(over)
