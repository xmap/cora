"""Pure-decider tests for the `void_allocation` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.budget.aggregates.allocation import (
    AllocationCannotVoidError,
    AllocationNotFoundError,
    AllocationStatus,
    AllocationVoided,
    InvalidAllocationReasonError,
)
from cora.budget.features.void_allocation.command import VoidAllocation
from cora.budget.features.void_allocation.decider import decide
from cora.shared.text_bounds import REASON_MAX_LENGTH
from tests.unit.budget._helpers import make_allocation

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
@pytest.mark.parametrize("status", [AllocationStatus.GRANTED, AllocationStatus.ACTIVE])
def test_voids_granted_and_active_allocations(status: AllocationStatus) -> None:
    envelope = make_allocation(status)
    events = decide(
        state=envelope,
        command=VoidAllocation(allocation_id=envelope.id, reason="Granted against the wrong cycle"),
        now=_NOW,
    )
    assert events == [
        AllocationVoided(
            allocation_id=envelope.id,
            reason="Granted against the wrong cycle",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_void_reason_trims_and_carries() -> None:
    envelope = make_allocation(AllocationStatus.GRANTED)
    events = decide(
        state=envelope,
        command=VoidAllocation(allocation_id=envelope.id, reason="  Wrong beamline  "),
        now=_NOW,
    )
    assert events[0].reason == "Wrong beamline"


@pytest.mark.unit
@pytest.mark.parametrize("bad_reason", ["", "   ", "x" * (REASON_MAX_LENGTH + 1)])
def test_invalid_reason_raises(bad_reason: str) -> None:
    """The withdrawal reason is REQUIRED: empty, whitespace-only, and
    over-length all refuse."""
    envelope = make_allocation(AllocationStatus.GRANTED)
    with pytest.raises(InvalidAllocationReasonError):
        decide(
            state=envelope,
            command=VoidAllocation(allocation_id=envelope.id, reason=bad_reason),
            now=_NOW,
        )


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    with pytest.raises(AllocationNotFoundError):
        decide(
            state=None,
            command=VoidAllocation(allocation_id=uuid4(), reason="Wrong beamline"),
            now=_NOW,
        )


@pytest.mark.unit
@pytest.mark.parametrize("status", [AllocationStatus.SEALED, AllocationStatus.VOIDED])
def test_cannot_void_terminal_envelope(status: AllocationStatus) -> None:
    """Re-terminating would blur which end the audit trail records."""
    envelope = make_allocation(status)
    with pytest.raises(AllocationCannotVoidError):
        decide(
            state=envelope,
            command=VoidAllocation(allocation_id=envelope.id, reason="Wrong beamline"),
            now=_NOW,
        )
