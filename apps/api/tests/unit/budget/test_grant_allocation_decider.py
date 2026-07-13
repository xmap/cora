"""Pure-decider tests for the `grant_allocation` slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.budget.aggregates.allocation import (
    ALLOCATION_NOTE_MAX_LENGTH,
    AllocationAlreadyExistsError,
    AllocationGranted,
    AllocationStatus,
    InvalidAllocationCeilingError,
    InvalidAllocationNoteError,
)
from cora.budget.features.grant_allocation.command import GrantAllocation
from cora.budget.features.grant_allocation.decider import decide
from cora.shared.identity import ActorId
from tests.unit.budget._helpers import make_allocation

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
_NEW_ID = uuid4()
_GRANTED_BY = ActorId(UUID("01900000-0000-7000-8000-000000000099"))
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000000044")


def _command(**overrides: object) -> GrantAllocation:
    base: dict[str, object] = {
        "ceiling_usd": 25000.0,
        "note": "FY26 imaging award",
    }
    base.update(overrides)
    return GrantAllocation(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_minimal_command_emits_single_allocation_granted() -> None:
    events = decide(
        state=None, command=_command(), now=_NOW, new_id=_NEW_ID, granted_by=_GRANTED_BY
    )
    assert events == [
        AllocationGranted(
            allocation_id=_NEW_ID,
            ceiling_usd=25000.0,
            campaign_id=None,
            note="FY26 imaging award",
            granted_by=_GRANTED_BY,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_campaign_bound_command_carries_campaign_id() -> None:
    events = decide(
        state=None,
        command=_command(campaign_id=_CAMPAIGN_ID),
        now=_NOW,
        new_id=_NEW_ID,
        granted_by=_GRANTED_BY,
    )
    assert events[0].campaign_id == _CAMPAIGN_ID


@pytest.mark.unit
def test_genesis_collision_raises_already_exists() -> None:
    existing = make_allocation(AllocationStatus.GRANTED, allocation_id=_NEW_ID)
    with pytest.raises(AllocationAlreadyExistsError):
        decide(
            state=existing,
            command=_command(),
            now=_NOW,
            new_id=_NEW_ID,
            granted_by=_GRANTED_BY,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad_ceiling",
    [0.0, -1.0, -25000.0, float("nan"), float("inf"), float("-inf")],
)
def test_non_positive_or_non_finite_ceiling_raises(bad_ceiling: float) -> None:
    with pytest.raises(InvalidAllocationCeilingError):
        decide(
            state=None,
            command=_command(ceiling_usd=bad_ceiling),
            now=_NOW,
            new_id=_NEW_ID,
            granted_by=_GRANTED_BY,
        )


@pytest.mark.unit
@pytest.mark.parametrize("bad_note", ["", "   ", "x" * (ALLOCATION_NOTE_MAX_LENGTH + 1)])
def test_invalid_note_raises(bad_note: str) -> None:
    with pytest.raises(InvalidAllocationNoteError):
        decide(
            state=None,
            command=_command(note=bad_note),
            now=_NOW,
            new_id=_NEW_ID,
            granted_by=_GRANTED_BY,
        )


@pytest.mark.unit
def test_note_trim_propagates() -> None:
    """The VO trims; the decider passes the trimmed value into the event."""
    events = decide(
        state=None,
        command=_command(note="  FY26 imaging award  "),
        now=_NOW,
        new_id=_NEW_ID,
        granted_by=_GRANTED_BY,
    )
    assert events[0].note == "FY26 imaging award"


@pytest.mark.unit
def test_event_uses_handler_supplied_now_new_id_and_granted_by() -> None:
    """Non-determinism principle: decider takes now + new_id + actor as inputs."""
    custom_now = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
    custom_id = uuid4()
    custom_actor = ActorId(uuid4())
    events = decide(
        state=None,
        command=_command(),
        now=custom_now,
        new_id=custom_id,
        granted_by=custom_actor,
    )
    assert events[0].occurred_at == custom_now
    assert events[0].allocation_id == custom_id
    assert events[0].granted_by == custom_actor
