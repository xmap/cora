"""Property-based tests for `add_assembly_presents_as.decide`.

Universal claims:
  - State=None always raises AssemblyNotFoundError.
  - Role already in presents_as always raises
    AssemblyRolePresentsAsAlreadyError.
  - Empty presents_as + any role -> single AssemblyPresentsAsAdded.
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
    AssemblyPresentsAsAdded,
    AssemblyRolePresentsAsAlreadyError,
)
from cora.equipment.features import add_assembly_presents_as
from cora.equipment.features.add_assembly_presents_as import AddAssemblyPresentsAs
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
        add_assembly_presents_as.decide(
            state=None,
            command=AddAssemblyPresentsAs(assembly_id=assembly_id, role_id=role_id),
            now=now,
        )


@pytest.mark.unit
@given(assembly_id=st.uuids(), role_id=st.uuids(), now=aware_datetimes())
def test_role_already_advertised_always_raises(
    assembly_id: UUID, role_id: UUID, now: datetime
) -> None:
    state = _assembly(assembly_id, presents_as=frozenset({RoleId(role_id)}))
    with pytest.raises(AssemblyRolePresentsAsAlreadyError):
        add_assembly_presents_as.decide(
            state=state,
            command=AddAssemblyPresentsAs(assembly_id=assembly_id, role_id=role_id),
            now=now,
        )


@pytest.mark.unit
@given(assembly_id=st.uuids(), role_id=st.uuids(), now=aware_datetimes())
def test_empty_presents_as_always_emits_single_event(
    assembly_id: UUID, role_id: UUID, now: datetime
) -> None:
    state = _assembly(assembly_id)
    events = add_assembly_presents_as.decide(
        state=state,
        command=AddAssemblyPresentsAs(assembly_id=assembly_id, role_id=role_id),
        now=now,
    )
    assert events == [
        AssemblyPresentsAsAdded(assembly_id=assembly_id, role_id=role_id, occurred_at=now)
    ]


@pytest.mark.unit
@given(assembly_id=st.uuids(), role_id=st.uuids(), now=aware_datetimes())
def test_decider_is_pure_same_input_same_output(
    assembly_id: UUID, role_id: UUID, now: datetime
) -> None:
    state = _assembly(assembly_id)
    cmd = AddAssemblyPresentsAs(assembly_id=assembly_id, role_id=role_id)
    first = add_assembly_presents_as.decide(state=state, command=cmd, now=now)
    second = add_assembly_presents_as.decide(state=state, command=cmd, now=now)
    assert first == second
