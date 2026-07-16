"""Property-based tests for `void_allocation.decide` (budget BC).

Complements the example-based `test_void_allocation_decider.py` with
universal claims across generated inputs. The decider is a pure FSM
transition

    (state, command, *, now) -> list[AllocationVoided]

Load-bearing properties:

  - state=None always raises `AllocationNotFoundError` carrying
    command.allocation_id.
  - The source-state partition is total over `AllocationStatus`:
    Granted and Active emit exactly one `AllocationVoided`; Sealed
    and Voided always raise `AllocationCannotVoidError` carrying the
    current status.
  - The reason is REQUIRED: whitespace-only strings of any length
    always raise `InvalidAllocationReasonError`; valid reasons carry
    through trimmed.
  - The emitted event's allocation_id is `state.id`, never
    `command.allocation_id`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.budget.aggregates.allocation import (
    AllocationCannotVoidError,
    AllocationNotFoundError,
    AllocationStatus,
    AllocationVoided,
    InvalidAllocationReasonError,
)
from cora.budget.features.void_allocation.command import VoidAllocation
from cora.budget.features.void_allocation.decider import decide
from tests._strategies import aware_datetimes, printable_ascii_text
from tests.unit.budget._helpers import make_allocation

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_VOIDABLE_SOURCES = (AllocationStatus.GRANTED, AllocationStatus.ACTIVE)
_DISALLOWED_SOURCES = tuple(s for s in AllocationStatus if s not in frozenset(_VOIDABLE_SOURCES))

_valid_reasons = printable_ascii_text(max_size=500)
_whitespace_only_reasons = st.text(alphabet=" \t\n", max_size=8)


@pytest.mark.unit
@given(allocation_id=st.uuids(), reason=_valid_reasons, now=aware_datetimes())
def test_void_with_none_state_always_raises_not_found(
    allocation_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Empty stream always raises not-found carrying command.allocation_id."""
    with pytest.raises(AllocationNotFoundError) as exc:
        decide(
            state=None,
            command=VoidAllocation(allocation_id=allocation_id, reason=reason),
            now=now,
        )
    assert exc.value.allocation_id == allocation_id


@pytest.mark.unit
@given(
    allocation_id=st.uuids(),
    source=st.sampled_from(_VOIDABLE_SOURCES),
    reason=_valid_reasons,
    now=aware_datetimes(),
)
def test_void_from_voidable_source_emits_single_event(
    allocation_id: UUID,
    source: AllocationStatus,
    reason: str,
    now: datetime,
) -> None:
    """Granted and Active both void; the event carries the trimmed reason."""
    events = decide(
        state=make_allocation(source, allocation_id=allocation_id),
        command=VoidAllocation(allocation_id=allocation_id, reason=reason),
        now=now,
    )
    assert events == [
        AllocationVoided(allocation_id=allocation_id, reason=reason.strip(), occurred_at=now)
    ]


@pytest.mark.unit
@given(
    allocation_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    reason=_valid_reasons,
    now=aware_datetimes(),
)
def test_void_from_terminal_source_always_raises_cannot_void(
    allocation_id: UUID,
    source: AllocationStatus,
    reason: str,
    now: datetime,
) -> None:
    """Any terminal source raises, carrying the current status."""
    with pytest.raises(AllocationCannotVoidError) as exc:
        decide(
            state=make_allocation(source, allocation_id=allocation_id),
            command=VoidAllocation(allocation_id=allocation_id, reason=reason),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    source=st.sampled_from(_VOIDABLE_SOURCES),
    reason=_whitespace_only_reasons,
    now=aware_datetimes(),
)
def test_void_whitespace_only_reason_always_raises(
    source: AllocationStatus,
    reason: str,
    now: datetime,
) -> None:
    """The reason is REQUIRED: anything that trims to empty refuses."""
    envelope = make_allocation(source)
    with pytest.raises(InvalidAllocationReasonError):
        decide(
            state=envelope,
            command=VoidAllocation(allocation_id=envelope.id, reason=reason),
            now=now,
        )


@pytest.mark.unit
@given(state_id=st.uuids(), command_id=st.uuids(), now=aware_datetimes())
def test_void_uses_state_id_not_command_allocation_id(
    state_id: UUID,
    command_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's allocation_id is state.id, not command's."""
    assume(state_id != command_id)
    events = decide(
        state=make_allocation(AllocationStatus.GRANTED, allocation_id=state_id),
        command=VoidAllocation(allocation_id=command_id, reason="Wrong beamline"),
        now=now,
    )
    assert events[0].allocation_id == state_id


@pytest.mark.unit
@given(reason=_valid_reasons, now=aware_datetimes())
def test_void_is_pure_same_input_same_output(reason: str, now: datetime) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    envelope = make_allocation(AllocationStatus.ACTIVE)
    command = VoidAllocation(allocation_id=envelope.id, reason=reason)
    first = decide(state=envelope, command=command, now=now)
    second = decide(state=envelope, command=command, now=now)
    assert first == second
