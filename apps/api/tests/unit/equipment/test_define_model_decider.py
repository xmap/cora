"""Pure-decider tests for the `define_model` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.model import (
    InvalidDeclaredFamiliesError,
    InvalidModelNameError,
    InvalidModelVersionTagError,
    InvalidPartNumberError,
    Manufacturer,
    ManufacturerIdentifier,
    ManufacturerIdentifierType,
    ManufacturerName,
    Model,
    ModelAlreadyExistsError,
    ModelName,
    ModelStatus,
    PartNumber,
)
from cora.equipment.features.define_model import DefineModel, decide

_NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def _minimal_command() -> DefineModel:
    return DefineModel(
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_families=frozenset({uuid4()}),
    )


@pytest.mark.unit
def test_decide_emits_model_defined_for_minimal_command() -> None:
    cmd = _minimal_command()
    new_id = uuid4()
    events = decide(None, cmd, now=_NOW, new_id=new_id)
    assert len(events) == 1
    event = events[0]
    assert event.model_id == new_id
    assert event.name == "Aerotech ANT130-L"
    assert event.manufacturer == cmd.manufacturer
    assert event.part_number == "ANT130-L"
    assert event.declared_families == cmd.declared_families
    assert event.occurred_at == _NOW
    assert event.version_tag is None


@pytest.mark.unit
def test_decide_carries_version_tag_when_supplied() -> None:
    cmd = DefineModel(
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_families=frozenset({uuid4()}),
        version_tag="rev-A",
    )
    events = decide(None, cmd, now=_NOW, new_id=uuid4())
    assert events[0].version_tag == "rev-A"


@pytest.mark.unit
def test_decide_carries_full_manufacturer_triple() -> None:
    cmd = DefineModel(
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(
            name=ManufacturerName("Aerotech"),
            identifier=ManufacturerIdentifier("https://ror.org/05gvnxz63"),
            identifier_type=ManufacturerIdentifierType.ROR,
        ),
        part_number="ANT130-L",
        declared_families=frozenset({uuid4()}),
    )
    events = decide(None, cmd, now=_NOW, new_id=uuid4())
    assert events[0].manufacturer.identifier is not None
    assert events[0].manufacturer.identifier.value == "https://ror.org/05gvnxz63"
    assert events[0].manufacturer.identifier_type is ManufacturerIdentifierType.ROR


@pytest.mark.unit
def test_decide_rejects_when_stream_already_has_state() -> None:
    existing = Model(
        id=uuid4(),
        name=ModelName("Existing"),
        manufacturer=Manufacturer(name=ManufacturerName("M")),
        part_number=PartNumber("P"),
        declared_families=frozenset({uuid4()}),
        status=ModelStatus.DEFINED,
    )
    with pytest.raises(ModelAlreadyExistsError):
        decide(existing, _minimal_command(), now=_NOW, new_id=uuid4())


@pytest.mark.unit
def test_decide_rejects_empty_declared_families() -> None:
    cmd = DefineModel(
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_families=frozenset(),
    )
    with pytest.raises(InvalidDeclaredFamiliesError):
        decide(None, cmd, now=_NOW, new_id=uuid4())


@pytest.mark.unit
def test_decide_rejects_invalid_name() -> None:
    cmd = DefineModel(
        name="   ",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_families=frozenset({uuid4()}),
    )
    with pytest.raises(InvalidModelNameError):
        decide(None, cmd, now=_NOW, new_id=uuid4())


@pytest.mark.unit
def test_decide_rejects_invalid_part_number() -> None:
    cmd = DefineModel(
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="",
        declared_families=frozenset({uuid4()}),
    )
    with pytest.raises(InvalidPartNumberError):
        decide(None, cmd, now=_NOW, new_id=uuid4())


@pytest.mark.unit
def test_decide_rejects_empty_initial_version_tag() -> None:
    cmd = DefineModel(
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_families=frozenset({uuid4()}),
        version_tag="   ",
    )
    with pytest.raises(InvalidModelVersionTagError):
        decide(None, cmd, now=_NOW, new_id=uuid4())
