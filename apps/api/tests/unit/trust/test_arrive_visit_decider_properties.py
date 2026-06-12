"""Property-based tests for `arrive_visit.decide` (Trust BC, Visit aggregate).

Complements the example-based `visit/test_arrive_visit_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, now) -> list[VisitArrived]

Load-bearing properties:

  - state=None always raises `VisitNotFoundError` carrying command.visit_id.
  - The source-state partition is total over `VisitStatus`: only
    `Planned` emits exactly one `VisitArrived` (visit_id=state.id,
    occurred_at=now); every other status raises `VisitCannotArriveError`
    carrying the current status, so a future status value cannot
    silently fall through.
  - The emitted event's visit_id is `state.id`, never `command.visit_id`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.trust.aggregates.visit import (
    Visit,
    VisitArrived,
    VisitCannotArriveError,
    VisitNotFoundError,
    VisitStatus,
    VisitType,
)
from cora.trust.features.arrive_visit import ArriveVisit
from cora.trust.features.arrive_visit.decider import decide
from tests._strategies import aware_datetimes

_POLICY_ID = UUID("01900000-0000-7000-8000-00000000a002")
_SURFACE_ID = UUID("01900000-0000-7000-8000-00000000a003")
_PLANNED_START = datetime.fromisoformat("2026-05-27T12:00:00+00:00")
_PLANNED_END = _PLANNED_START + timedelta(hours=8)

_ARRIVABLE_SOURCES = (VisitStatus.PLANNED,)
_DISALLOWED_SOURCES = tuple(s for s in VisitStatus if s not in frozenset(_ARRIVABLE_SOURCES))


def _visit(*, visit_id: UUID, status: VisitStatus) -> Visit:
    return Visit(
        id=visit_id,
        policy_id=_POLICY_ID,
        surface_id=_SURFACE_ID,
        type=VisitType.USER,
        planned_start_at=_PLANNED_START,
        planned_end_at=_PLANNED_END,
        status=status,
    )


@pytest.mark.unit
@given(visit_id=st.uuids(), now=aware_datetimes())
def test_arrive_with_none_state_always_raises_not_found(
    visit_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `VisitNotFoundError` carrying command.visit_id."""
    with pytest.raises(VisitNotFoundError) as exc:
        decide(state=None, command=ArriveVisit(visit_id=visit_id), now=now)
    assert exc.value.visit_id == visit_id


@pytest.mark.unit
@given(visit_id=st.uuids(), now=aware_datetimes())
def test_arrive_from_planned_emits_single_event(visit_id: UUID, now: datetime) -> None:
    """Planned is the only arrivable source; emits one VisitArrived."""
    events = decide(
        state=_visit(visit_id=visit_id, status=VisitStatus.PLANNED),
        command=ArriveVisit(visit_id=visit_id),
        now=now,
    )
    assert events == [VisitArrived(visit_id=visit_id, occurred_at=now)]


@pytest.mark.unit
@given(
    visit_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_arrive_from_disallowed_source_always_raises_cannot_arrive(
    visit_id: UUID,
    source: VisitStatus,
    now: datetime,
) -> None:
    """Any source other than Planned raises, carrying the current status."""
    with pytest.raises(VisitCannotArriveError) as exc:
        decide(
            state=_visit(visit_id=visit_id, status=source),
            command=ArriveVisit(visit_id=visit_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_visit_id=st.uuids(), command_visit_id=st.uuids(), now=aware_datetimes())
def test_arrive_uses_state_id_not_command_visit_id(
    state_visit_id: UUID,
    command_visit_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's visit_id is state.id, not command.visit_id."""
    assume(state_visit_id != command_visit_id)
    events = decide(
        state=_visit(visit_id=state_visit_id, status=VisitStatus.PLANNED),
        command=ArriveVisit(visit_id=command_visit_id),
        now=now,
    )
    assert events[0].visit_id == state_visit_id


@pytest.mark.unit
@given(visit_id=st.uuids(), now=aware_datetimes())
def test_arrive_is_pure_same_input_same_output(visit_id: UUID, now: datetime) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _visit(visit_id=visit_id, status=VisitStatus.PLANNED)
    command = ArriveVisit(visit_id=visit_id)
    first = decide(state=state, command=command, now=now)
    second = decide(state=state, command=command, now=now)
    assert first == second
