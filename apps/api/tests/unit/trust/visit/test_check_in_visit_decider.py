"""Decider tests for `check_in_visit` (presence + status guard)."""

from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest

from cora.trust.aggregates.visit import (
    PresenceEntry,
    PresenceMode,
    VisitAlreadyCheckedInError,
    VisitCannotCheckInError,
    VisitCheckedIn,
    VisitNotFoundError,
    VisitStatus,
)
from cora.trust.features.check_in_visit import CheckInVisit
from cora.trust.features.check_in_visit.decider import decide
from tests.unit.trust.visit._fixtures import NOW, VISIT_ID, make_visit


@pytest.mark.parametrize(
    "from_status",
    [VisitStatus.ARRIVED, VisitStatus.IN_PROGRESS, VisitStatus.ON_HOLD],
)
@pytest.mark.unit
def test_check_in_from_permitted_statuses_emits_visit_checked_in(
    from_status: VisitStatus,
) -> None:
    actor_id = uuid4()
    events = decide(
        state=make_visit(from_status),
        command=CheckInVisit(visit_id=VISIT_ID, actor_id=actor_id, mode=PresenceMode.PHYSICAL),
        now=NOW,
    )
    [e] = events
    assert isinstance(e, VisitCheckedIn)
    assert e.actor_id == actor_id
    assert e.mode == "physical"


@pytest.mark.unit
def test_check_in_carries_remote_mode_through_to_event() -> None:
    events = decide(
        state=make_visit(VisitStatus.IN_PROGRESS),
        command=CheckInVisit(visit_id=VISIT_ID, actor_id=uuid4(), mode=PresenceMode.REMOTE),
        now=NOW,
    )
    assert events[0].mode == "remote"


@pytest.mark.unit
def test_check_in_raises_not_found_on_empty_state() -> None:
    with pytest.raises(VisitNotFoundError):
        decide(
            state=None,
            command=CheckInVisit(visit_id=VISIT_ID, actor_id=uuid4(), mode=PresenceMode.PHYSICAL),
            now=NOW,
        )


@pytest.mark.unit
def test_check_in_rejects_planned_status_does_not_auto_arrive() -> None:
    """V6 explicit-gesture lock: presence does NOT auto-transition Planned
    -> Arrived. Operator must record_visit_arrival first."""
    with pytest.raises(VisitCannotCheckInError):
        decide(
            state=make_visit(VisitStatus.PLANNED),
            command=CheckInVisit(visit_id=VISIT_ID, actor_id=uuid4(), mode=PresenceMode.PHYSICAL),
            now=NOW,
        )


@pytest.mark.unit
def test_check_in_rejects_duplicate_open_entry_for_same_actor() -> None:
    actor_id = uuid4()
    base = make_visit(VisitStatus.IN_PROGRESS)
    state_with_open_entry = replace(
        base,
        presence_entries=frozenset(
            {
                PresenceEntry(
                    actor_id=actor_id,
                    mode=PresenceMode.PHYSICAL,
                    check_in_at=NOW,
                    check_out_at=None,
                )
            }
        ),
    )
    with pytest.raises(VisitAlreadyCheckedInError) as exc_info:
        decide(
            state=state_with_open_entry,
            command=CheckInVisit(visit_id=VISIT_ID, actor_id=actor_id, mode=PresenceMode.REMOTE),
            now=NOW,
        )
    assert exc_info.value.actor_id == actor_id


@pytest.mark.unit
def test_check_in_allows_same_actor_after_check_out_multi_shift() -> None:
    """Multi-shift: same actor may check in again after a prior cycle closed."""
    actor_id = uuid4()
    earlier = NOW - timedelta(hours=4)
    base = make_visit(VisitStatus.IN_PROGRESS)
    state_with_closed_entry = replace(
        base,
        presence_entries=frozenset(
            {
                PresenceEntry(
                    actor_id=actor_id,
                    mode=PresenceMode.PHYSICAL,
                    check_in_at=earlier,
                    check_out_at=earlier + timedelta(hours=2),
                )
            }
        ),
    )
    events = decide(
        state=state_with_closed_entry,
        command=CheckInVisit(visit_id=VISIT_ID, actor_id=actor_id, mode=PresenceMode.REMOTE),
        now=NOW,
    )
    assert len(events) == 1
