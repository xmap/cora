"""Value objects + Model dataclass + ModelStatus enum tests."""

from uuid import uuid4

import pytest

from cora.equipment.aggregates.model import (
    MANUFACTURER_IDENTIFIER_MAX_LENGTH,
    MANUFACTURER_NAME_MAX_LENGTH,
    MODEL_NAME_MAX_LENGTH,
    MODEL_PART_NUMBER_MAX_LENGTH,
    MODEL_VERSION_TAG_MAX_LENGTH,
    InvalidManufacturerIdentifierError,
    InvalidManufacturerIdentifierPairingError,
    InvalidManufacturerNameError,
    InvalidModelDeprecationReasonError,
    InvalidModelNameError,
    InvalidModelVersionTagError,
    InvalidPartNumberError,
    Manufacturer,
    ManufacturerIdentifier,
    ManufacturerIdentifierType,
    ManufacturerName,
    Model,
    ModelDeprecationReason,
    ModelName,
    ModelStatus,
    ModelVersionTag,
    PartNumber,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


@pytest.mark.unit
def test_model_name_accepts_normal_string() -> None:
    name = ModelName("Aerotech ANT130-L")
    assert name.value == "Aerotech ANT130-L"


@pytest.mark.unit
def test_model_name_trims_whitespace() -> None:
    name = ModelName("  PCO Edge 5.5  ")
    assert name.value == "PCO Edge 5.5"


@pytest.mark.unit
def test_model_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidModelNameError):
        ModelName("")


@pytest.mark.unit
def test_model_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidModelNameError):
        ModelName("   \t\n   ")


@pytest.mark.unit
def test_model_name_rejects_too_long() -> None:
    with pytest.raises(InvalidModelNameError):
        ModelName("X" * (MODEL_NAME_MAX_LENGTH + 1))


@pytest.mark.unit
def test_part_number_accepts_case_sensitive_sku() -> None:
    upper = PartNumber("RV120CCHL")
    lower = PartNumber("rv120cchl")
    assert upper.value == "RV120CCHL"
    assert lower.value == "rv120cchl"
    assert upper.value != lower.value


@pytest.mark.unit
def test_part_number_trims_whitespace() -> None:
    assert PartNumber(" ANT130-L ").value == "ANT130-L"


@pytest.mark.unit
def test_part_number_rejects_empty() -> None:
    with pytest.raises(InvalidPartNumberError):
        PartNumber("")


@pytest.mark.unit
def test_part_number_rejects_too_long() -> None:
    with pytest.raises(InvalidPartNumberError):
        PartNumber("X" * (MODEL_PART_NUMBER_MAX_LENGTH + 1))


@pytest.mark.unit
def test_manufacturer_name_rejects_empty() -> None:
    with pytest.raises(InvalidManufacturerNameError):
        ManufacturerName("")


@pytest.mark.unit
def test_manufacturer_name_rejects_too_long() -> None:
    with pytest.raises(InvalidManufacturerNameError):
        ManufacturerName("X" * (MANUFACTURER_NAME_MAX_LENGTH + 1))


@pytest.mark.unit
def test_manufacturer_identifier_trims_and_accepts_ror() -> None:
    ident = ManufacturerIdentifier("  https://ror.org/05gvnxz63  ")
    assert ident.value == "https://ror.org/05gvnxz63"


@pytest.mark.unit
def test_manufacturer_identifier_rejects_empty() -> None:
    with pytest.raises(InvalidManufacturerIdentifierError):
        ManufacturerIdentifier("   ")


@pytest.mark.unit
def test_manufacturer_identifier_rejects_too_long() -> None:
    with pytest.raises(InvalidManufacturerIdentifierError):
        ManufacturerIdentifier("X" * (MANUFACTURER_IDENTIFIER_MAX_LENGTH + 1))


@pytest.mark.unit
def test_manufacturer_accepts_name_only() -> None:
    mfr = Manufacturer(name=ManufacturerName("Aerotech"))
    assert mfr.name.value == "Aerotech"
    assert mfr.identifier is None
    assert mfr.identifier_type is None


@pytest.mark.unit
def test_manufacturer_accepts_full_triple() -> None:
    mfr = Manufacturer(
        name=ManufacturerName("Aerotech"),
        identifier=ManufacturerIdentifier("https://ror.org/05gvnxz63"),
        identifier_type=ManufacturerIdentifierType.ROR,
    )
    assert mfr.identifier is not None
    assert mfr.identifier.value == "https://ror.org/05gvnxz63"
    assert mfr.identifier_type is ManufacturerIdentifierType.ROR


@pytest.mark.unit
def test_manufacturer_rejects_identifier_without_type() -> None:
    with pytest.raises(InvalidManufacturerIdentifierPairingError):
        Manufacturer(
            name=ManufacturerName("Aerotech"),
            identifier=ManufacturerIdentifier("https://ror.org/05gvnxz63"),
            identifier_type=None,
        )


@pytest.mark.unit
def test_manufacturer_rejects_type_without_identifier() -> None:
    with pytest.raises(InvalidManufacturerIdentifierPairingError):
        Manufacturer(
            name=ManufacturerName("Aerotech"),
            identifier=None,
            identifier_type=ManufacturerIdentifierType.GRID,
        )


@pytest.mark.unit
def test_model_version_tag_rejects_empty_and_too_long() -> None:
    with pytest.raises(InvalidModelVersionTagError):
        ModelVersionTag("")
    with pytest.raises(InvalidModelVersionTagError):
        ModelVersionTag("X" * (MODEL_VERSION_TAG_MAX_LENGTH + 1))


@pytest.mark.unit
def test_model_deprecation_reason_rejects_empty_and_too_long() -> None:
    with pytest.raises(InvalidModelDeprecationReasonError):
        ModelDeprecationReason("")
    with pytest.raises(InvalidModelDeprecationReasonError):
        ModelDeprecationReason("X" * (REASON_MAX_LENGTH + 1))


@pytest.mark.unit
def test_model_status_enum_values() -> None:
    assert ModelStatus.DEFINED.value == "Defined"
    assert ModelStatus.VERSIONED.value == "Versioned"
    assert ModelStatus.DEPRECATED.value == "Deprecated"


@pytest.mark.unit
def test_model_aggregate_constructs_with_required_fields() -> None:
    family_a = uuid4()
    model = Model(
        id=uuid4(),
        name=ModelName("Aerotech ANT130-L"),
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number=PartNumber("ANT130-L"),
        declared_family_ids=frozenset({family_a}),
    )
    assert model.status is ModelStatus.DEFINED
    assert model.version is None
    assert model.declared_family_ids == frozenset({family_a})
