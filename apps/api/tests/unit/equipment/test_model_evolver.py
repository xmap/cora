"""FSM evolution tests for the Model aggregate."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    ModelDefined,
    ModelDeprecated,
    ModelFamilyAdded,
    ModelFamilyRemoved,
    ModelStatus,
    ModelVersioned,
    evolve,
    fold,
)


def _now() -> datetime:
    return datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def _defined(family_id: object | None = None) -> ModelDefined:
    family = family_id if isinstance(family_id, type(uuid4())) else uuid4()
    return ModelDefined(
        model_id=uuid4(),
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_families=frozenset({family}),
        occurred_at=_now(),
    )


@pytest.mark.unit
def test_model_defined_sets_genesis_state() -> None:
    event = _defined()
    state = evolve(None, event)
    assert state.id == event.model_id
    assert state.name.value == "Aerotech ANT130-L"
    assert state.status is ModelStatus.DEFINED
    assert state.version is None
    assert state.declared_families == event.declared_families


@pytest.mark.unit
def test_model_defined_with_initial_version_tag_carries_through() -> None:
    event = ModelDefined(
        model_id=uuid4(),
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_families=frozenset({uuid4()}),
        occurred_at=_now(),
        version_tag="rev-A",
    )
    state = evolve(None, event)
    assert state.version == "rev-A"


@pytest.mark.unit
def test_model_versioned_transitions_from_defined() -> None:
    defined = _defined()
    new_family = uuid4()
    versioned = ModelVersioned(
        model_id=defined.model_id,
        name="Aerotech ANT130-L (rev B)",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech Newport JV")),
        part_number="ANT130-L-B",
        declared_families=frozenset({new_family}),
        version_tag="rev-B",
        occurred_at=_now(),
    )
    state = fold([defined, versioned])
    assert state is not None
    assert state.status is ModelStatus.VERSIONED
    assert state.version == "rev-B"
    # Wholesale replacement: name, manufacturer, part_number, families all swapped.
    assert state.name.value == "Aerotech ANT130-L (rev B)"
    assert state.manufacturer.name.value == "Aerotech Newport JV"
    assert state.part_number.value == "ANT130-L-B"
    assert state.declared_families == frozenset({new_family})


@pytest.mark.unit
def test_model_versioned_transitions_from_versioned() -> None:
    defined = _defined()
    v1 = ModelVersioned(
        model_id=defined.model_id,
        name="A",
        manufacturer=Manufacturer(name=ManufacturerName("M")),
        part_number="P",
        declared_families=frozenset({uuid4()}),
        version_tag="rev-B",
        occurred_at=_now(),
    )
    v2 = ModelVersioned(
        model_id=defined.model_id,
        name="A",
        manufacturer=Manufacturer(name=ManufacturerName("M")),
        part_number="P",
        declared_families=frozenset({uuid4()}),
        version_tag="rev-C",
        occurred_at=_now(),
    )
    state = fold([defined, v1, v2])
    assert state is not None
    assert state.status is ModelStatus.VERSIONED
    assert state.version == "rev-C"


@pytest.mark.unit
def test_model_deprecated_transitions_from_defined() -> None:
    defined = _defined()
    deprecated = ModelDeprecated(
        model_id=defined.model_id,
        reason="EOL",
        occurred_at=_now(),
    )
    state = fold([defined, deprecated])
    assert state is not None
    assert state.status is ModelStatus.DEPRECATED
    # declared_families preserved across deprecation (audit trail).
    assert state.declared_families == defined.declared_families


@pytest.mark.unit
def test_model_deprecated_transitions_from_versioned() -> None:
    defined = _defined()
    versioned = ModelVersioned(
        model_id=defined.model_id,
        name="A",
        manufacturer=Manufacturer(name=ManufacturerName("M")),
        part_number="P",
        declared_families=frozenset({uuid4()}),
        version_tag="rev-B",
        occurred_at=_now(),
    )
    deprecated = ModelDeprecated(model_id=defined.model_id, reason="r", occurred_at=_now())
    state = fold([defined, versioned, deprecated])
    assert state is not None
    assert state.status is ModelStatus.DEPRECATED
    assert state.version == "rev-B"


@pytest.mark.unit
def test_model_family_added_extends_declared_families() -> None:
    defined = _defined()
    extra = uuid4()
    added = ModelFamilyAdded(model_id=defined.model_id, family_id=extra, occurred_at=_now())
    state = fold([defined, added])
    assert state is not None
    assert state.status is ModelStatus.DEFINED  # status preserved on targeted mutation
    assert state.declared_families == defined.declared_families | {extra}


@pytest.mark.unit
def test_model_family_removed_shrinks_declared_families() -> None:
    family_a = uuid4()
    family_b = uuid4()
    defined = ModelDefined(
        model_id=uuid4(),
        name="N",
        manufacturer=Manufacturer(name=ManufacturerName("M")),
        part_number="P",
        declared_families=frozenset({family_a, family_b}),
        occurred_at=_now(),
    )
    removed = ModelFamilyRemoved(
        model_id=defined.model_id,
        family_id=family_a,
        occurred_at=_now(),
    )
    state = fold([defined, removed])
    assert state is not None
    assert state.declared_families == frozenset({family_b})


@pytest.mark.unit
def test_versioning_empty_stream_raises() -> None:
    versioned = ModelVersioned(
        model_id=uuid4(),
        name="N",
        manufacturer=Manufacturer(name=ManufacturerName("M")),
        part_number="P",
        declared_families=frozenset({uuid4()}),
        version_tag="rev-B",
        occurred_at=_now(),
    )
    with pytest.raises(ValueError):
        evolve(None, versioned)


@pytest.mark.unit
def test_fold_empty_stream_returns_none() -> None:
    assert fold([]) is None
