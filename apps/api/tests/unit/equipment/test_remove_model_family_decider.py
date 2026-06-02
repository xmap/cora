"""Pure-decider tests for the `remove_model_family` slice.

Targeted mutation of `Model.declared_families`, not a lifecycle
transition. Status is preserved (`Defined` stays `Defined`,
`Versioned` stays `Versioned`); only `Deprecated` is rejected via
the per-verb `ModelCannotRemoveFamilyError` (mirrors
`AssetCannotRemoveFamilyError`).

Strict-not-idempotent: removing a family not in `declared_families`
raises `ModelFamilyNotPresentError`, mirroring the
`remove_asset_family` precedent.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    Model,
    ModelCannotRemoveFamilyError,
    ModelFamilyNotPresentError,
    ModelFamilyRemoved,
    ModelName,
    ModelNotFoundError,
    ModelStatus,
    PartNumber,
)
from cora.equipment.features import remove_model_family
from cora.equipment.features.remove_model_family import RemoveModelFamily

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
def test_decide_emits_model_family_removed_from_defined_state() -> None:
    existing = uuid4()
    state = _model(status=ModelStatus.DEFINED, declared_families=frozenset({existing}))
    events = remove_model_family.decide(
        state=state,
        command=RemoveModelFamily(model_id=state.id, family_id=existing),
        now=_NOW,
    )
    assert events == [ModelFamilyRemoved(model_id=state.id, family_id=existing, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_emits_model_family_removed_from_versioned_state() -> None:
    """Status preserved across targeted mutation; Versioned is a valid source."""
    existing = uuid4()
    state = _model(
        status=ModelStatus.VERSIONED,
        version="v2",
        declared_families=frozenset({existing}),
    )
    events = remove_model_family.decide(
        state=state,
        command=RemoveModelFamily(model_id=state.id, family_id=existing),
        now=_NOW,
    )
    assert events == [ModelFamilyRemoved(model_id=state.id, family_id=existing, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_cannot_remove_family_when_deprecated() -> None:
    """Deprecated catalog entries are frozen; remove_model_family rejects."""
    existing = uuid4()
    state = _model(
        status=ModelStatus.DEPRECATED,
        version="v1",
        declared_families=frozenset({existing}),
    )
    with pytest.raises(ModelCannotRemoveFamilyError) as exc_info:
        remove_model_family.decide(
            state=state,
            command=RemoveModelFamily(model_id=state.id, family_id=existing),
            now=_NOW,
        )
    assert exc_info.value.model_id == state.id
    assert exc_info.value.current_status is ModelStatus.DEPRECATED


@pytest.mark.unit
def test_decide_raises_model_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(ModelNotFoundError) as exc_info:
        remove_model_family.decide(
            state=None,
            command=RemoveModelFamily(model_id=target_id, family_id=uuid4()),
            now=_NOW,
        )
    assert exc_info.value.model_id == target_id


@pytest.mark.unit
def test_decide_raises_not_present_on_absent_family() -> None:
    """Strict-not-idempotent: removing an absent family raises rather
    than no-op so operators can detect 'wait, this was never declared'
    instead of silently succeeding."""
    declared = uuid4()
    absent = uuid4()
    state = _model(declared_families=frozenset({declared}))
    with pytest.raises(ModelFamilyNotPresentError) as exc_info:
        remove_model_family.decide(
            state=state,
            command=RemoveModelFamily(model_id=state.id, family_id=absent),
            now=_NOW,
        )
    assert exc_info.value.model_id == state.id
    assert exc_info.value.family_id == absent


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    family = uuid4()
    state = _model(declared_families=frozenset({family}))
    command = RemoveModelFamily(model_id=state.id, family_id=family)
    first = remove_model_family.decide(state=state, command=command, now=_NOW)
    second = remove_model_family.decide(state=state, command=command, now=_NOW)
    assert first == second
