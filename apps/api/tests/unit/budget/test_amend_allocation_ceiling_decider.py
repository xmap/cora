"""Pure-decider tests for the `amend_allocation_ceiling` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.budget.aggregates.allocation import (
    AllocationCannotAmendCeilingError,
    AllocationCeilingAmended,
    AllocationNotFoundError,
    AllocationStatus,
    InvalidAllocationCeilingError,
)
from cora.budget.features.amend_allocation_ceiling.command import AmendAllocationCeiling
from cora.budget.features.amend_allocation_ceiling.decider import decide
from tests.unit.budget._helpers import make_allocation

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
@pytest.mark.parametrize("status", [AllocationStatus.GRANTED, AllocationStatus.ACTIVE])
def test_amends_ceiling_from_granted_and_active(status: AllocationStatus) -> None:
    envelope = make_allocation(status, ceiling_usd=25000.0)
    events = decide(
        state=envelope,
        command=AmendAllocationCeiling(allocation_id=envelope.id, ceiling_usd=18000.0),
        now=_NOW,
    )
    assert events == [
        AllocationCeilingAmended(
            allocation_id=envelope.id,
            ceiling_usd=18000.0,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_same_ceiling_returns_no_events() -> None:
    """PUT semantics are idempotent: a retried amend that matches the
    stored ceiling appends nothing (the update_agent_budget precedent)."""
    envelope = make_allocation(AllocationStatus.ACTIVE, ceiling_usd=25000.0)
    events = decide(
        state=envelope,
        command=AmendAllocationCeiling(allocation_id=envelope.id, ceiling_usd=25000.0),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    with pytest.raises(AllocationNotFoundError):
        decide(
            state=None,
            command=AmendAllocationCeiling(allocation_id=uuid4(), ceiling_usd=100.0),
            now=_NOW,
        )


@pytest.mark.unit
@pytest.mark.parametrize("status", [AllocationStatus.SEALED, AllocationStatus.VOIDED])
def test_cannot_amend_terminal_envelope(status: AllocationStatus) -> None:
    envelope = make_allocation(status)
    with pytest.raises(AllocationCannotAmendCeilingError):
        decide(
            state=envelope,
            command=AmendAllocationCeiling(allocation_id=envelope.id, ceiling_usd=100.0),
            now=_NOW,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad_ceiling",
    [0.0, -1.0, float("nan"), float("inf"), float("-inf")],
)
def test_non_positive_or_non_finite_ceiling_raises(bad_ceiling: float) -> None:
    envelope = make_allocation(AllocationStatus.GRANTED)
    with pytest.raises(InvalidAllocationCeilingError):
        decide(
            state=envelope,
            command=AmendAllocationCeiling(allocation_id=envelope.id, ceiling_usd=bad_ceiling),
            now=_NOW,
        )


@pytest.mark.unit
def test_validation_fires_before_idempotency_short_circuit() -> None:
    """A malformed ceiling raises even when comparison against the
    stored value would have short-circuited: NaN never equals, but the
    guard order is the load-bearing property being pinned."""
    envelope = make_allocation(AllocationStatus.GRANTED, ceiling_usd=25000.0)
    with pytest.raises(InvalidAllocationCeilingError):
        decide(
            state=envelope,
            command=AmendAllocationCeiling(allocation_id=envelope.id, ceiling_usd=float("nan")),
            now=_NOW,
        )
