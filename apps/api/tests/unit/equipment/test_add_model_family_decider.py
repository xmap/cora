"""Pure-decider tests for the `add_model_family` slice.

Targeted mutation of `Model.declared_families`, not a lifecycle
transition. Status is preserved (`Defined` stays `Defined`,
`Versioned` stays `Versioned`); only `Deprecated` is rejected via
`ModelCannotVersionError` (Model's general "cannot mutate from
Deprecated" gate, reused by the add/remove family slices).

Strict-not-idempotent: re-adding a present family raises
`ModelFamilyAlreadyPresentError`, mirroring the `add_asset_family`
precedent.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    Model,
    ModelCannotVersionError,
    ModelFamilyAdded,
    ModelFamilyAlreadyPresentError,
    ModelName,
    ModelNotFoundError,
    ModelStatus,
    PartNumber,
)
from cora.equipment.features import add_model_family
from cora.equipment.features.add_model_family import AddModelFamily

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)


def _model(
    *,
    status: ModelStatus = ModelStatus.DEFINED,
    declared_families: frozenset[UUID] | None = None,
    version: str | None = None,
) -> Model:
    return Model(
        id=uuid4(),
        name=ModelName("Aerotech ANT130-L"),
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number=PartNumber("ANT130-L"),
        declared_families=declared_families
        if declared_families is not None
        else frozenset({uuid4()}),
        status=status,
        version=version,
    )


@pytest.mark.unit
def test_decide_emits_model_family_added_from_defined_state() -> None:
    state = _model(status=ModelStatus.DEFINED)
    new_family = uuid4()
    events = add_model_family.decide(
        state=state,
        command=AddModelFamily(model_id=state.id, family_id=new_family),
        now=_NOW,
    )
    assert events == [ModelFamilyAdded(model_id=state.id, family_id=new_family, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_emits_model_family_added_from_versioned_state() -> None:
    """Status preserved across targeted mutation; Versioned is a valid source."""
    state = _model(status=ModelStatus.VERSIONED, version="v2")
    new_family = uuid4()
    events = add_model_family.decide(
        state=state,
        command=AddModelFamily(model_id=state.id, family_id=new_family),
        now=_NOW,
    )
    assert events == [ModelFamilyAdded(model_id=state.id, family_id=new_family, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_cannot_version_when_deprecated() -> None:
    """Deprecated catalog entries are frozen; add_model_family rejects."""
    state = _model(status=ModelStatus.DEPRECATED, version="v1")
    with pytest.raises(ModelCannotVersionError) as exc_info:
        add_model_family.decide(
            state=state,
            command=AddModelFamily(model_id=state.id, family_id=uuid4()),
            now=_NOW,
        )
    assert exc_info.value.model_id == state.id
    assert exc_info.value.current_status is ModelStatus.DEPRECATED


@pytest.mark.unit
def test_decide_raises_model_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(ModelNotFoundError) as exc_info:
        add_model_family.decide(
            state=None,
            command=AddModelFamily(model_id=target_id, family_id=uuid4()),
            now=_NOW,
        )
    assert exc_info.value.model_id == target_id


@pytest.mark.unit
def test_decide_raises_already_present_on_duplicate_family() -> None:
    """Strict-not-idempotent: re-adding a present family raises rather
    than no-op so operators can detect 'wait, this is already declared'
    instead of silently succeeding."""
    existing = uuid4()
    state = _model(declared_families=frozenset({existing}))
    with pytest.raises(ModelFamilyAlreadyPresentError) as exc_info:
        add_model_family.decide(
            state=state,
            command=AddModelFamily(model_id=state.id, family_id=existing),
            now=_NOW,
        )
    assert exc_info.value.model_id == state.id
    assert exc_info.value.family_id == existing


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _model()
    family = uuid4()
    command = AddModelFamily(model_id=state.id, family_id=family)
    first = add_model_family.decide(state=state, command=command, now=_NOW)
    second = add_model_family.decide(state=state, command=command, now=_NOW)
    assert first == second
