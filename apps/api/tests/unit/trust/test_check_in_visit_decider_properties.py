"""Property-based tests for `check_in_visit.decide` (Trust BC, Visit aggregate).

Complements the example-based `visit/test_check_in_visit_decider.py` with
universal claims across generated inputs. The decider is a pure
two-part-guard transition

    (state, command, now) -> list[VisitCheckedIn]

that adds one open presence entry for `command.actor_id`.

Load-bearing properties:

  - state=None always raises `VisitNotFoundError` carrying command.visit_id
    (existence guard).
  - The source-state partition is total over `VisitStatus`: only
    `{Arrived, InProgress, OnHold}` may check in; every other status
    raises `VisitCannotCheckInError` carrying the current status, so a
    future status value cannot silently fall through.
  - An actor who already holds an open presence entry always raises
    `VisitAlreadyCheckedInError` carrying that actor_id.
  - A clean check-in from a permitted status emits exactly one
    `VisitCheckedIn` keyed on state.id (never command.visit_id), the
    threaded actor_id, the command's mode value, and occurred_at=now.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.trust.aggregates.visit import (
    PresenceEntry,
    PresenceMode,
    Visit,
    VisitAlreadyCheckedInError,
    VisitCannotCheckInError,
    VisitCheckedIn,
    VisitNotFoundError,
    VisitStatus,
    VisitType,
)
from cora.trust.features.check_in_visit import CheckInVisit
from cora.trust.features.check_in_visit.decider import decide
from tests._strategies import aware_datetimes

_POLICY_ID = UUID("01900000-0000-7000-8000-00000000a002")
_SURFACE_ID = UUID("01900000-0000-7000-8000-00000000a003")
_PLANNED_START = datetime.fromisoformat("2026-05-27T12:00:00+00:00")
_PLANNED_END = _PLANNED_START + timedelta(hours=8)

_PERMITTED_SOURCES = (VisitStatus.ARRIVED, VisitStatus.IN_PROGRESS, VisitStatus.ON_HOLD)
_DISALLOWED_SOURCES = tuple(s for s in VisitStatus if s not in frozenset(_PERMITTED_SOURCES))


def _visit(
    *,
    visit_id: UUID,
    status: VisitStatus,
    presence_entries: frozenset[PresenceEntry] = frozenset(),
) -> Visit:
    return Visit(
        id=visit_id,
        policy_id=_POLICY_ID,
        surface_id=_SURFACE_ID,
        type=VisitType.USER,
        planned_start_at=_PLANNED_START,
        planned_end_at=_PLANNED_END,
        presence_entries=presence_entries,
        status=status,
    )


def _open_entry(actor_id: UUID) -> PresenceEntry:
    return PresenceEntry(
        actor_id=actor_id,
        mode=PresenceMode.PHYSICAL,
        check_in_at=_PLANNED_START,
        check_out_at=None,
    )


@pytest.mark.unit
@given(visit_id=st.uuids(), actor_id=st.uuids(), now=aware_datetimes())
def test_check_in_with_none_state_always_raises_not_found(
    visit_id: UUID,
    actor_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `VisitNotFoundError` carrying command.visit_id."""
    with pytest.raises(VisitNotFoundError) as exc:
        decide(
            state=None,
            command=CheckInVisit(visit_id=visit_id, actor_id=actor_id, mode=PresenceMode.PHYSICAL),
            now=now,
        )
    assert exc.value.visit_id == visit_id


@pytest.mark.unit
@given(
    visit_id=st.uuids(),
    actor_id=st.uuids(),
    source=st.sampled_from(_PERMITTED_SOURCES),
    mode=st.sampled_from(PresenceMode),
    now=aware_datetimes(),
)
def test_check_in_from_permitted_source_emits_single_event(
    visit_id: UUID,
    actor_id: UUID,
    source: VisitStatus,
    mode: PresenceMode,
    now: datetime,
) -> None:
    """A permitted status with no open entry emits one VisitCheckedIn keyed on state.id."""
    events = decide(
        state=_visit(visit_id=visit_id, status=source),
        command=CheckInVisit(visit_id=visit_id, actor_id=actor_id, mode=mode),
        now=now,
    )
    assert events == [
        VisitCheckedIn(visit_id=visit_id, actor_id=actor_id, mode=mode.value, occurred_at=now)
    ]


@pytest.mark.unit
@given(
    visit_id=st.uuids(),
    actor_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_check_in_from_disallowed_source_always_raises_cannot_check_in(
    visit_id: UUID,
    actor_id: UUID,
    source: VisitStatus,
    now: datetime,
) -> None:
    """Any source outside {Arrived, InProgress, OnHold} raises, carrying the status."""
    with pytest.raises(VisitCannotCheckInError) as exc:
        decide(
            state=_visit(visit_id=visit_id, status=source),
            command=CheckInVisit(visit_id=visit_id, actor_id=actor_id, mode=PresenceMode.PHYSICAL),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    visit_id=st.uuids(),
    actor_id=st.uuids(),
    source=st.sampled_from(_PERMITTED_SOURCES),
    now=aware_datetimes(),
)
def test_check_in_with_open_entry_always_raises_already_checked_in(
    visit_id: UUID,
    actor_id: UUID,
    source: VisitStatus,
    now: datetime,
) -> None:
    """An actor with an existing open presence entry raises, carrying that actor_id."""
    with pytest.raises(VisitAlreadyCheckedInError) as exc:
        decide(
            state=_visit(
                visit_id=visit_id,
                status=source,
                presence_entries=frozenset({_open_entry(actor_id)}),
            ),
            command=CheckInVisit(visit_id=visit_id, actor_id=actor_id, mode=PresenceMode.REMOTE),
            now=now,
        )
    assert exc.value.actor_id == actor_id


@pytest.mark.unit
@given(
    state_visit_id=st.uuids(),
    command_visit_id=st.uuids(),
    actor_id=st.uuids(),
    now=aware_datetimes(),
)
def test_check_in_uses_state_id_not_command_visit_id(
    state_visit_id: UUID,
    command_visit_id: UUID,
    actor_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's visit_id is state.id, not command.visit_id."""
    assume(state_visit_id != command_visit_id)
    events = decide(
        state=_visit(visit_id=state_visit_id, status=VisitStatus.IN_PROGRESS),
        command=CheckInVisit(
            visit_id=command_visit_id, actor_id=actor_id, mode=PresenceMode.PHYSICAL
        ),
        now=now,
    )
    assert events[0].visit_id == state_visit_id


@pytest.mark.unit
@given(visit_id=st.uuids(), actor_id=st.uuids(), now=aware_datetimes())
def test_check_in_is_pure_same_input_same_output(
    visit_id: UUID,
    actor_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _visit(visit_id=visit_id, status=VisitStatus.IN_PROGRESS)
    command = CheckInVisit(visit_id=visit_id, actor_id=actor_id, mode=PresenceMode.PHYSICAL)
    first = decide(state=state, command=command, now=now)
    second = decide(state=state, command=command, now=now)
    assert first == second
