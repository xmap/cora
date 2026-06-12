"""Closed-enum invariants for `PersistentIdentifierScheme` (Lock 11 / L4).

The scheme enum is the v1 PIDINST Property 1 vocabulary subset CORA
accepts on the assign path. Two members only (DOI + HANDLE), and the
member values must match `PidinstIdentifierType.DOI` and
`PidinstIdentifierType.HANDLE` byte-for-byte so the serializer swap
from URN to DOI / Handle does not need a translation map.
"""

from enum import StrEnum

import pytest

from cora.equipment._pidinst import PidinstIdentifierType
from cora.shared.identifier import PersistentIdentifierScheme

pytestmark = [pytest.mark.unit, pytest.mark.timeout(60, method="thread")]


def test_persistent_identifier_scheme_is_strenum_subclass() -> None:
    assert issubclass(PersistentIdentifierScheme, StrEnum)


def test_persistent_identifier_scheme_has_exactly_two_members() -> None:
    assert len(PersistentIdentifierScheme) == 2


def test_persistent_identifier_scheme_member_set_is_doi_and_handle() -> None:
    assert {member.name for member in PersistentIdentifierScheme} == {"DOI", "HANDLE"}


def test_persistent_identifier_scheme_doi_value_matches_pidinst_doi_byte_for_byte() -> None:
    assert PersistentIdentifierScheme.DOI.value == PidinstIdentifierType.DOI.value


def test_persistent_identifier_scheme_handle_value_matches_pidinst_handle_byte_for_byte() -> None:
    assert PersistentIdentifierScheme.HANDLE.value == PidinstIdentifierType.HANDLE.value


def test_persistent_identifier_scheme_doi_value_is_literal_doi_string() -> None:
    assert PersistentIdentifierScheme.DOI.value == "DOI"


def test_persistent_identifier_scheme_handle_value_is_literal_handle_string() -> None:
    assert PersistentIdentifierScheme.HANDLE.value == "Handle"


def test_persistent_identifier_scheme_does_not_mirror_pidinst_urn_member() -> None:
    assert "URN" not in {member.name for member in PersistentIdentifierScheme}
    assert PidinstIdentifierType.URN.value not in {
        member.value for member in PersistentIdentifierScheme
    }


def test_persistent_identifier_scheme_does_not_mirror_pidinst_url_member() -> None:
    assert "URL" not in {member.name for member in PersistentIdentifierScheme}
    assert PidinstIdentifierType.URL.value not in {
        member.value for member in PersistentIdentifierScheme
    }


def test_persistent_identifier_scheme_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        PersistentIdentifierScheme("ARK")


def test_persistent_identifier_scheme_rejects_lowercase_doi_value() -> None:
    with pytest.raises(ValueError):
        PersistentIdentifierScheme("doi")


def test_persistent_identifier_scheme_rejects_uppercase_handle_value() -> None:
    with pytest.raises(ValueError):
        PersistentIdentifierScheme("HANDLE")


def test_persistent_identifier_scheme_round_trips_through_value_lookup() -> None:
    assert PersistentIdentifierScheme(PersistentIdentifierScheme.DOI.value) is (
        PersistentIdentifierScheme.DOI
    )
    assert PersistentIdentifierScheme(PersistentIdentifierScheme.HANDLE.value) is (
        PersistentIdentifierScheme.HANDLE
    )
