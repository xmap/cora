"""Property-based tests for `version_assembly.decide` (Equipment BC).

Mirrors `test_define_assembly_decider_properties.py` on the
update-style command. Universal claims across generated inputs:

  - state=None always raises AssemblyNotFoundError carrying the
    command's assembly_id.
  - state.status=Deprecated always raises AssemblyCannotVersionError.
  - state=Defined or Versioned + empty missing_family_ids emits a
    single AssemblyVersioned with the injected now and
    previous_content_hash = state.content_hash.
  - state=Defined/Versioned + non-empty missing_family_ids raises
    FamilyNotFoundForAssemblyError carrying the sorted-first id.
  - Pure: same (state, command, context, now) returns the same
    events (and the same content_hash).
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
    AssemblyCannotVersionError,
    AssemblyName,
    AssemblyNotFoundError,
    AssemblyStatus,
    AssemblyVersioned,
    FamilyNotFoundForAssemblyError,
)
from cora.equipment.features import version_assembly
from cora.equipment.features.version_assembly import (
    VersionAssembly,
    VersionAssemblyContext,
)
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_NAME = printable_ascii_text(min_size=1, max_size=ASSEMBLY_NAME_MAX_LENGTH)

_VERSIONABLE_STATUS = st.sampled_from((AssemblyStatus.DEFINED, AssemblyStatus.VERSIONED))


def _state(assembly_id: UUID, family_id: UUID, status: AssemblyStatus) -> Assembly:
    return Assembly(
        id=assembly_id,
        name=AssemblyName("Initial"),
        presents_as=frozenset({RoleId(family_id)}),
        status=status,
        content_hash="a" * 64,
    )


@pytest.mark.unit
@given(name=_NAME, status=_VERSIONABLE_STATUS, now=aware_datetimes())
def test_decide_versionable_state_emits_versioned_event(
    name: str,
    status: AssemblyStatus,
    now: datetime,
) -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    state = _state(assembly_id, family_id, status)
    events = version_assembly.decide(
        state=state,
        command=VersionAssembly(
            assembly_id=assembly_id,
            name=name,
            presents_as=frozenset({RoleId(family_id)}),
        ),
        context=VersionAssemblyContext(missing_family_ids=frozenset()),
        now=now,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, AssemblyVersioned)
    assert event.assembly_id == assembly_id
    assert event.previous_content_hash == "a" * 64
    assert event.occurred_at == now
    assert len(event.content_hash) == 64


@pytest.mark.unit
@given(name=_NAME, now=aware_datetimes())
def test_decide_none_state_always_raises_not_found(
    name: str,
    now: datetime,
) -> None:
    target_id = uuid4()
    with pytest.raises(AssemblyNotFoundError) as exc_info:
        version_assembly.decide(
            state=None,
            command=VersionAssembly(
                assembly_id=target_id,
                name=name,
                presents_as=frozenset({RoleId(uuid4())}),
            ),
            context=VersionAssemblyContext(missing_family_ids=frozenset()),
            now=now,
        )
    assert exc_info.value.assembly_id == target_id


@pytest.mark.unit
@given(name=_NAME, now=aware_datetimes())
def test_decide_deprecated_state_always_raises_cannot_version(
    name: str,
    now: datetime,
) -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    state = _state(assembly_id, family_id, AssemblyStatus.DEPRECATED)
    with pytest.raises(AssemblyCannotVersionError) as exc_info:
        version_assembly.decide(
            state=state,
            command=VersionAssembly(
                assembly_id=assembly_id,
                name=name,
                presents_as=frozenset({RoleId(family_id)}),
            ),
            context=VersionAssemblyContext(missing_family_ids=frozenset()),
            now=now,
        )
    assert exc_info.value.assembly_id == assembly_id


@pytest.mark.unit
@given(
    name=_NAME,
    status=_VERSIONABLE_STATUS,
    missing_count=st.integers(min_value=1, max_value=5),
    now=aware_datetimes(),
)
def test_decide_versionable_state_with_missing_families_raises_family_not_found(
    name: str,
    status: AssemblyStatus,
    missing_count: int,
    now: datetime,
) -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    state = _state(assembly_id, family_id, status)
    missing = frozenset(uuid4() for _ in range(missing_count))
    with pytest.raises(FamilyNotFoundForAssemblyError) as exc_info:
        version_assembly.decide(
            state=state,
            command=VersionAssembly(
                assembly_id=assembly_id,
                name=name,
                presents_as=frozenset({RoleId(family_id)}),
            ),
            context=VersionAssemblyContext(missing_family_ids=missing),
            now=now,
        )
    assert exc_info.value.family_id in missing


@pytest.mark.unit
@given(name=_NAME, status=_VERSIONABLE_STATUS, now=aware_datetimes())
def test_decide_is_pure_same_inputs_yield_same_events(
    name: str,
    status: AssemblyStatus,
    now: datetime,
) -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    state = _state(assembly_id, family_id, status)
    command = VersionAssembly(
        assembly_id=assembly_id,
        name=name,
        presents_as=frozenset({RoleId(family_id)}),
    )
    context = VersionAssemblyContext(missing_family_ids=frozenset())
    events_a = version_assembly.decide(state, command, context=context, now=now)
    events_b = version_assembly.decide(state, command, context=context, now=now)
    assert events_a == events_b
    assert events_a[0].content_hash == events_b[0].content_hash
