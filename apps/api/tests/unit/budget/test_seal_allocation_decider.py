"""Pure-decider tests for the `seal_allocation` slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.budget.aggregates.allocation import (
    AllocationCannotSealError,
    AllocationNotFoundError,
    AllocationSealed,
    AllocationStatus,
    InvalidAllocationReasonError,
)
from cora.budget.features.seal_allocation.command import SealAllocation
from cora.budget.features.seal_allocation.decider import decide
from cora.shared.identity import ActorId
from cora.shared.text_bounds import REASON_MAX_LENGTH
from tests.unit.budget._helpers import make_allocation

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
_SEALED_BY = ActorId(UUID("01900000-0000-7000-8000-000000000099"))


@pytest.mark.unit
def test_seal_from_active_emits_sealed_event_with_reader_snapshot() -> None:
    envelope = make_allocation(AllocationStatus.ACTIVE)
    events = decide(
        state=envelope,
        command=SealAllocation(allocation_id=envelope.id),
        now=_NOW,
        spent_usd=812.4,
        sealed_by=_SEALED_BY,
    )
    assert events == [
        AllocationSealed(
            allocation_id=envelope.id,
            spent_usd=812.4,
            reason=None,
            sealed_by=_SEALED_BY,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_seal_reason_trims_and_carries() -> None:
    envelope = make_allocation(AllocationStatus.ACTIVE)
    events = decide(
        state=envelope,
        command=SealAllocation(allocation_id=envelope.id, reason="  Campaign closed early  "),
        now=_NOW,
        spent_usd=0.0,
        sealed_by=_SEALED_BY,
    )
    assert events[0].reason == "Campaign closed early"


@pytest.mark.unit
@pytest.mark.parametrize("bad_reason", ["", "   ", "x" * (REASON_MAX_LENGTH + 1)])
def test_invalid_reason_raises(bad_reason: str) -> None:
    envelope = make_allocation(AllocationStatus.ACTIVE)
    with pytest.raises(InvalidAllocationReasonError):
        decide(
            state=envelope,
            command=SealAllocation(allocation_id=envelope.id, reason=bad_reason),
            now=_NOW,
            spent_usd=0.0,
            sealed_by=_SEALED_BY,
        )


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    with pytest.raises(AllocationNotFoundError):
        decide(
            state=None,
            command=SealAllocation(allocation_id=uuid4()),
            now=_NOW,
            spent_usd=0.0,
            sealed_by=_SEALED_BY,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [
        AllocationStatus.GRANTED,
        AllocationStatus.SEALED,
        AllocationStatus.VOIDED,
    ],
)
def test_seal_from_non_active_raises_cannot_seal(status: AllocationStatus) -> None:
    """A dormant grant has no open window to close (void it instead);
    terminals are already closed."""
    envelope = make_allocation(status)
    with pytest.raises(AllocationCannotSealError):
        decide(
            state=envelope,
            command=SealAllocation(allocation_id=envelope.id),
            now=_NOW,
            spent_usd=0.0,
            sealed_by=_SEALED_BY,
        )


@pytest.mark.unit
def test_event_uses_handler_supplied_snapshot_and_actor() -> None:
    """Non-determinism principle: the ledger fold and the acting
    principal are inputs, never recomputed here."""
    envelope = make_allocation(AllocationStatus.ACTIVE)
    custom_actor = ActorId(uuid4())
    events = decide(
        state=envelope,
        command=SealAllocation(allocation_id=envelope.id),
        now=_NOW,
        spent_usd=12345.67,
        sealed_by=custom_actor,
    )
    assert events[0].spent_usd == 12345.67
    assert events[0].sealed_by == custom_actor
