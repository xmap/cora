"""Unit tests for the serializer's persistent_id -> PidinstIdentifier swap.

Per section 13.1 of [[project-asset-persistent-id-write-design]]: when
`AssetPidinstView.persistent_id` is set, `_build_identifier` emits a
`PidinstIdentifier` carrying the matching `PidinstIdentifierType`
(DOI or Handle); when absent, the URN fallback (slice C contract)
still holds. The persistent_id value is passed through to the wire
identifier verbatim (no normalization, no resolver-URL prepend).
"""

from dataclasses import replace

import pytest

from cora.equipment._pidinst import PidinstIdentifierType, to_pidinst_record
from cora.shared.identifier import (
    PersistentIdentifier,
    PersistentIdentifierScheme,
)
from tests.unit.equipment._helpers import build_view_with_model

pytestmark = [pytest.mark.unit, pytest.mark.timeout(60, method="thread")]

_DOI_VALUE = "10.5281/zenodo.1234567"
_HANDLE_VALUE = "20.500.12613/12345"


def test_serializer_with_view_persistent_id_doi_emits_pidinst_identifier_type_doi() -> None:
    view = replace(
        build_view_with_model(),
        persistent_id=PersistentIdentifier(
            scheme=PersistentIdentifierScheme.DOI,
            value=_DOI_VALUE,
        ),
    )
    record = to_pidinst_record(view)
    assert record.identifier.scheme is PidinstIdentifierType.DOI
    assert record.identifier.value == _DOI_VALUE


def test_serializer_with_view_persistent_id_handle_emits_pidinst_identifier_type_handle() -> None:
    view = replace(
        build_view_with_model(),
        persistent_id=PersistentIdentifier(
            scheme=PersistentIdentifierScheme.HANDLE,
            value=_HANDLE_VALUE,
        ),
    )
    record = to_pidinst_record(view)
    assert record.identifier.scheme is PidinstIdentifierType.HANDLE
    assert record.identifier.value == _HANDLE_VALUE


def test_serializer_without_view_persistent_id_falls_back_to_urn() -> None:
    view = build_view_with_model()
    assert view.persistent_id is None
    record = to_pidinst_record(view)
    assert record.identifier.scheme is PidinstIdentifierType.URN
    assert record.identifier.value == f"urn:uuid:{view.asset_id}"


def test_serializer_persistent_id_value_is_unchanged_at_wire() -> None:
    view = replace(
        build_view_with_model(),
        persistent_id=PersistentIdentifier(
            scheme=PersistentIdentifierScheme.DOI,
            value=_DOI_VALUE,
        ),
    )
    record = to_pidinst_record(view)
    assert record.identifier.value == _DOI_VALUE
    assert not record.identifier.value.startswith("https://")
    assert not record.identifier.value.startswith("http://")
    assert not record.identifier.value.startswith("doi:")
