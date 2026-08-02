"""Decider tests for `check_out_visit` (frozen-replace presence close)."""

from dataclasses import replace
from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from cora.shared.identity import ActorId
from cora.trust.aggregates.visit import (
    PresenceEntry,
    PresenceMode,
    Visit,
    VisitActorNotCheckedInError,
    VisitCheckedOut,
    VisitNotFoundError,
    VisitStatus,
)
from cora.trust.features.check_out_visit import CheckOutVisit
from cora.trust.features.check_out_visit.decider import decide
from tests.unit.trust.visit._fixtures import NOW, VISIT_ID, make_visit


def _state_with_open_entry(actor_id: UUID, status: VisitStatus = VisitStatus.IN_PROGRESS) -> Visit:
    base = make_visit(status)
    return replace(
        base,
        presence_entries=frozenset(
            {
                PresenceEntry(
                    actor_id=actor_id,
                    mode=PresenceMode.PHYSICAL,
                    check_in_at=NOW - timedelta(hours=2),
                    check_out_at=None,
                )
            }
        ),
    )


@pytest.mark.unit
def test_check_out_closes_open_entry_with_visit_checked_out() -> None:
    actor_id = uuid4()
    events = decide(
        state=_state_with_open_entry(actor_id),
        command=CheckOutVisit(visit_id=VISIT_ID),
        now=NOW,
        checked_out_by=ActorId(actor_id),
    )
    [e] = events
    assert isinstance(e, VisitCheckedOut)
    assert e.actor_id == actor_id
    assert e.occurred_at == NOW


@pytest.mark.unit
def test_check_out_raises_not_found_on_empty_state() -> None:
    actor_id = uuid4()
    with pytest.raises(VisitNotFoundError):
        decide(
            state=None,
            command=CheckOutVisit(visit_id=VISIT_ID),
            now=NOW,
            checked_out_by=ActorId(actor_id),
        )


@pytest.mark.unit
def test_check_out_raises_when_actor_has_no_open_entry() -> None:
    actor_id = uuid4()
    base = make_visit(VisitStatus.IN_PROGRESS)
    with pytest.raises(VisitActorNotCheckedInError) as exc_info:
        decide(
            state=base,
            command=CheckOutVisit(visit_id=VISIT_ID),
            now=NOW,
            checked_out_by=ActorId(actor_id),
        )
    assert exc_info.value.visit_id == base.id


@pytest.mark.unit
def test_check_out_rejects_already_closed_actor() -> None:
    actor_id = uuid4()
    base = make_visit(VisitStatus.IN_PROGRESS)
    state_with_closed_entry = replace(
        base,
        presence_entries=frozenset(
            {
                PresenceEntry(
                    actor_id=actor_id,
                    mode=PresenceMode.PHYSICAL,
                    check_in_at=NOW - timedelta(hours=4),
                    check_out_at=NOW - timedelta(hours=2),
                )
            }
        ),
    )
    with pytest.raises(VisitActorNotCheckedInError):
        decide(
            state=state_with_closed_entry,
            command=CheckOutVisit(visit_id=VISIT_ID),
            now=NOW,
            checked_out_by=ActorId(actor_id),
        )


@pytest.mark.unit
def test_check_out_works_after_visit_completion_lifecycle_independent() -> None:
    """Per design memo: check-out does NOT require a particular Visit.status."""
    base = make_visit(VisitStatus.IN_PROGRESS)
    actor_id = uuid4()
    state = replace(
        base,
        presence_entries=frozenset(
            {
                PresenceEntry(
                    actor_id=actor_id,
                    mode=PresenceMode.PHYSICAL,
                    check_in_at=NOW - timedelta(hours=1),
                    check_out_at=None,
                )
            }
        ),
        status=VisitStatus.COMPLETED,
    )
    events = decide(
        state=state,
        command=CheckOutVisit(visit_id=VISIT_ID),
        now=NOW,
        checked_out_by=ActorId(actor_id),
    )
    assert len(events) == 1
