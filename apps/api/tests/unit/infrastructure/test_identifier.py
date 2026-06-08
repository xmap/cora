"""Unit tests for `cora.shared.identifier`.

Coverage:
  - Happy path construction of `Identifier(scheme, value)`.
  - Trim semantics on both `scheme` and `value`.
  - Rejection of empty, whitespace-only, and over-length scheme + value,
    with the ORIGINAL untrimmed input preserved on the raised error.
  - Equality, hash, and frozen-immutability behaviour of the dataclass.
  - Distinct-type discipline: an Identifier is NOT equal to a bare string
    or to a sibling 2-field VO with the same field values.
"""

from dataclasses import FrozenInstanceError, dataclass

import pytest

from cora.shared.identifier import (
    IDENTIFIER_SCHEME_MAX_LENGTH,
    IDENTIFIER_VALUE_MAX_LENGTH,
    Identifier,
    InvalidIdentifierError,
)


@pytest.mark.unit
def test_identifier_happy_path_constructs_scheme_value_pair() -> None:
    ident = Identifier("doi", "10.1234/abc")
    assert ident.scheme == "doi"
    assert ident.value == "10.1234/abc"


@pytest.mark.unit
def test_identifier_trims_both_fields() -> None:
    ident = Identifier("  doi  ", "  10.1234/abc  ")
    assert ident.scheme == "doi"
    assert ident.value == "10.1234/abc"


@pytest.mark.unit
def test_identifier_rejects_empty_scheme_with_original_value() -> None:
    with pytest.raises(InvalidIdentifierError) as excinfo:
        Identifier("", "x")
    assert excinfo.value.field == "scheme"
    assert excinfo.value.value == ""


@pytest.mark.unit
def test_identifier_rejects_whitespace_only_scheme_with_original_value() -> None:
    with pytest.raises(InvalidIdentifierError) as excinfo:
        Identifier("   ", "x")
    assert excinfo.value.field == "scheme"
    assert excinfo.value.value == "   "


@pytest.mark.unit
def test_identifier_rejects_over_length_scheme_with_original_value() -> None:
    over_length_scheme = "a" * (IDENTIFIER_SCHEME_MAX_LENGTH + 1)
    with pytest.raises(InvalidIdentifierError) as excinfo:
        Identifier(over_length_scheme, "x")
    assert excinfo.value.field == "scheme"
    assert excinfo.value.value == over_length_scheme


@pytest.mark.unit
def test_identifier_rejects_empty_value_with_original_value() -> None:
    with pytest.raises(InvalidIdentifierError) as excinfo:
        Identifier("doi", "")
    assert excinfo.value.field == "value"
    assert excinfo.value.value == ""


@pytest.mark.unit
def test_identifier_rejects_over_length_value_with_original_value() -> None:
    over_length_value = "a" * (IDENTIFIER_VALUE_MAX_LENGTH + 1)
    with pytest.raises(InvalidIdentifierError) as excinfo:
        Identifier("doi", over_length_value)
    assert excinfo.value.field == "value"
    assert excinfo.value.value == over_length_value


@pytest.mark.unit
def test_identifier_equality_holds_on_matching_fields() -> None:
    assert Identifier("doi", "x") == Identifier("doi", "x")


@pytest.mark.unit
def test_identifier_inequality_holds_on_differing_fields() -> None:
    assert Identifier("doi", "x") != Identifier("doi", "y")
    assert Identifier("doi", "x") != Identifier("handle", "x")


@pytest.mark.unit
def test_identifier_is_hashable_and_works_in_frozenset() -> None:
    a = Identifier("doi", "x")
    b = Identifier("doi", "x")
    c = Identifier("handle", "x")
    assert hash(a) == hash(b)
    assert {a, b, c} == {a, c}


@pytest.mark.unit
def test_identifier_scheme_assignment_is_frozen() -> None:
    ident = Identifier("doi", "x")
    with pytest.raises(FrozenInstanceError):
        ident.scheme = "handle"  # type: ignore[misc]


@pytest.mark.unit
def test_identifier_value_assignment_is_frozen() -> None:
    ident = Identifier("doi", "x")
    with pytest.raises(FrozenInstanceError):
        ident.value = "y"  # type: ignore[misc]


@pytest.mark.unit
def test_identifier_not_equal_to_bare_string() -> None:
    ident = Identifier("doi", "x")
    assert ident != "doi"
    assert ident != "x"
    assert ident != ("doi", "x")


@pytest.mark.unit
def test_identifier_not_equal_to_sibling_two_field_vo() -> None:
    @dataclass(frozen=True, slots=True)
    class _LookAlike:
        scheme: str
        value: str

    assert Identifier("doi", "x") != _LookAlike(scheme="doi", value="x")
