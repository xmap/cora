"""Decider tests for `record_visit_arrival` (Planned -> Arrived; explicit gesture)."""

import pytest

from cora.trust.aggregates.visit import (
    VisitArrived,
    VisitCannotArriveError,
    VisitNotFoundError,
    VisitStatus,
)
from cora.trust.features.record_visit_arrival import RecordVisitArrival
from cora.trust.features.record_visit_arrival.decider import decide
from tests.unit.trust.visit._fixtures import NOW, VISIT_ID, make_visit


@pytest.mark.unit
def test_arrive_from_planned_emits_visit_arrived() -> None:
    events = decide(
        state=make_visit(VisitStatus.PLANNED),
        command=RecordVisitArrival(visit_id=VISIT_ID),
        now=NOW,
    )
    assert len(events) == 1
    [e] = events
    assert isinstance(e, VisitArrived)
    assert e.visit_id == VISIT_ID
    assert e.occurred_at == NOW


@pytest.mark.unit
def test_arrive_raises_not_found_on_empty_state() -> None:
    with pytest.raises(VisitNotFoundError):
        decide(state=None, command=RecordVisitArrival(visit_id=VISIT_ID), now=NOW)


@pytest.mark.parametrize(
    "current_status",
    [
        VisitStatus.ARRIVED,
        VisitStatus.IN_PROGRESS,
        VisitStatus.ON_HOLD,
    ],
)
@pytest.mark.unit
def test_arrive_rejects_non_planned_statuses(current_status: VisitStatus) -> None:
    with pytest.raises(VisitCannotArriveError) as exc_info:
        decide(
            state=make_visit(current_status),
            command=RecordVisitArrival(visit_id=VISIT_ID),
            now=NOW,
        )
    assert exc_info.value.current_status == current_status
    assert exc_info.value.permitted_sources == (VisitStatus.PLANNED,)
