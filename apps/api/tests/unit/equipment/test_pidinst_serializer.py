"""Unit tests for `to_pidinst_record` per-property mapping and failure modes.

29 positive cases per section 7.2 of the design memo (one per
cardinality + enum branch across the 14 PIDINST properties), and 6
negative cases per section 7.3 (one per pre-construction exception
plus the schema-order ordering case).
"""

from dataclasses import replace
from uuid import UUID

import pytest

from cora.equipment._pidinst import (
    AssetNameMissingError,
    AssetPidinstView,
    DateType,
    LandingPageMissingError,
    ManufacturerStateNotAvailableError,
    OwnerStateNotAvailableError,
    PidinstIdentifierType,
    SchemaVersion,
    to_pidinst_record,
)
from cora.equipment.aggregates.asset import (
    AssetLifecycle,
)
from cora.equipment.aggregates.model import ManufacturerIdentifierType
from cora.shared.identifier import (
    AlternateIdentifier,
    AlternateIdentifierKind,
)
from tests.unit.equipment._helpers import (
    build_minimal_view,
    build_view_2bm_rotary_stage,
    build_view_with_model,
)

pytestmark = [pytest.mark.unit, pytest.mark.timeout(60, method="thread")]

_ASSET_ID = UUID("01900000-0000-7000-8000-00000000b001")


def _view_without_model() -> AssetPidinstView:
    return replace(build_minimal_view(), model=None)


def _view_with_empty_owners() -> AssetPidinstView:
    return replace(build_minimal_view(), owners=())


def _view_with_empty_name() -> AssetPidinstView:
    return replace(build_minimal_view(), asset_name="   ")


def _view_with_empty_landing_page() -> AssetPidinstView:
    return replace(build_minimal_view(), landing_page_url="")


def test_to_pidinst_record_minimal_view_emits_required_properties() -> None:
    record = to_pidinst_record(build_minimal_view())
    assert record.identifier.scheme is PidinstIdentifierType.URN
    assert record.schema_version is SchemaVersion.V1_0
    assert record.landing_page
    assert record.name
    assert record.owners
    assert record.manufacturers


def test_to_pidinst_record_schema_version_is_constant_one_zero() -> None:
    record = to_pidinst_record(build_minimal_view())
    assert record.schema_version is SchemaVersion.V1_0
    assert record.schema_version.value == "1.0"


def test_to_pidinst_record_landing_page_passes_through() -> None:
    view = build_minimal_view()
    record = to_pidinst_record(view)
    assert record.landing_page == view.landing_page_url


def test_to_pidinst_record_name_passes_through() -> None:
    view = build_minimal_view()
    record = to_pidinst_record(view)
    assert record.name == view.asset_name


def test_to_pidinst_record_identifier_is_urn_uuid_pre_slice_e() -> None:
    view = build_minimal_view()
    record = to_pidinst_record(view)
    assert record.identifier.value == f"urn:uuid:{view.asset_id}"
    assert record.identifier.scheme is PidinstIdentifierType.URN


def test_to_pidinst_record_with_model_emits_model_property() -> None:
    record = to_pidinst_record(build_view_with_model())
    assert record.model is not None
    assert record.model.name == "ANT130-L"


def test_to_pidinst_record_with_model_uses_part_number_as_identifier() -> None:
    record = to_pidinst_record(build_view_with_model())
    assert record.model is not None
    assert record.model.identifier == "ANT130-L-RM"
    assert record.model.identifier_type == "PartNumber"


def test_to_pidinst_record_with_model_emits_manufacturer_property() -> None:
    record = to_pidinst_record(build_view_with_model())
    assert len(record.manufacturers) == 1
    assert record.manufacturers[0].name == "Aerotech"


def test_to_pidinst_record_with_ror_manufacturer_emits_type_ror() -> None:
    record = to_pidinst_record(build_view_with_model())
    assert record.manufacturers[0].identifier_type is ManufacturerIdentifierType.ROR


def test_to_pidinst_record_with_grid_manufacturer_emits_type_grid() -> None:
    base = build_view_with_model()
    assert base.model is not None
    view = replace(
        base,
        model=replace(
            base.model,
            manufacturer_identifier="grid.475244.4",
            manufacturer_identifier_type=ManufacturerIdentifierType.GRID,
        ),
    )
    record = to_pidinst_record(view)
    assert record.manufacturers[0].identifier_type is ManufacturerIdentifierType.GRID


def test_to_pidinst_record_with_isni_manufacturer_emits_type_isni() -> None:
    base = build_view_with_model()
    assert base.model is not None
    view = replace(
        base,
        model=replace(
            base.model,
            manufacturer_identifier="0000000123456789",
            manufacturer_identifier_type=ManufacturerIdentifierType.ISNI,
        ),
    )
    record = to_pidinst_record(view)
    assert record.manufacturers[0].identifier_type is ManufacturerIdentifierType.ISNI


def test_to_pidinst_record_with_manufacturer_without_identifier_emits_null_subfields() -> None:
    record = to_pidinst_record(build_minimal_view())
    assert record.manufacturers[0].identifier is None
    assert record.manufacturers[0].identifier_type is None


def test_to_pidinst_record_description_always_none() -> None:
    record = to_pidinst_record(build_view_with_model())
    assert record.description is None


def test_to_pidinst_record_with_family_emits_instrument_type_per_family() -> None:
    record = to_pidinst_record(build_view_with_model())
    assert len(record.instrument_types) == 1
    assert record.instrument_types[0].name == "RotaryStage"
    assert record.instrument_types[0].identifier_type == "URN"


def test_to_pidinst_record_with_two_families_preserves_view_order() -> None:
    record = to_pidinst_record(build_view_2bm_rotary_stage())
    assert [it.name for it in record.instrument_types] == [
        "PrecisionStage",
        "RotaryStage",
    ]


def test_to_pidinst_record_with_unsorted_family_tuple_preserves_view_order() -> None:
    """The serializer honors the view's pre-sort contract; it does NOT re-sort."""
    base = build_view_with_model()
    fid_a = UUID("01900000-0000-7000-8000-00000000c001")
    fid_b = UUID("01900000-0000-7000-8000-00000000c002")
    view = replace(
        base,
        family_names=("Zeta", "Alpha"),
        family_ids=(fid_a, fid_b),
    )
    record = to_pidinst_record(view)
    assert [it.name for it in record.instrument_types] == ["Zeta", "Alpha"]


def test_to_pidinst_record_with_no_families_emits_empty_tuple() -> None:
    record = to_pidinst_record(build_minimal_view())
    assert record.instrument_types == ()


def test_to_pidinst_record_measured_variable_always_empty() -> None:
    record = to_pidinst_record(build_view_2bm_rotary_stage())
    assert record.measured_variables == ()


def test_to_pidinst_record_with_commissioned_at_emits_date_commissioned() -> None:
    record = to_pidinst_record(build_view_with_model())
    assert len(record.dates) == 1
    assert record.dates[0].date_type is DateType.COMMISSIONED
    assert record.dates[0].value == "2024-05-15"


def test_to_pidinst_record_with_decommissioned_at_emits_date_decommissioned() -> None:
    record = to_pidinst_record(build_view_2bm_rotary_stage())
    kinds = [d.date_type for d in record.dates]
    assert DateType.DECOMMISSIONED in kinds


def test_to_pidinst_record_with_no_lifecycle_dates_emits_empty_tuple() -> None:
    record = to_pidinst_record(build_minimal_view())
    assert record.dates == ()


def test_to_pidinst_record_with_decommissioned_lifecycle_still_serializes() -> None:
    """DECOMMISSIONED lifecycle is not a failure; PIDINST records survive their referent."""
    record = to_pidinst_record(build_view_2bm_rotary_stage())
    assert record.name == "2-BM Sample Rotary Stage"
    assert record.dates  # carries the decommissioned date


def test_to_pidinst_record_related_identifier_always_empty_in_slice_c() -> None:
    record = to_pidinst_record(build_view_2bm_rotary_stage())
    assert record.related_identifiers == ()


def test_to_pidinst_record_with_alternate_identifier_serial_number_preserves_kind() -> None:
    base = build_view_with_model()
    view = replace(
        base,
        alternate_identifiers=frozenset(
            {AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="SN-1")}
        ),
    )
    record = to_pidinst_record(view)
    assert len(record.alternate_identifiers) == 1
    assert record.alternate_identifiers[0].kind is AlternateIdentifierKind.SERIAL_NUMBER


def test_to_pidinst_record_with_alternate_identifier_inventory_number_preserves_kind() -> None:
    base = build_view_with_model()
    view = replace(
        base,
        alternate_identifiers=frozenset(
            {AlternateIdentifier(kind=AlternateIdentifierKind.INVENTORY_NUMBER, value="INV-9")}
        ),
    )
    record = to_pidinst_record(view)
    assert record.alternate_identifiers[0].kind is AlternateIdentifierKind.INVENTORY_NUMBER


def test_to_pidinst_record_with_alternate_identifier_other_preserves_kind() -> None:
    base = build_view_with_model()
    view = replace(
        base,
        alternate_identifiers=frozenset(
            {AlternateIdentifier(kind=AlternateIdentifierKind.OTHER, value="LEG-1")}
        ),
    )
    record = to_pidinst_record(view)
    assert record.alternate_identifiers[0].kind is AlternateIdentifierKind.OTHER


def test_to_pidinst_record_with_three_alternate_identifiers_sorted_by_kind_then_value() -> None:
    record = to_pidinst_record(build_view_2bm_rotary_stage())
    pairs = [(ai.kind.value, ai.value) for ai in record.alternate_identifiers]
    assert pairs == sorted(pairs)


def test_to_pidinst_record_with_no_alternate_identifiers_emits_empty_tuple() -> None:
    record = to_pidinst_record(build_minimal_view())
    assert record.alternate_identifiers == ()


def test_to_pidinst_record_measurement_technique_always_empty() -> None:
    record = to_pidinst_record(build_view_2bm_rotary_stage())
    assert record.measurement_techniques == ()


def test_to_pidinst_record_without_model_raises_manufacturer_state_not_available_error() -> None:
    with pytest.raises(ManufacturerStateNotAvailableError):
        to_pidinst_record(_view_without_model())


def test_to_pidinst_record_without_model_carries_asset_id_on_exception() -> None:
    with pytest.raises(ManufacturerStateNotAvailableError) as exc_info:
        to_pidinst_record(_view_without_model())
    assert exc_info.value.asset_id == _ASSET_ID


def test_to_pidinst_record_with_empty_name_raises_asset_name_missing_error() -> None:
    with pytest.raises(AssetNameMissingError) as exc_info:
        to_pidinst_record(_view_with_empty_name())
    assert exc_info.value.asset_id == _ASSET_ID


def test_to_pidinst_record_with_empty_landing_page_raises_landing_page_missing_error() -> None:
    with pytest.raises(LandingPageMissingError) as exc_info:
        to_pidinst_record(_view_with_empty_landing_page())
    assert exc_info.value.asset_id == _ASSET_ID


def test_to_pidinst_record_pre_owner_slice_raises_owner_state_not_available_error() -> None:
    """Removed when slice D ships; replaced with positive owner tests."""
    with pytest.raises(OwnerStateNotAvailableError) as exc_info:
        to_pidinst_record(_view_with_empty_owners())
    assert exc_info.value.asset_id == _ASSET_ID


def test_to_pidinst_record_raises_in_schema_order_when_multiple_mandatory_missing() -> None:
    """Section 6.2 + L9: PIDINST schema order is property 3 LandingPage,
    then 4 Name, then 5 Owner, then 6 Manufacturer. The first missing
    mandatory property in property-number order wins; when all four are
    missing, `LandingPageMissingError` wins.
    """
    view = AssetPidinstView(
        asset_id=_ASSET_ID,
        asset_name="",
        landing_page_url="",
        lifecycle=AssetLifecycle.COMMISSIONED,
        alternate_identifiers=frozenset(),
        parent_id=None,
        family_names=(),
        family_ids=(),
        model=None,
        commissioned_at=None,
        decommissioned_at=None,
        publisher="ANL",
        publication_year=None,
        owners=(),
    )
    with pytest.raises(LandingPageMissingError):
        to_pidinst_record(view)


def test_to_pidinst_record_raises_landing_page_before_name_when_both_missing() -> None:
    """LandingPage (property 3) is checked before Name (property 4)."""
    view = replace(build_minimal_view(), landing_page_url="", asset_name="")
    with pytest.raises(LandingPageMissingError):
        to_pidinst_record(view)


def test_to_pidinst_record_raises_name_before_owner_when_both_missing() -> None:
    """Name (property 4) is checked before Owner (property 5)."""
    view = replace(build_minimal_view(), asset_name="", owners=())
    with pytest.raises(AssetNameMissingError):
        to_pidinst_record(view)


def test_to_pidinst_record_raises_owner_before_manufacturer_when_both_missing() -> None:
    """Owner (property 5) is checked before Manufacturer (property 6)."""
    view = replace(build_minimal_view(), owners=(), model=None)
    with pytest.raises(OwnerStateNotAvailableError):
        to_pidinst_record(view)
