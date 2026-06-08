"""Unit tests for the PersistentIdentifier VO and its scheme enum."""

from dataclasses import FrozenInstanceError

import pytest

from cora.shared.identifier import (
    PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH,
    InvalidPersistentIdentifierValueError,
    PersistentIdentifier,
    PersistentIdentifierScheme,
)

pytestmark = pytest.mark.timeout(60, method="thread")


@pytest.mark.unit
def test_persistent_identifier_with_valid_doi_value_constructs() -> None:
    pid = PersistentIdentifier(
        scheme=PersistentIdentifierScheme.DOI,
        value="10.5281/zenodo.1234567",
    )
    assert pid.scheme is PersistentIdentifierScheme.DOI
    assert pid.value == "10.5281/zenodo.1234567"


@pytest.mark.unit
def test_persistent_identifier_with_valid_handle_value_constructs() -> None:
    pid = PersistentIdentifier(
        scheme=PersistentIdentifierScheme.HANDLE,
        value="20.500.12613/12345",
    )
    assert pid.scheme is PersistentIdentifierScheme.HANDLE
    assert pid.value == "20.500.12613/12345"


@pytest.mark.unit
def test_persistent_identifier_with_empty_value_raises_invalid_value_error() -> None:
    with pytest.raises(InvalidPersistentIdentifierValueError):
        PersistentIdentifier(scheme=PersistentIdentifierScheme.DOI, value="")


@pytest.mark.unit
def test_persistent_identifier_with_whitespace_only_value_raises_invalid_value_error() -> None:
    with pytest.raises(InvalidPersistentIdentifierValueError):
        PersistentIdentifier(scheme=PersistentIdentifierScheme.DOI, value="   ")


@pytest.mark.unit
def test_persistent_identifier_with_too_long_value_raises_invalid_value_error() -> None:
    over_limit = "x" * (PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH + 1)
    with pytest.raises(InvalidPersistentIdentifierValueError):
        PersistentIdentifier(
            scheme=PersistentIdentifierScheme.DOI,
            value=over_limit,
        )


@pytest.mark.unit
def test_persistent_identifier_at_max_length_succeeds() -> None:
    at_limit = "x" * PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH
    pid = PersistentIdentifier(
        scheme=PersistentIdentifierScheme.DOI,
        value=at_limit,
    )
    assert pid.value == at_limit


@pytest.mark.unit
def test_persistent_identifier_trims_surrounding_whitespace() -> None:
    pid = PersistentIdentifier(
        scheme=PersistentIdentifierScheme.DOI,
        value="   10.5281/zenodo.1234567   ",
    )
    assert pid.value == "10.5281/zenodo.1234567"


@pytest.mark.unit
def test_persistent_identifier_is_frozen() -> None:
    pid = PersistentIdentifier(
        scheme=PersistentIdentifierScheme.DOI,
        value="10.5281/zenodo.1234567",
    )
    with pytest.raises(FrozenInstanceError):
        pid.value = "10.5281/zenodo.7654321"  # type: ignore[misc]


@pytest.mark.unit
def test_persistent_identifier_is_hashable_in_frozenset() -> None:
    a = PersistentIdentifier(
        scheme=PersistentIdentifierScheme.DOI,
        value="10.5281/zenodo.1234567",
    )
    b = PersistentIdentifier(
        scheme=PersistentIdentifierScheme.HANDLE,
        value="20.500.12613/12345",
    )
    members = frozenset({a, b})
    assert a in members
    assert b in members


@pytest.mark.unit
def test_persistent_identifier_equality_is_value_based() -> None:
    a = PersistentIdentifier(
        scheme=PersistentIdentifierScheme.DOI,
        value="10.5281/zenodo.1234567",
    )
    b = PersistentIdentifier(
        scheme=PersistentIdentifierScheme.DOI,
        value="  10.5281/zenodo.1234567  ",
    )
    assert a == b


@pytest.mark.unit
def test_persistent_identifier_with_different_scheme_is_not_equal() -> None:
    a = PersistentIdentifier(
        scheme=PersistentIdentifierScheme.DOI,
        value="10.5281/zenodo.1234567",
    )
    b = PersistentIdentifier(
        scheme=PersistentIdentifierScheme.HANDLE,
        value="10.5281/zenodo.1234567",
    )
    assert a != b
