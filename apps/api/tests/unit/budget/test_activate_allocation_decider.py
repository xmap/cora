"""Pure-decider tests for the `activate_allocation` slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.budget.aggregates.allocation import (
    AllocationActivated,
    AllocationCannotActivateError,
    AllocationNotFoundError,
    AllocationStatus,
)
from cora.budget.features.activate_allocation.command import ActivateAllocation
from cora.budget.features.activate_allocation.decider import decide
from cora.shared.identity import ActorId
from tests.unit.budget._helpers import make_allocation

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
_ACTIVATED_BY = ActorId(UUID("01900000-0000-7000-8000-000000000099"))


@pytest.mark.unit
def test_activates_a_granted_allocation() -> None:
    envelope = make_allocation(AllocationStatus.GRANTED)
    events = decide(
        state=envelope,
        command=ActivateAllocation(allocation_id=envelope.id),
        now=_NOW,
        activated_by=_ACTIVATED_BY,
    )
    assert events == [
        AllocationActivated(
            allocation_id=envelope.id,
            activated_by=_ACTIVATED_BY,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    with pytest.raises(AllocationNotFoundError):
        decide(
            state=None,
            command=ActivateAllocation(allocation_id=uuid4()),
            now=_NOW,
            activated_by=_ACTIVATED_BY,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [
        AllocationStatus.ACTIVE,
        AllocationStatus.SEALED,
        AllocationStatus.VOIDED,
    ],
)
def test_cannot_activate_from_non_granted(status: AllocationStatus) -> None:
    envelope = make_allocation(status)
    with pytest.raises(AllocationCannotActivateError):
        decide(
            state=envelope,
            command=ActivateAllocation(allocation_id=envelope.id),
            now=_NOW,
            activated_by=_ACTIVATED_BY,
        )
