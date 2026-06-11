"""AssetName VO + AssetTier + AssetLifecycle enum tests."""

from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetAlternateIdentifierAlreadyPresentError,
    AssetAlternateIdentifierNotPresentError,
    AssetLifecycle,
    AssetModelMismatchError,
    AssetName,
    AssetTier,
    InvalidAssetNameError,
)
from cora.shared.identifier import (
    AlternateIdentifier,
    AlternateIdentifierKind,
    InvalidAlternateIdentifierValueError,
)

# ---------- AssetName VO ----------


@pytest.mark.unit
def test_asset_name_accepts_normal_string() -> None:
    name = AssetName("APS-2BM-A")
    assert name.value == "APS-2BM-A"


@pytest.mark.unit
def test_asset_name_trims_whitespace() -> None:
    name = AssetName("  Eiger-2X-9M  ")
    assert name.value == "Eiger-2X-9M"


@pytest.mark.unit
def test_asset_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidAssetNameError):
        AssetName("")


@pytest.mark.unit
def test_asset_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidAssetNameError):
        AssetName("   \t\n   ")


@pytest.mark.unit
def test_asset_name_rejects_too_long() -> None:
    with pytest.raises(InvalidAssetNameError):
        AssetName("a" * 201)


@pytest.mark.unit
def test_asset_name_accepts_max_length() -> None:
    name = AssetName("a" * 200)
    assert len(name.value) == 200


@pytest.mark.unit
def test_asset_name_is_frozen() -> None:
    name = AssetName("APS-2BM")
    with pytest.raises(AttributeError):
        name.value = "Other"  # type: ignore[misc]


# ---------- AssetTier enum ----------


@pytest.mark.unit
def test_asset_tier_has_three_isa88_tiers() -> None:
    """Pin the closed AssetTier value set (ISA-88-derived equipment
    tiers, single-word convention). Facility-envelope scope (site /
    area / institution) is owned by the Facility aggregate, not an
    Asset tier; adding / removing values should be a deliberate change
    visible here."""
    assert {t.value for t in AssetTier} == {"Unit", "Component", "Device"}


@pytest.mark.unit
def test_asset_tier_values_are_pascal_case_strings() -> None:
    assert AssetTier.UNIT == "Unit"
    assert AssetTier.COMPONENT == "Component"
    assert AssetTier.DEVICE == "Device"


@pytest.mark.unit
def test_asset_tier_is_str_enum_for_natural_serialization() -> None:
    """StrEnum so JSON serialization and string comparison Just Work
    without `.value` access. AssetTier is carried in event payloads
    as the StrEnum's string value, so this matters for the wire
    format."""
    assert isinstance(AssetTier.UNIT, str)
    assert AssetTier.UNIT == "Unit"
    assert f"{AssetTier.DEVICE}" == "Device"


@pytest.mark.unit
def test_asset_tier_can_be_constructed_from_string_value() -> None:
    """The evolver reconstructs the enum from event payload strings via
    `AssetTier(payload['tier'])`. Pin that the round-trip works for
    every value."""
    for tier in AssetTier:
        assert AssetTier(tier.value) == tier


# ---------- AssetLifecycle enum ----------


@pytest.mark.unit
def test_asset_lifecycle_has_all_four_lifecycle_values() -> None:
    """Pin the full lifecycle vocabulary from the BC map. Adding /
    removing values should be a deliberate change visible here."""
    assert {lc.value for lc in AssetLifecycle} == {
        "Commissioned",
        "Active",
        "Maintenance",
        "Decommissioned",
    }


@pytest.mark.unit
def test_asset_lifecycle_values_are_pascal_case_strings() -> None:
    assert AssetLifecycle.COMMISSIONED == "Commissioned"
    assert AssetLifecycle.ACTIVE == "Active"
    assert AssetLifecycle.MAINTENANCE == "Maintenance"
    assert AssetLifecycle.DECOMMISSIONED == "Decommissioned"


@pytest.mark.unit
def test_asset_lifecycle_is_str_enum() -> None:
    assert isinstance(AssetLifecycle.COMMISSIONED, str)
    assert AssetLifecycle.COMMISSIONED == "Commissioned"


# ---------- Asset.model_id ----------


@pytest.mark.unit
def test_asset_model_id_defaults_to_none() -> None:
    """Additive-state pattern: legacy AssetRegistered streams without
    model_id fold cleanly to None. Pin so adding a different default
    is a deliberate change."""
    asset = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
    )
    assert asset.model_id is None


@pytest.mark.unit
def test_asset_model_id_accepts_uuid() -> None:
    """Construction with a Model binding lands the UUID on state."""
    model_id = uuid4()
    asset = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        model_id=model_id,
    )
    assert asset.model_id == model_id


# ---------- AssetModelMismatchError error class ----------


@pytest.mark.unit
def test_asset_model_mismatch_carries_all_four_fields() -> None:
    """Lock E: the error carries (asset_id, model_id, declared_family_ids,
    asset_family_ids) for diagnostics. Pin so any constructor signature
    change is deliberate."""
    asset_id = uuid4()
    model_id = uuid4()
    fam_a = uuid4()
    fam_b = uuid4()
    declared = frozenset({fam_a, fam_b})
    on_asset = frozenset({fam_a})
    error = AssetModelMismatchError(
        asset_id=asset_id,
        model_id=model_id,
        declared_family_ids=declared,
        asset_family_ids=on_asset,
    )
    assert error.asset_id == asset_id
    assert error.model_id == model_id
    assert error.declared_family_ids == declared
    assert error.asset_family_ids == on_asset


@pytest.mark.unit
def test_asset_model_mismatch_message_lists_both_sets_verbatim() -> None:
    """Lock E: message lists both sets verbatim so operators see exactly
    which Families are missing on the Asset."""
    asset_id = uuid4()
    model_id = uuid4()
    fam_a = uuid4()
    fam_b = uuid4()
    declared = frozenset({fam_a, fam_b})
    on_asset = frozenset({fam_a})
    error = AssetModelMismatchError(
        asset_id=asset_id,
        model_id=model_id,
        declared_family_ids=declared,
        asset_family_ids=on_asset,
    )
    message = str(error)
    assert str(asset_id) in message
    assert str(model_id) in message
    # Both UUIDs of declared_family_ids must appear; same for asset_family_ids.
    assert str(fam_a) in message
    assert str(fam_b) in message


@pytest.mark.unit
def test_asset_model_mismatch_is_exception() -> None:
    """Subclass of Exception so it can be raised / caught in the
    cannot_transition_cls tuple in routes.py."""
    error = AssetModelMismatchError(
        asset_id=uuid4(),
        model_id=uuid4(),
        declared_family_ids=frozenset(),
        asset_family_ids=frozenset(),
    )
    assert isinstance(error, Exception)


# ---------- AlternateIdentifierKind enum ----------


@pytest.mark.unit
def test_alternate_identifier_kind_has_pidinst_v1_vocabulary() -> None:
    """Pin the closed vocabulary from PIDINST v1.0 spec page 8 Table 1
    (Property 13 alternateIdentifierType). Adding / removing values
    should be a deliberate change visible here. See Lock B in the
    design memo."""
    assert {kind.value for kind in AlternateIdentifierKind} == {
        "SerialNumber",
        "InventoryNumber",
        "Other",
    }


@pytest.mark.unit
def test_alternate_identifier_kind_values_are_pascalcase_strings() -> None:
    assert AlternateIdentifierKind.SERIAL_NUMBER == "SerialNumber"
    assert AlternateIdentifierKind.INVENTORY_NUMBER == "InventoryNumber"
    assert AlternateIdentifierKind.OTHER == "Other"


@pytest.mark.unit
def test_alternate_identifier_kind_is_str_enum() -> None:
    """StrEnum so JSON serialization works naturally without `.value`
    access: the wire format carries the StrEnum value."""
    assert isinstance(AlternateIdentifierKind.SERIAL_NUMBER, str)
    assert AlternateIdentifierKind.SERIAL_NUMBER == "SerialNumber"


@pytest.mark.unit
def test_alternate_identifier_kind_round_trips_from_string() -> None:
    """The events from_stored path reconstructs the enum from
    payload strings via `AlternateIdentifierKind(payload['kind'])`."""
    for kind in AlternateIdentifierKind:
        assert AlternateIdentifierKind(kind.value) == kind


# ---------- AlternateIdentifier VO ----------


@pytest.mark.unit
def test_alternate_identifier_constructs_with_valid_inputs() -> None:
    identifier = AlternateIdentifier(
        kind=AlternateIdentifierKind.SERIAL_NUMBER,
        value="12345-ABC",
    )
    assert identifier.kind is AlternateIdentifierKind.SERIAL_NUMBER
    assert identifier.value == "12345-ABC"


@pytest.mark.unit
def test_alternate_identifier_trims_value() -> None:
    identifier = AlternateIdentifier(
        kind=AlternateIdentifierKind.INVENTORY_NUMBER,
        value="  APS-2BM-CAM-001  ",
    )
    assert identifier.value == "APS-2BM-CAM-001"


@pytest.mark.unit
def test_alternate_identifier_rejects_empty_value() -> None:
    with pytest.raises(InvalidAlternateIdentifierValueError):
        AlternateIdentifier(kind=AlternateIdentifierKind.OTHER, value="")


@pytest.mark.unit
def test_alternate_identifier_rejects_whitespace_only_value() -> None:
    with pytest.raises(InvalidAlternateIdentifierValueError):
        AlternateIdentifier(kind=AlternateIdentifierKind.OTHER, value="   \t\n   ")


@pytest.mark.unit
def test_alternate_identifier_rejects_too_long_value() -> None:
    """Bound mirrors ManufacturerIdentifier (200 chars)."""
    with pytest.raises(InvalidAlternateIdentifierValueError):
        AlternateIdentifier(
            kind=AlternateIdentifierKind.SERIAL_NUMBER,
            value="x" * 201,
        )


@pytest.mark.unit
def test_alternate_identifier_accepts_max_length_value() -> None:
    identifier = AlternateIdentifier(
        kind=AlternateIdentifierKind.SERIAL_NUMBER,
        value="x" * 200,
    )
    assert len(identifier.value) == 200


@pytest.mark.unit
def test_alternate_identifier_is_frozen_and_hashable() -> None:
    """Pinned: AlternateIdentifier is a frozen dataclass (hashable) so
    instances can live in a frozenset on Asset state."""
    from dataclasses import FrozenInstanceError

    identifier = AlternateIdentifier(
        kind=AlternateIdentifierKind.SERIAL_NUMBER,
        value="abc",
    )
    s = {identifier}
    assert identifier in s
    with pytest.raises(FrozenInstanceError):
        identifier.value = "xyz"  # type: ignore[misc]


@pytest.mark.unit
def test_alternate_identifier_equality_is_value_based() -> None:
    """Two AlternateIdentifiers with the same (kind, value) tuple are
    equal regardless of incoming whitespace."""
    a = AlternateIdentifier(kind=AlternateIdentifierKind.OTHER, value="abc")
    b = AlternateIdentifier(kind=AlternateIdentifierKind.OTHER, value="  abc  ")
    assert a == b


@pytest.mark.unit
def test_alternate_identifier_different_kind_is_not_equal() -> None:
    a = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="123")
    b = AlternateIdentifier(kind=AlternateIdentifierKind.INVENTORY_NUMBER, value="123")
    assert a != b


# ---------- Asset.alternate_identifiers field ----------


@pytest.mark.unit
def test_asset_alternate_identifiers_defaults_to_empty_frozenset() -> None:
    """Additive-state pattern: legacy AssetRegistered streams without
    alternate_identifiers fold cleanly to empty frozenset."""
    asset = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
    )
    assert asset.alternate_identifiers == frozenset()


@pytest.mark.unit
def test_asset_alternate_identifiers_accepts_non_empty_set() -> None:
    ident1 = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="12345")
    ident2 = AlternateIdentifier(kind=AlternateIdentifierKind.INVENTORY_NUMBER, value="APS-001")
    asset = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        alternate_identifiers=frozenset({ident1, ident2}),
    )
    assert asset.alternate_identifiers == frozenset({ident1, ident2})


# ---------- AssetAlternateIdentifierAlreadyPresentError ----------


@pytest.mark.unit
def test_asset_alternate_identifier_already_present_carries_asset_id_and_identifier() -> None:
    asset_id = uuid4()
    identifier = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="12345-ABC")
    error = AssetAlternateIdentifierAlreadyPresentError(asset_id=asset_id, identifier=identifier)
    assert error.asset_id == asset_id
    assert error.identifier == identifier


@pytest.mark.unit
def test_asset_alternate_identifier_already_present_message_quotes_kind_and_value() -> None:
    asset_id = uuid4()
    identifier = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="12345-ABC")
    error = AssetAlternateIdentifierAlreadyPresentError(asset_id=asset_id, identifier=identifier)
    message = str(error)
    assert str(asset_id) in message
    assert "SerialNumber" in message
    assert "12345-ABC" in message


@pytest.mark.unit
def test_asset_alternate_identifier_already_present_is_exception() -> None:
    """Subclass of Exception so it can be raised / caught in the
    cannot_transition_cls tuple in routes.py (strict-not-idempotent
    family)."""
    error = AssetAlternateIdentifierAlreadyPresentError(
        asset_id=uuid4(),
        identifier=AlternateIdentifier(kind=AlternateIdentifierKind.OTHER, value="x"),
    )
    assert isinstance(error, Exception)


# ---------- AssetAlternateIdentifierNotPresentError ----------


@pytest.mark.unit
def test_asset_alternate_identifier_not_present_carries_asset_id_and_identifier() -> None:
    asset_id = uuid4()
    identifier = AlternateIdentifier(
        kind=AlternateIdentifierKind.INVENTORY_NUMBER, value="APS-2BM-001"
    )
    error = AssetAlternateIdentifierNotPresentError(asset_id=asset_id, identifier=identifier)
    assert error.asset_id == asset_id
    assert error.identifier == identifier


@pytest.mark.unit
def test_asset_alternate_identifier_not_present_message_quotes_kind_and_value() -> None:
    asset_id = uuid4()
    identifier = AlternateIdentifier(
        kind=AlternateIdentifierKind.INVENTORY_NUMBER, value="APS-2BM-001"
    )
    error = AssetAlternateIdentifierNotPresentError(asset_id=asset_id, identifier=identifier)
    message = str(error)
    assert str(asset_id) in message
    assert "InventoryNumber" in message
    assert "APS-2BM-001" in message


@pytest.mark.unit
def test_asset_alternate_identifier_not_present_is_exception() -> None:
    error = AssetAlternateIdentifierNotPresentError(
        asset_id=uuid4(),
        identifier=AlternateIdentifier(kind=AlternateIdentifierKind.OTHER, value="x"),
    )
    assert isinstance(error, Exception)


# ---------- InvalidAlternateIdentifierValueError ----------


@pytest.mark.unit
def test_invalid_alternate_identifier_value_error_quotes_raw_value() -> None:
    """Error message echoes the original (untrimmed) value so the
    caller sees exactly what they sent."""
    with pytest.raises(InvalidAlternateIdentifierValueError) as excinfo:
        AlternateIdentifier(kind=AlternateIdentifierKind.OTHER, value="   ")
    assert excinfo.value.value == "   "
    assert "   " in str(excinfo.value)
