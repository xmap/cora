"""Property-based tests for `deprecate_assembly.decide` (Equipment BC)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyCannotDeprecateError,
    AssemblyDeprecated,
    AssemblyName,
    AssemblyNotFoundError,
    AssemblyStatus,
)
from cora.equipment.features import deprecate_assembly
from cora.equipment.features.deprecate_assembly import DeprecateAssembly
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_REASON = printable_ascii_text(min_size=1, max_size=500)
_DEPRECATABLE_STATUS = st.sampled_from((AssemblyStatus.DEFINED, AssemblyStatus.VERSIONED))


def _state(assembly_id: UUID, status: AssemblyStatus) -> Assembly:
    return Assembly(
        id=assembly_id,
        name=AssemblyName("X"),
        presents_as=frozenset({RoleId(uuid4())}),
        status=status,
    )


@pytest.mark.unit
@given(reason=_REASON, status=_DEPRECATABLE_STATUS, now=aware_datetimes())
def test_decide_deprecatable_state_emits_deprecated_event(
    reason: str,
    status: AssemblyStatus,
    now: datetime,
) -> None:
    assembly_id = uuid4()
    state = _state(assembly_id, status)
    events = deprecate_assembly.decide(
        state=state,
        command=DeprecateAssembly(assembly_id=assembly_id, reason=reason),
        now=now,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, AssemblyDeprecated)
    assert event.assembly_id == assembly_id
    assert event.reason == reason
    assert event.occurred_at == now


@pytest.mark.unit
@given(reason=_REASON, now=aware_datetimes())
def test_decide_none_state_always_raises_not_found(
    reason: str,
    now: datetime,
) -> None:
    target_id = uuid4()
    with pytest.raises(AssemblyNotFoundError) as exc_info:
        deprecate_assembly.decide(
            state=None,
            command=DeprecateAssembly(assembly_id=target_id, reason=reason),
            now=now,
        )
    assert exc_info.value.assembly_id == target_id


@pytest.mark.unit
@given(reason=_REASON, now=aware_datetimes())
def test_decide_deprecated_state_always_raises_cannot_deprecate(
    reason: str,
    now: datetime,
) -> None:
    assembly_id = uuid4()
    state = _state(assembly_id, AssemblyStatus.DEPRECATED)
    with pytest.raises(AssemblyCannotDeprecateError) as exc_info:
        deprecate_assembly.decide(
            state=state,
            command=DeprecateAssembly(assembly_id=assembly_id, reason=reason),
            now=now,
        )
    assert exc_info.value.assembly_id == assembly_id


@pytest.mark.unit
@given(reason=_REASON, status=_DEPRECATABLE_STATUS, now=aware_datetimes())
def test_decide_is_pure_same_inputs_yield_same_events(
    reason: str,
    status: AssemblyStatus,
    now: datetime,
) -> None:
    assembly_id = uuid4()
    state = _state(assembly_id, status)
    command = DeprecateAssembly(assembly_id=assembly_id, reason=reason)
    events_a = deprecate_assembly.decide(state, command, now=now)
    events_b = deprecate_assembly.decide(state, command, now=now)
    assert events_a == events_b
