"""Property-based tests for `remove_model_family.decide` (Equipment BC).

Targeted mutation of `Model.declared_families`; status is preserved
across the mutation and only `Deprecated` is rejected (via the shared
`ModelCannotVersionError` gate). Universal claims across generated
inputs:

  - state in {Defined, Versioned} + family_id IN declared_families
    emits exactly one ModelFamilyRemoved with the injected `now`
    timestamp.
  - family_id NOT in declared_families always raises
    ModelFamilyNotPresentError carrying the model + family id.
  - state=None always raises ModelNotFoundError carrying the
    command's model_id.
  - state.status==Deprecated always raises ModelCannotVersionError
    carrying the Deprecated source status.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    Model,
    ModelCannotVersionError,
    ModelFamilyNotPresentError,
    ModelFamilyRemoved,
    ModelName,
    ModelNotFoundError,
    ModelStatus,
    PartNumber,
)
from cora.equipment.features import remove_model_family
from cora.equipment.features.remove_model_family import RemoveModelFamily
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


# Mutable source statuses; only Deprecated is rejected at the slice gate.
_MUTABLE_STATUS = st.sampled_from([ModelStatus.DEFINED, ModelStatus.VERSIONED])

# 1 to 5 pre-existing declared family ids; frozenset dedupes naturally.
_DECLARED_FAMILIES = st.frozensets(st.uuids(), min_size=1, max_size=5)


def _model(
    model_id: UUID,
    *,
    status: ModelStatus,
    declared_families: frozenset[UUID],
) -> Model:
    return Model(
        id=model_id,
        name=ModelName("Existing"),
        manufacturer=Manufacturer(name=ManufacturerName("M")),
        part_number=PartNumber("P"),
        declared_families=declared_families,
        status=status,
        version="v0" if status is ModelStatus.VERSIONED else None,
    )


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    status=_MUTABLE_STATUS,
    declared_families=_DECLARED_FAMILIES,
    now=aware_datetimes(),
    pick_index=st.integers(min_value=0, max_value=4),
)
def test_remove_model_family_emits_one_event_for_present_family(
    model_id: UUID,
    status: ModelStatus,
    declared_families: frozenset[UUID],
    now: datetime,
    pick_index: int,
) -> None:
    """Mutable source + family_id IN declared_families -> exactly one
    ModelFamilyRemoved with the injected `now`."""
    # Pick a deterministic family id from the existing set (declared has
    # at least one member, so the modulo always lands).
    declared_list = sorted(declared_families, key=str)
    target = declared_list[pick_index % len(declared_list)]
    state = _model(model_id, status=status, declared_families=declared_families)
    command = RemoveModelFamily(model_id=model_id, family_id=target)
    events = remove_model_family.decide(state=state, command=command, now=now)
    assert events == [ModelFamilyRemoved(model_id=model_id, family_id=target, occurred_at=now)]


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    status=_MUTABLE_STATUS,
    declared_families=_DECLARED_FAMILIES,
    absent_family=st.uuids(),
    now=aware_datetimes(),
)
def test_remove_model_family_with_absent_family_always_raises(
    model_id: UUID,
    status: ModelStatus,
    declared_families: frozenset[UUID],
    absent_family: UUID,
    now: datetime,
) -> None:
    """family_id NOT in declared_families -> ModelFamilyNotPresentError."""
    # Ensure the absent family is genuinely missing from the prior set.
    declared_without_absent = declared_families - {absent_family}
    state = _model(model_id, status=status, declared_families=declared_without_absent)
    command = RemoveModelFamily(model_id=model_id, family_id=absent_family)
    with pytest.raises(ModelFamilyNotPresentError) as exc:
        remove_model_family.decide(state=state, command=command, now=now)
    assert exc.value.model_id == model_id
    assert exc.value.family_id == absent_family


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    family_id=st.uuids(),
    now=aware_datetimes(),
)
def test_remove_model_family_on_empty_state_always_raises_not_found(
    model_id: UUID,
    family_id: UUID,
    now: datetime,
) -> None:
    """state=None -> ModelNotFoundError carrying command.model_id."""
    command = RemoveModelFamily(model_id=model_id, family_id=family_id)
    with pytest.raises(ModelNotFoundError) as exc:
        remove_model_family.decide(state=None, command=command, now=now)
    assert exc.value.model_id == model_id


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    declared_families=_DECLARED_FAMILIES,
    family_id=st.uuids(),
    now=aware_datetimes(),
)
def test_remove_model_family_on_deprecated_state_always_raises_cannot_version(
    model_id: UUID,
    declared_families: frozenset[UUID],
    family_id: UUID,
    now: datetime,
) -> None:
    """state.status==Deprecated -> ModelCannotVersionError, regardless of
    whether family_id would have been a present remove or an absent one."""
    state = _model(
        model_id,
        status=ModelStatus.DEPRECATED,
        declared_families=declared_families,
    )
    command = RemoveModelFamily(model_id=model_id, family_id=family_id)
    with pytest.raises(ModelCannotVersionError) as exc:
        remove_model_family.decide(state=state, command=command, now=now)
    assert exc.value.model_id == model_id
    assert exc.value.current_status is ModelStatus.DEPRECATED
