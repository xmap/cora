"""Property-based tests for `remove_assembly_presents_as.decide`.

Universal claims:
  - State=None always raises AssemblyNotFoundError.
  - Role not in presents_as always raises
    AssemblyRolePresentsAsNotPresentError.
  - Role present always emits a single AssemblyPresentsAsRemoved.
  - Pure: same inputs always produce the same outputs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyName,
    AssemblyNotFoundError,
    AssemblyPresentsAsRemoved,
    AssemblyRolePresentsAsNotPresentError,
)
from cora.equipment.features import remove_assembly_presents_as
from cora.equipment.features.remove_assembly_presents_as import RemoveAssemblyPresentsAs
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


def _assembly(
    assembly_id: UUID,
    *,
    presents_as: frozenset[RoleId] = frozenset(),
) -> Assembly:
    from uuid import uuid4

    return Assembly(
        id=assembly_id,
        name=AssemblyName("X"),
        presents_as_family_id=uuid4(),
        presents_as=presents_as,
    )


@pytest.mark.unit
@given(assembly_id=st.uuids(), role_id=st.uuids(), now=aware_datetimes())
def test_state_none_always_raises_assembly_not_found(
    assembly_id: UUID, role_id: UUID, now: datetime
) -> None:
    with pytest.raises(AssemblyNotFoundError):
        remove_assembly_presents_as.decide(
            state=None,
            command=RemoveAssemblyPresentsAs(assembly_id=assembly_id, role_id=role_id),
            now=now,
        )


@pytest.mark.unit
@given(assembly_id=st.uuids(), role_id=st.uuids(), now=aware_datetimes())
def test_role_not_present_always_raises_not_present(
    assembly_id: UUID, role_id: UUID, now: datetime
) -> None:
    state = _assembly(assembly_id, presents_as=frozenset())
    with pytest.raises(AssemblyRolePresentsAsNotPresentError):
        remove_assembly_presents_as.decide(
            state=state,
            command=RemoveAssemblyPresentsAs(assembly_id=assembly_id, role_id=role_id),
            now=now,
        )


@pytest.mark.unit
@given(assembly_id=st.uuids(), role_id=st.uuids(), now=aware_datetimes())
def test_role_present_emits_single_event(assembly_id: UUID, role_id: UUID, now: datetime) -> None:
    state = _assembly(assembly_id, presents_as=frozenset({RoleId(role_id)}))
    events = remove_assembly_presents_as.decide(
        state=state,
        command=RemoveAssemblyPresentsAs(assembly_id=assembly_id, role_id=role_id),
        now=now,
    )
    assert events == [
        AssemblyPresentsAsRemoved(assembly_id=assembly_id, role_id=role_id, occurred_at=now)
    ]


@pytest.mark.unit
@given(assembly_id=st.uuids(), role_id=st.uuids(), now=aware_datetimes())
def test_decider_is_pure_same_input_same_output(
    assembly_id: UUID, role_id: UUID, now: datetime
) -> None:
    state = _assembly(assembly_id, presents_as=frozenset({RoleId(role_id)}))
    cmd = RemoveAssemblyPresentsAs(assembly_id=assembly_id, role_id=role_id)
    first = remove_assembly_presents_as.decide(state=state, command=cmd, now=now)
    second = remove_assembly_presents_as.decide(state=state, command=cmd, now=now)
    assert first == second
