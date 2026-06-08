"""Unit tests for `to_fixture_pidinst_record` per Section 15.1 of the design memo.

Mirrors `test_pidinst_serializer*.py` style: per-property example tests
for the happy paths (URN fallback, DOI / Handle swap, owners passthrough,
manufacturers union, HasComponent relations) and one negative case per
`FixturePidinstSerializationError` subclass plus the kernel
`PidinstRecordInvariantError` that propagates unwrapped from
`PidinstRecord.__post_init__`.
"""

from dataclasses import replace
from uuid import UUID

import pytest

from cora.equipment._pidinst_serializer import to_fixture_pidinst_record
from cora.equipment._pidinst_types import (
    FixtureComponentRef,
    FixturePidinstView,
    Manufacturer,
    PidinstIdentifierType,
    PidinstRelationType,
    SchemaVersion,
)
from cora.equipment.aggregates.asset import (
    AssetOwner,
    AssetOwnerContact,
    AssetOwnerIdentifier,
    AssetOwnerIdentifierType,
    AssetOwnerName,
)
from cora.equipment.aggregates.model import ManufacturerIdentifierType
from cora.equipment.errors import (
    FixtureLandingPageMissingError,
    FixtureManufacturerStateNotAvailableError,
    FixtureNameMissingError,
    FixtureOwnerStateNotAvailableError,
    PidinstRecordInvariantError,
)
from cora.shared.identifier import (
    PersistentIdentifier,
    PersistentIdentifierScheme,
)

pytestmark = [pytest.mark.unit, pytest.mark.timeout(60, method="thread")]

_FIXTURE_ID = UUID("01900000-0000-7000-8000-00000000f001")
_ASSET_ID_A = UUID("01900000-0000-7000-8000-00000000a001")
_ASSET_ID_B = UUID("01900000-0000-7000-8000-00000000a002")

_LANDING_PAGE = f"https://cora.example/fixtures/{_FIXTURE_ID}"
_PUBLISHER = "Argonne National Laboratory"

_DOI_VALUE = "10.5281/zenodo.7654321"
_HANDLE_VALUE = "20.500.12613/98765"

_OWNER_APS = AssetOwner(
    name=AssetOwnerName("Advanced Photon Source"),
    contact=AssetOwnerContact("aps-ops@anl.gov"),
    identifier=AssetOwnerIdentifier("https://ror.org/05gvnxz63"),
    identifier_type=AssetOwnerIdentifierType("ROR"),
)

_OWNER_HZB = AssetOwner(
    name=AssetOwnerName("Helmholtz-Zentrum Berlin"),
    contact=AssetOwnerContact("instrument-data@helmholtz-berlin.de"),
    identifier=AssetOwnerIdentifier("https://ror.org/02aj13c28"),
    identifier_type=AssetOwnerIdentifierType("ROR"),
)

_MANUFACTURER_AEROTECH = Manufacturer(
    name="Aerotech",
    identifier="https://ror.org/04bw7nh07",
    identifier_type=ManufacturerIdentifierType.ROR,
)

_MANUFACTURER_FLIR = Manufacturer(
    name="FLIR",
    identifier="https://ror.org/03kqv4r80",
    identifier_type=ManufacturerIdentifierType.ROR,
)


def _build_minimal_fixture_view() -> FixturePidinstView:
    """Smallest Fixture view that still serializes.

    One owner, one manufacturer, zero components, no persistent_id.
    Mirrors `build_minimal_view` from the Asset-side `_helpers.py`.
    """
    return FixturePidinstView(
        fixture_id=_FIXTURE_ID,
        name="Sample Fixture",
        persistent_id=None,
        owners=(_OWNER_APS,),
        manufacturers=(_MANUFACTURER_AEROTECH,),
        components=(),
        publication_year=2026,
    )


def test_to_fixture_pidinst_record_minimal_view_emits_required_properties() -> None:
    record = to_fixture_pidinst_record(
        _build_minimal_fixture_view(),
        landing_page_url=_LANDING_PAGE,
        publisher=_PUBLISHER,
    )
    assert record.identifier.scheme is PidinstIdentifierType.URN
    assert record.schema_version is SchemaVersion.V1_0
    assert record.landing_page == _LANDING_PAGE
    assert record.name == "Sample Fixture"
    assert record.owners
    assert record.manufacturers
    assert record.publisher == _PUBLISHER
    assert record.publication_year == 2026


def test_to_fixture_pidinst_record_without_persistent_id_emits_urn_fallback() -> None:
    record = to_fixture_pidinst_record(
        _build_minimal_fixture_view(),
        landing_page_url=_LANDING_PAGE,
        publisher=_PUBLISHER,
    )
    assert record.identifier.scheme is PidinstIdentifierType.URN
    assert record.identifier.value == f"urn:uuid:{_FIXTURE_ID}"


def test_to_fixture_pidinst_record_with_minted_persistent_id_doi_emits_doi_identifier() -> None:
    view = replace(
        _build_minimal_fixture_view(),
        persistent_id=PersistentIdentifier(
            scheme=PersistentIdentifierScheme.DOI,
            value=_DOI_VALUE,
        ),
    )
    record = to_fixture_pidinst_record(view, landing_page_url=_LANDING_PAGE, publisher=_PUBLISHER)
    assert record.identifier.scheme is PidinstIdentifierType.DOI
    assert record.identifier.value == _DOI_VALUE


def test_to_fixture_pidinst_record_with_minted_persistent_id_handle_emits_handle_identifier() -> (
    None
):
    view = replace(
        _build_minimal_fixture_view(),
        persistent_id=PersistentIdentifier(
            scheme=PersistentIdentifierScheme.HANDLE,
            value=_HANDLE_VALUE,
        ),
    )
    record = to_fixture_pidinst_record(view, landing_page_url=_LANDING_PAGE, publisher=_PUBLISHER)
    assert record.identifier.scheme is PidinstIdentifierType.HANDLE
    assert record.identifier.value == _HANDLE_VALUE


def test_to_fixture_pidinst_record_with_owners_emits_pidinst_owners_property() -> None:
    view = replace(
        _build_minimal_fixture_view(),
        owners=(_OWNER_APS, _OWNER_HZB),
    )
    record = to_fixture_pidinst_record(view, landing_page_url=_LANDING_PAGE, publisher=_PUBLISHER)
    names = [owner.name for owner in record.owners]
    assert names == ["Advanced Photon Source", "Helmholtz-Zentrum Berlin"]
    assert record.owners[0].identifier == "https://ror.org/05gvnxz63"
    assert record.owners[0].identifier_type == "ROR"
    assert record.owners[0].contact == "aps-ops@anl.gov"


def test_to_fixture_pidinst_record_with_manufacturers_emits_pidinst_manufacturers_property() -> (
    None
):
    view = replace(
        _build_minimal_fixture_view(),
        manufacturers=(_MANUFACTURER_AEROTECH, _MANUFACTURER_FLIR),
    )
    record = to_fixture_pidinst_record(view, landing_page_url=_LANDING_PAGE, publisher=_PUBLISHER)
    assert [m.name for m in record.manufacturers] == ["Aerotech", "FLIR"]
    assert record.manufacturers[0].identifier == "https://ror.org/04bw7nh07"
    assert record.manufacturers[0].identifier_type is ManufacturerIdentifierType.ROR


def test_to_fixture_pidinst_record_with_components_emits_has_component_relations() -> None:
    components = (
        FixtureComponentRef(
            component_id=_ASSET_ID_A,
            scheme=PersistentIdentifierScheme.DOI,
            value="10.5281/zenodo.1111",
            name="Rotary Stage A",
        ),
        FixtureComponentRef(
            component_id=_ASSET_ID_B,
            scheme=PersistentIdentifierScheme.HANDLE,
            value="20.500.12613/22222",
            name="Camera B",
        ),
    )
    view = replace(_build_minimal_fixture_view(), components=components)
    record = to_fixture_pidinst_record(view, landing_page_url=_LANDING_PAGE, publisher=_PUBLISHER)
    assert len(record.related_identifiers) == 2
    assert all(
        ri.relation_type is PidinstRelationType.HAS_COMPONENT for ri in record.related_identifiers
    )
    values = [ri.value for ri in record.related_identifiers]
    assert values == ["10.5281/zenodo.1111", "20.500.12613/22222"]
    types = [ri.identifier_type for ri in record.related_identifiers]
    assert types == [
        PersistentIdentifierScheme.DOI.value,
        PersistentIdentifierScheme.HANDLE.value,
    ]


def test_to_fixture_pidinst_record_with_unminted_components_skips_them_from_relations() -> None:
    components = (
        FixtureComponentRef(
            component_id=_ASSET_ID_A,
            scheme=PersistentIdentifierScheme.DOI,
            value="10.5281/zenodo.1111",
            name="Rotary Stage A",
        ),
        FixtureComponentRef(
            component_id=_ASSET_ID_B,
            scheme=None,
            value=None,
            name="Unminted Camera",
        ),
    )
    view = replace(_build_minimal_fixture_view(), components=components)
    record = to_fixture_pidinst_record(view, landing_page_url=_LANDING_PAGE, publisher=_PUBLISHER)
    assert len(record.related_identifiers) == 1
    assert record.related_identifiers[0].value == "10.5281/zenodo.1111"


def test_to_fixture_pidinst_record_with_empty_landing_page_raises_landing_page_missing_error() -> (
    None
):
    with pytest.raises(FixtureLandingPageMissingError) as exc_info:
        to_fixture_pidinst_record(
            _build_minimal_fixture_view(),
            landing_page_url="",
            publisher=_PUBLISHER,
        )
    assert exc_info.value.fixture_id == _FIXTURE_ID


def test_to_fixture_pidinst_record_with_empty_name_raises_name_missing_error() -> None:
    view = replace(_build_minimal_fixture_view(), name="   ")
    with pytest.raises(FixtureNameMissingError) as exc_info:
        to_fixture_pidinst_record(view, landing_page_url=_LANDING_PAGE, publisher=_PUBLISHER)
    assert exc_info.value.fixture_id == _FIXTURE_ID


def test_to_fixture_pidinst_record_with_empty_owners_raises_owner_state_not_available_error() -> (
    None
):
    view = replace(_build_minimal_fixture_view(), owners=())
    with pytest.raises(FixtureOwnerStateNotAvailableError) as exc_info:
        to_fixture_pidinst_record(view, landing_page_url=_LANDING_PAGE, publisher=_PUBLISHER)
    assert exc_info.value.fixture_id == _FIXTURE_ID


def test_to_record_with_empty_manufacturers_raises_manufacturer_state_not_available_error() -> None:
    view = replace(_build_minimal_fixture_view(), manufacturers=())
    with pytest.raises(FixtureManufacturerStateNotAvailableError) as exc_info:
        to_fixture_pidinst_record(view, landing_page_url=_LANDING_PAGE, publisher=_PUBLISHER)
    assert exc_info.value.fixture_id == _FIXTURE_ID


def test_to_record_with_whitespace_landing_page_raises_landing_page_missing_error() -> None:
    with pytest.raises(FixtureLandingPageMissingError):
        to_fixture_pidinst_record(
            _build_minimal_fixture_view(),
            landing_page_url="   ",
            publisher=_PUBLISHER,
        )


def test_to_record_with_owners_pairing_violation_raises_pidinst_record_invariant_error() -> None:
    """Kernel `PidinstRecordInvariantError` propagates unwrapped from the intermediate Owner VO.

    Owner's `__post_init__` enforces the identifier / identifier_type
    pairing invariant and raises `PidinstRecordInvariantError`. The
    Fixture serializer surfaces it unwrapped (mirrors the Asset side;
    no `FixturePidinstRecordInvariantError` sibling ships).
    """
    bad_asset_owner = AssetOwner.__new__(AssetOwner)
    object.__setattr__(bad_asset_owner, "name", AssetOwnerName("Bypassed"))
    object.__setattr__(bad_asset_owner, "contact", AssetOwnerContact("bypass@example.org"))
    object.__setattr__(
        bad_asset_owner, "identifier", AssetOwnerIdentifier("https://ror.org/000000000")
    )
    object.__setattr__(bad_asset_owner, "identifier_type", None)
    view = replace(_build_minimal_fixture_view(), owners=(bad_asset_owner,))
    with pytest.raises(PidinstRecordInvariantError):
        to_fixture_pidinst_record(view, landing_page_url=_LANDING_PAGE, publisher=_PUBLISHER)
