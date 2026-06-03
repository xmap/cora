"""Unit tests for the AssetOwner VO and its bounded-text components."""

import pytest

from cora.equipment.aggregates.asset import (
    ASSET_OWNER_IDENTIFIER_TYPE_MAX_LENGTH,
    AssetOwner,
    AssetOwnerContact,
    AssetOwnerIdentifier,
    AssetOwnerIdentifierType,
    AssetOwnerName,
    InvalidAssetOwnerContactError,
    InvalidAssetOwnerIdentifierError,
    InvalidAssetOwnerIdentifierPairingError,
    InvalidAssetOwnerIdentifierTypeError,
    InvalidAssetOwnerNameError,
)


def _name(value: str = "HZB") -> AssetOwnerName:
    return AssetOwnerName(value)


@pytest.mark.unit
def test_asset_owner_minimum_name_only_succeeds() -> None:
    owner = AssetOwner(name=_name("HZB"))
    assert owner.name.value == "HZB"
    assert owner.contact is None
    assert owner.identifier is None
    assert owner.identifier_type is None


@pytest.mark.unit
def test_asset_owner_with_contact_only_succeeds() -> None:
    owner = AssetOwner(
        name=_name("HZB"),
        contact=AssetOwnerContact("instrument-data@helmholtz-berlin.de"),
    )
    assert owner.contact is not None
    assert owner.contact.value == "instrument-data@helmholtz-berlin.de"


@pytest.mark.unit
def test_asset_owner_with_identifier_pair_succeeds() -> None:
    owner = AssetOwner(
        name=_name("HZB"),
        identifier=AssetOwnerIdentifier("https://ror.org/02aj13c28"),
        identifier_type=AssetOwnerIdentifierType("ROR"),
    )
    assert owner.identifier is not None
    assert owner.identifier_type is not None
    assert owner.identifier.value == "https://ror.org/02aj13c28"
    assert owner.identifier_type.value == "ROR"


@pytest.mark.unit
def test_asset_owner_fully_populated_succeeds() -> None:
    owner = AssetOwner(
        name=_name("HZB"),
        contact=AssetOwnerContact("ops@helmholtz-berlin.de"),
        identifier=AssetOwnerIdentifier("02aj13c28"),
        identifier_type=AssetOwnerIdentifierType("ROR"),
    )
    assert owner.name.value == "HZB"
    assert owner.contact is not None and owner.contact.value == "ops@helmholtz-berlin.de"
    assert owner.identifier is not None and owner.identifier.value == "02aj13c28"
    assert owner.identifier_type is not None and owner.identifier_type.value == "ROR"


@pytest.mark.unit
def test_asset_owner_is_hashable_in_frozenset() -> None:
    a = AssetOwner(name=_name("HZB"))
    b = AssetOwner(name=_name("APS"))
    members = frozenset({a, b})
    assert a in members
    assert b in members


@pytest.mark.unit
def test_asset_owner_value_equality_on_all_four_fields_holds() -> None:
    a = AssetOwner(
        name=_name("HZB"),
        contact=AssetOwnerContact("ops@hzb.de"),
        identifier=AssetOwnerIdentifier("https://ror.org/02aj13c28"),
        identifier_type=AssetOwnerIdentifierType("ROR"),
    )
    b = AssetOwner(
        name=_name("HZB"),
        contact=AssetOwnerContact("ops@hzb.de"),
        identifier=AssetOwnerIdentifier("https://ror.org/02aj13c28"),
        identifier_type=AssetOwnerIdentifierType("ROR"),
    )
    assert a == b
    different_contact = AssetOwner(
        name=_name("HZB"),
        contact=AssetOwnerContact("other@hzb.de"),
        identifier=AssetOwnerIdentifier("https://ror.org/02aj13c28"),
        identifier_type=AssetOwnerIdentifierType("ROR"),
    )
    assert a != different_contact


@pytest.mark.unit
def test_asset_owner_name_empty_raises() -> None:
    with pytest.raises(InvalidAssetOwnerNameError):
        AssetOwnerName("")


@pytest.mark.unit
def test_asset_owner_name_whitespace_only_raises() -> None:
    with pytest.raises(InvalidAssetOwnerNameError):
        AssetOwnerName("   ")


@pytest.mark.unit
def test_asset_owner_contact_whitespace_only_raises() -> None:
    with pytest.raises(InvalidAssetOwnerContactError):
        AssetOwnerContact("   ")


@pytest.mark.unit
def test_asset_owner_identifier_whitespace_only_raises() -> None:
    with pytest.raises(InvalidAssetOwnerIdentifierError):
        AssetOwnerIdentifier("   ")


@pytest.mark.unit
def test_asset_owner_identifier_without_type_raises_pairing_error() -> None:
    with pytest.raises(InvalidAssetOwnerIdentifierPairingError):
        AssetOwner(
            name=_name("HZB"),
            identifier=AssetOwnerIdentifier("02aj13c28"),
            identifier_type=None,
        )


@pytest.mark.unit
def test_asset_owner_type_without_identifier_raises_pairing_error() -> None:
    with pytest.raises(InvalidAssetOwnerIdentifierPairingError):
        AssetOwner(
            name=_name("HZB"),
            identifier=None,
            identifier_type=AssetOwnerIdentifierType("ROR"),
        )


@pytest.mark.unit
def test_asset_owner_identifier_type_64_char_limit_enforced() -> None:
    over_limit = "X" * (ASSET_OWNER_IDENTIFIER_TYPE_MAX_LENGTH + 1)
    with pytest.raises(InvalidAssetOwnerIdentifierTypeError):
        AssetOwnerIdentifierType(over_limit)
    at_limit = "X" * ASSET_OWNER_IDENTIFIER_TYPE_MAX_LENGTH
    assert AssetOwnerIdentifierType(at_limit).value == at_limit


@pytest.mark.unit
def test_asset_owner_accepts_ror_as_identifier_type() -> None:
    """Lock 4: ROR is the recommended scheme but the type is free text."""
    owner = AssetOwner(
        name=_name(),
        identifier=AssetOwnerIdentifier("02aj13c28"),
        identifier_type=AssetOwnerIdentifierType("ROR"),
    )
    assert owner.identifier_type is not None
    assert owner.identifier_type.value == "ROR"


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        "GRID",
        "ISNI",
        "RAID",
        "IGSN",
        "facility-internal-2024",
        "ANL-CORP-ID",
    ],
)
def test_asset_owner_accepts_arbitrary_string_as_identifier_type(value: str) -> None:
    """F6.3 confirmation: PIDINST 5.3.1 is deliberately free text; any
    organization-identifier authority is accepted."""
    type_vo = AssetOwnerIdentifierType(value)
    assert type_vo.value == value


@pytest.mark.unit
@pytest.mark.parametrize("value", ["ror", "Ror", "ROR"])
def test_asset_owner_preserves_identifier_type_casing(value: str) -> None:
    """Aggregate does NOT case-normalize; PIDINST output preserves the
    operator-recorded casing."""
    type_vo = AssetOwnerIdentifierType(value)
    assert type_vo.value == value


@pytest.mark.unit
def test_asset_owner_name_trims_surrounding_whitespace() -> None:
    name = AssetOwnerName("   HZB   ")
    assert name.value == "HZB"


@pytest.mark.unit
def test_asset_owner_identifier_accepts_bare_code_and_full_url() -> None:
    bare = AssetOwnerIdentifier("02aj13c28")
    full = AssetOwnerIdentifier("https://ror.org/02aj13c28")
    assert bare.value == "02aj13c28"
    assert full.value == "https://ror.org/02aj13c28"
