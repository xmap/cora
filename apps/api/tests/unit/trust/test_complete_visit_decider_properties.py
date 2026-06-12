"""Property-based tests for `complete_visit.decide` (Trust BC).

Complements the example-based `visit/test_complete_visit_decider.py`
with universal claims across generated inputs. The decider is a pure
multi-source FSM terminal

    (state, command, now) -> list[VisitCompleted]

Load-bearing properties:

  - state=None always raises `VisitNotFoundError` carrying command.visit_id.
  - The source-state partition is total over `VisitStatus`: only
    `InProgress` and `OnHold` emit exactly one `VisitCompleted`
    (visit_id=state.id, occurred_at=now); every other status raises
    `VisitCannotCompleteError` carrying the current status, so a future
    status value cannot silently fall through.
  - The emitted event's visit_id is `state.id`, never `command.visit_id`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.trust.aggregates.visit import (
    Visit,
    VisitCannotCompleteError,
    VisitCompleted,
    VisitNotFoundError,
    VisitStatus,
    VisitType,
)
from cora.trust.features.complete_visit import CompleteVisit
from cora.trust.features.complete_visit.decider import decide
from tests._strategies import aware_datetimes

_POLICY_ID = UUID("01900000-0000-7000-8000-00000000a002")
_SURFACE_ID = UUID("01900000-0000-7000-8000-00000000a003")
_PLANNED_START = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
_PLANNED_END = _PLANNED_START + timedelta(hours=8)

_COMPLETABLE_SOURCES = (VisitStatus.IN_PROGRESS, VisitStatus.ON_HOLD)
_DISALLOWED_SOURCES = tuple(s for s in VisitStatus if s not in frozenset(_COMPLETABLE_SOURCES))


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
def test_complete_with_none_state_always_raises_not_found(
    visit_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `VisitNotFoundError` carrying command.visit_id."""
    with pytest.raises(VisitNotFoundError) as exc:
        decide(state=None, command=CompleteVisit(visit_id=visit_id), now=now)
    assert exc.value.visit_id == visit_id


@pytest.mark.unit
@given(
    visit_id=st.uuids(),
    source=st.sampled_from(_COMPLETABLE_SOURCES),
    now=aware_datetimes(),
)
def test_complete_from_active_source_emits_single_event(
    visit_id: UUID,
    source: VisitStatus,
    now: datetime,
) -> None:
    """InProgress and OnHold are the only completable sources; each emits one event."""
    events = decide(
        state=_visit(visit_id=visit_id, status=source),
        command=CompleteVisit(visit_id=visit_id),
        now=now,
    )
    assert events == [VisitCompleted(visit_id=visit_id, occurred_at=now)]


@pytest.mark.unit
@given(
    visit_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_complete_from_disallowed_source_always_raises_cannot_complete(
    visit_id: UUID,
    source: VisitStatus,
    now: datetime,
) -> None:
    """Any source outside {InProgress, OnHold} raises, carrying the current status."""
    with pytest.raises(VisitCannotCompleteError) as exc:
        decide(
            state=_visit(visit_id=visit_id, status=source),
            command=CompleteVisit(visit_id=visit_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_visit_id=st.uuids(), command_visit_id=st.uuids(), now=aware_datetimes())
def test_complete_uses_state_id_not_command_visit_id(
    state_visit_id: UUID,
    command_visit_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's visit_id is state.id, not command.visit_id."""
    assume(state_visit_id != command_visit_id)
    events = decide(
        state=_visit(visit_id=state_visit_id, status=VisitStatus.IN_PROGRESS),
        command=CompleteVisit(visit_id=command_visit_id),
        now=now,
    )
    assert events[0].visit_id == state_visit_id


@pytest.mark.unit
@given(visit_id=st.uuids(), now=aware_datetimes())
def test_complete_is_pure_same_input_same_output(visit_id: UUID, now: datetime) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _visit(visit_id=visit_id, status=VisitStatus.IN_PROGRESS)
    command = CompleteVisit(visit_id=visit_id)
    first = decide(state=state, command=command, now=now)
    second = decide(state=state, command=command, now=now)
    assert first == second
