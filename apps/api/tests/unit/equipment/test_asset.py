"""AssetName VO + AssetLevel + AssetLifecycle enum tests."""

from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetLevel,
    AssetLifecycle,
    AssetModelMismatchError,
    AssetName,
    InvalidAssetNameError,
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


# ---------- AssetLevel enum ----------


@pytest.mark.unit
def test_asset_level_has_all_six_isa88_levels() -> None:
    """Pin the full level vocabulary from the BC map (ISA-88-derived,
    single-word convention). Adding / removing values should be a
    deliberate change visible here."""
    assert {lvl.value for lvl in AssetLevel} == {
        "Enterprise",
        "Site",
        "Area",
        "Unit",
        "Assembly",
        "Device",
    }


@pytest.mark.unit
def test_asset_level_values_are_pascal_case_strings() -> None:
    assert AssetLevel.ENTERPRISE == "Enterprise"
    assert AssetLevel.SITE == "Site"
    assert AssetLevel.AREA == "Area"
    assert AssetLevel.UNIT == "Unit"
    assert AssetLevel.ASSEMBLY == "Assembly"
    assert AssetLevel.DEVICE == "Device"


@pytest.mark.unit
def test_asset_level_is_str_enum_for_natural_serialization() -> None:
    """StrEnum so JSON serialization and string comparison Just Work
    without `.value` access. AssetLevel is carried in event payloads
    as the StrEnum's string value, so this matters for the wire
    format."""
    assert isinstance(AssetLevel.ENTERPRISE, str)
    assert AssetLevel.ENTERPRISE == "Enterprise"
    assert f"{AssetLevel.SITE}" == "Site"


@pytest.mark.unit
def test_asset_level_can_be_constructed_from_string_value() -> None:
    """The evolver reconstructs the enum from event payload strings via
    `AssetLevel(payload['level'])`. Pin that the round-trip works
    for every value."""
    for level in AssetLevel:
        assert AssetLevel(level.value) == level


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
        level=AssetLevel.UNIT,
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
        level=AssetLevel.UNIT,
        parent_id=uuid4(),
        model_id=model_id,
    )
    assert asset.model_id == model_id


# ---------- AssetModelMismatchError error class ----------


@pytest.mark.unit
def test_asset_model_mismatch_carries_all_four_fields() -> None:
    """Lock E: the error carries (asset_id, model_id, declared_families,
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
        declared_families=declared,
        asset_family_ids=on_asset,
    )
    assert error.asset_id == asset_id
    assert error.model_id == model_id
    assert error.declared_families == declared
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
        declared_families=declared,
        asset_family_ids=on_asset,
    )
    message = str(error)
    assert str(asset_id) in message
    assert str(model_id) in message
    # Both UUIDs of declared_families must appear; same for asset_family_ids.
    assert str(fam_a) in message
    assert str(fam_b) in message


@pytest.mark.unit
def test_asset_model_mismatch_is_exception() -> None:
    """Subclass of Exception so it can be raised / caught in the
    cannot_transition_cls tuple in routes.py."""
    error = AssetModelMismatchError(
        asset_id=uuid4(),
        model_id=uuid4(),
        declared_families=frozenset(),
        asset_family_ids=frozenset(),
    )
    assert isinstance(error, Exception)
