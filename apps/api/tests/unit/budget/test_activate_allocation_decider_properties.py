"""Property-based tests for `activate_allocation.decide` (budget BC).

Complements the example-based `test_activate_allocation_decider.py`
with universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, *, now, activated_by) -> list[AllocationActivated]

Load-bearing properties:

  - state=None always raises `AllocationNotFoundError` carrying
    command.allocation_id.
  - The source-state partition is total over `AllocationStatus`:
    only `Granted` emits exactly one `AllocationActivated`
    (allocation_id=state.id, activated_by, occurred_at=now); every
    other status raises `AllocationCannotActivateError` carrying the
    current status, so a future status value cannot silently fall
    through.
  - The emitted event's allocation_id is `state.id`, never
    `command.allocation_id`.
  - Pure: same (state, command, now, activated_by) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.budget.aggregates.allocation import (
    AllocationActivated,
    AllocationCannotActivateError,
    AllocationNotFoundError,
    AllocationStatus,
)
from cora.budget.features.activate_allocation.command import ActivateAllocation
from cora.budget.features.activate_allocation.decider import decide
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes
from tests.unit.budget._helpers import make_allocation

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_ACTIVATABLE_SOURCES = (AllocationStatus.GRANTED,)
_DISALLOWED_SOURCES = tuple(s for s in AllocationStatus if s not in frozenset(_ACTIVATABLE_SOURCES))


@pytest.mark.unit
@given(allocation_id=st.uuids(), activated_by=st.uuids(), now=aware_datetimes())
def test_activate_with_none_state_always_raises_not_found(
    allocation_id: UUID,
    activated_by: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises not-found carrying command.allocation_id."""
    with pytest.raises(AllocationNotFoundError) as exc:
        decide(
            state=None,
            command=ActivateAllocation(allocation_id=allocation_id),
            now=now,
            activated_by=ActorId(activated_by),
        )
    assert exc.value.allocation_id == allocation_id


@pytest.mark.unit
@given(allocation_id=st.uuids(), activated_by=st.uuids(), now=aware_datetimes())
def test_activate_from_granted_emits_single_event(
    allocation_id: UUID,
    activated_by: UUID,
    now: datetime,
) -> None:
    """Granted is the only activatable source; emits one AllocationActivated."""
    events = decide(
        state=make_allocation(AllocationStatus.GRANTED, allocation_id=allocation_id),
        command=ActivateAllocation(allocation_id=allocation_id),
        now=now,
        activated_by=ActorId(activated_by),
    )
    assert events == [
        AllocationActivated(
            allocation_id=allocation_id,
            activated_by=ActorId(activated_by),
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    allocation_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    activated_by=st.uuids(),
    now=aware_datetimes(),
)
def test_activate_from_disallowed_source_always_raises_cannot_activate(
    allocation_id: UUID,
    source: AllocationStatus,
    activated_by: UUID,
    now: datetime,
) -> None:
    """Any source other than Granted raises, carrying the current status."""
    with pytest.raises(AllocationCannotActivateError) as exc:
        decide(
            state=make_allocation(source, allocation_id=allocation_id),
            command=ActivateAllocation(allocation_id=allocation_id),
            now=now,
            activated_by=ActorId(activated_by),
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_id=st.uuids(), command_id=st.uuids(), activated_by=st.uuids(), now=aware_datetimes())
def test_activate_uses_state_id_not_command_allocation_id(
    state_id: UUID,
    command_id: UUID,
    activated_by: UUID,
    now: datetime,
) -> None:
    """The emitted event's allocation_id is state.id, not command's."""
    assume(state_id != command_id)
    events = decide(
        state=make_allocation(AllocationStatus.GRANTED, allocation_id=state_id),
        command=ActivateAllocation(allocation_id=command_id),
        now=now,
        activated_by=ActorId(activated_by),
    )
    assert events[0].allocation_id == state_id


@pytest.mark.unit
@given(allocation_id=st.uuids(), activated_by=st.uuids(), now=aware_datetimes())
def test_activate_is_pure_same_input_same_output(
    allocation_id: UUID,
    activated_by: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = make_allocation(AllocationStatus.GRANTED, allocation_id=allocation_id)
    command = ActivateAllocation(allocation_id=allocation_id)
    first = decide(state=state, command=command, now=now, activated_by=ActorId(activated_by))
    second = decide(state=state, command=command, now=now, activated_by=ActorId(activated_by))
    assert first == second
