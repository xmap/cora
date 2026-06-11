"""Property-based tests for `remove_family_presents_as.decide`.

Universal claims:
  - State=None always raises FamilyNotFoundError.
  - Role not in presents_as always raises
    FamilyRolePresentsAsNotPresentError (strict-not-idempotent).
  - Role present always emits a single FamilyPresentsAsRemoved.
  - Pure: same inputs always produce the same outputs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.family import (
    Affordance,
    Family,
    FamilyName,
    FamilyNotFoundError,
    FamilyPresentsAsRemoved,
    FamilyRolePresentsAsNotPresentError,
)
from cora.equipment.features import remove_family_presents_as
from cora.equipment.features.remove_family_presents_as import RemoveFamilyPresentsAs
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


def _family(family_id: UUID, *, presents_as: frozenset[RoleId]) -> Family:
    return Family(
        id=family_id,
        name=FamilyName("X"),
        affordances=frozenset({Affordance.IMAGEABLE}),
        presents_as=presents_as,
    )


@pytest.mark.unit
@given(family_id=st.uuids(), role_id=st.uuids(), now=aware_datetimes())
def test_state_none_always_raises_family_not_found(
    family_id: UUID,
    role_id: UUID,
    now: datetime,
) -> None:
    with pytest.raises(FamilyNotFoundError):
        remove_family_presents_as.decide(
            state=None,
            command=RemoveFamilyPresentsAs(family_id=family_id, role_id=role_id),
            now=now,
        )


@pytest.mark.unit
@given(family_id=st.uuids(), role_id=st.uuids(), now=aware_datetimes())
def test_role_not_present_always_raises_not_present(
    family_id: UUID,
    role_id: UUID,
    now: datetime,
) -> None:
    state = _family(family_id, presents_as=frozenset())
    with pytest.raises(FamilyRolePresentsAsNotPresentError):
        remove_family_presents_as.decide(
            state=state,
            command=RemoveFamilyPresentsAs(family_id=family_id, role_id=role_id),
            now=now,
        )


@pytest.mark.unit
@given(family_id=st.uuids(), role_id=st.uuids(), now=aware_datetimes())
def test_role_present_emits_single_event(
    family_id: UUID,
    role_id: UUID,
    now: datetime,
) -> None:
    state = _family(family_id, presents_as=frozenset({RoleId(role_id)}))
    events = remove_family_presents_as.decide(
        state=state,
        command=RemoveFamilyPresentsAs(family_id=family_id, role_id=role_id),
        now=now,
    )
    assert events == [
        FamilyPresentsAsRemoved(family_id=family_id, role_id=role_id, occurred_at=now)
    ]


@pytest.mark.unit
@given(family_id=st.uuids(), role_id=st.uuids(), now=aware_datetimes())
def test_decider_is_pure_same_input_same_output(
    family_id: UUID,
    role_id: UUID,
    now: datetime,
) -> None:
    state = _family(family_id, presents_as=frozenset({RoleId(role_id)}))
    cmd = RemoveFamilyPresentsAs(family_id=family_id, role_id=role_id)
    first = remove_family_presents_as.decide(state=state, command=cmd, now=now)
    second = remove_family_presents_as.decide(state=state, command=cmd, now=now)
    assert first == second
