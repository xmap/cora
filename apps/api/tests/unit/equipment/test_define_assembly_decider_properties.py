"""Property-based tests for `define_assembly.decide` (Equipment BC).

Mirrors `test_register_mount_decider_properties.py` on a create-style
command with a `context` cross-aggregate kwarg. Universal claims
across generated inputs:

  - state=None + empty missing_family_ids + valid command emits a
    single AssemblyDefined with the injected ids / now and an
    AssemblyName-trimmed name.
  - state=Assembly always raises AssemblyAlreadyExistsError carrying
    the pre-existing assembly_id.
  - state=None + non-empty missing_family_ids always raises
    FamilyNotFoundForAssemblyError carrying the sorted-first missing
    family_id for deterministic responses.
  - Pure: same (state, command, context, now, new_id) returns the
    same events (including the same content_hash).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.assembly import (
    ASSEMBLY_NAME_MAX_LENGTH,
    Assembly,
    AssemblyAlreadyExistsError,
    AssemblyDefined,
    AssemblyName,
    AssemblyStatus,
    FamilyNotFoundForAssemblyError,
)
from cora.equipment.features import define_assembly
from cora.equipment.features.define_assembly import (
    DefineAssembly,
    DefineAssemblyContext,
)
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_NAME = printable_ascii_text(min_size=1, max_size=ASSEMBLY_NAME_MAX_LENGTH)


def _assembly(assembly_id: UUID, family_id: UUID) -> Assembly:
    return Assembly(
        id=assembly_id,
        name=AssemblyName("Existing"),
        presents_as=frozenset({RoleId(family_id)}),
        status=AssemblyStatus.DEFINED,
    )


@pytest.mark.unit
@given(
    name=_NAME,
    now=aware_datetimes(),
)
def test_decide_genesis_emits_assembly_defined_carrying_injected_fields(
    name: str,
    now: datetime,
) -> None:
    new_id = uuid4()
    family_id = uuid4()
    events = define_assembly.decide(
        state=None,
        command=DefineAssembly(name=name, presents_as=frozenset({RoleId(family_id)})),
        context=DefineAssemblyContext(missing_family_ids=frozenset()),
        now=now,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, AssemblyDefined)
    assert event.assembly_id == new_id
    assert event.presents_as == frozenset({family_id})
    assert event.occurred_at == now
    assert event.name == AssemblyName(name)
    assert len(event.content_hash) == 64


@pytest.mark.unit
@given(
    name=_NAME,
    now=aware_datetimes(),
)
def test_decide_non_none_state_always_raises_already_exists(
    name: str,
    now: datetime,
) -> None:
    existing_id = uuid4()
    family_id = uuid4()
    state = _assembly(existing_id, family_id)
    with pytest.raises(AssemblyAlreadyExistsError) as exc_info:
        define_assembly.decide(
            state=state,
            command=DefineAssembly(name=name, presents_as=frozenset({RoleId(family_id)})),
            context=DefineAssemblyContext(missing_family_ids=frozenset()),
            now=now,
            new_id=uuid4(),
        )
    assert exc_info.value.assembly_id == existing_id


@pytest.mark.unit
@given(
    name=_NAME,
    missing_count=st.integers(min_value=1, max_value=5),
    now=aware_datetimes(),
)
def test_decide_with_missing_families_always_raises_family_not_found(
    name: str,
    missing_count: int,
    now: datetime,
) -> None:
    missing = frozenset(uuid4() for _ in range(missing_count))
    with pytest.raises(FamilyNotFoundForAssemblyError) as exc_info:
        define_assembly.decide(
            state=None,
            command=DefineAssembly(name=name, presents_as=frozenset({RoleId(uuid4())})),
            context=DefineAssemblyContext(missing_family_ids=missing),
            now=now,
            new_id=uuid4(),
        )
    expected_first = sorted(missing, key=str)[0]
    assert exc_info.value.family_id == expected_first


@pytest.mark.unit
@given(
    name=_NAME,
    now=aware_datetimes(),
)
def test_decide_is_pure_same_inputs_yield_same_events(
    name: str,
    now: datetime,
) -> None:
    new_id = uuid4()
    family_id = uuid4()
    command = DefineAssembly(name=name, presents_as=frozenset({RoleId(family_id)}))
    context = DefineAssemblyContext(missing_family_ids=frozenset())
    events_a = define_assembly.decide(
        state=None,
        command=command,
        context=context,
        now=now,
        new_id=new_id,
    )
    events_b = define_assembly.decide(
        state=None,
        command=command,
        context=context,
        now=now,
        new_id=new_id,
    )
    assert events_a == events_b
    assert events_a[0].content_hash == events_b[0].content_hash
