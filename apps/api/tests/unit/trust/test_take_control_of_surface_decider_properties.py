"""Property-based tests for `take_control_of_surface.decide` (Trust BC).

Complements the example-based `test_take_control_of_surface_decider.py`
with universal claims across generated inputs. `take_control_of_surface`
is a bespoke cross-aggregate decider that validates the requesting Visit
against a Surface-controller snapshot (`context.active_holder`) and emits
a single `VisitSurfaceControlTaken`. The full gate matrix (surface
mismatch, status partition, parent-descendant ancestry, self-holding
idempotency) is pinned by the example tests; the PBT asserts the
universal claims that hold across the whole input space:

  - Any None state always raises `VisitNotFoundError` carrying
    command.visit_id, regardless of context / command / now.
  - A representative disallowed status (Planned, the one non-terminal
    status outside {Arrived, InProgress, OnHold}) always raises
    `VisitCannotTakeControlError(reason="status_not_eligible")`.
  - A surface_id that does not match state.surface_id always raises
    `VisitCannotTakeControlError(reason="surface_mismatch")`.
  - On the clean path (permitted status, matching surface, free Surface)
    the single `VisitSurfaceControlTaken` carries the injected fields:
    visit_id=state.id, surface_id=command.surface_id, occurred_at=now.
  - Pure: same inputs return equal results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.trust.aggregates.visit import (
    VisitCannotTakeControlError,
    VisitNotFoundError,
    VisitStatus,
    VisitSurfaceControlTaken,
)
from cora.trust.features.take_control_of_surface import TakeControlOfSurface
from cora.trust.features.take_control_of_surface.context import TakeControlOfSurfaceContext
from cora.trust.features.take_control_of_surface.decider import decide
from cora.trust.projections.surface_active_visit import SurfaceActiveVisit
from tests._strategies import aware_datetimes
from tests.unit.trust.visit._fixtures import SURFACE_ID, VISIT_ID, make_visit

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_PERMITTED = st.sampled_from([VisitStatus.ARRIVED, VisitStatus.IN_PROGRESS, VisitStatus.ON_HOLD])


def _context(*, active_holder: SurfaceActiveVisit | None = None) -> TakeControlOfSurfaceContext:
    return TakeControlOfSurfaceContext(active_holder=active_holder)


def _command(*, visit_id: UUID = VISIT_ID, surface_id: UUID = SURFACE_ID) -> TakeControlOfSurface:
    return TakeControlOfSurface(visit_id=visit_id, surface_id=surface_id)


@pytest.mark.unit
@given(
    visit_id=st.uuids(),
    surface_id=st.uuids(),
    holder_id=st.uuids(),
    now=aware_datetimes(),
)
def test_take_on_none_state_always_raises_not_found(
    visit_id: UUID,
    surface_id: UUID,
    holder_id: UUID,
    now: datetime,
) -> None:
    """Any None state raises VisitNotFoundError carrying command.visit_id."""
    with pytest.raises(VisitNotFoundError) as exc:
        decide(
            state=None,
            command=_command(visit_id=visit_id, surface_id=surface_id),
            context=_context(active_holder=SurfaceActiveVisit(visit_id=holder_id, since_at=now)),
            now=now,
        )
    assert exc.value.visit_id == visit_id


@pytest.mark.unit
@given(now=aware_datetimes())
def test_take_from_planned_status_always_raises_status_not_eligible(now: datetime) -> None:
    """The one non-terminal disallowed status raises status_not_eligible."""
    with pytest.raises(VisitCannotTakeControlError) as exc:
        decide(
            state=make_visit(VisitStatus.PLANNED),
            command=_command(),
            context=_context(),
            now=now,
        )
    assert exc.value.reason == "status_not_eligible"


@pytest.mark.unit
@given(status=_PERMITTED, other_surface=st.uuids(), now=aware_datetimes())
def test_take_with_surface_mismatch_always_raises_surface_mismatch(
    status: VisitStatus,
    other_surface: UUID,
    now: datetime,
) -> None:
    """A command surface_id differing from state.surface_id raises surface_mismatch."""
    state = make_visit(status)
    assume(other_surface != state.surface_id)
    with pytest.raises(VisitCannotTakeControlError) as exc:
        decide(
            state=state,
            command=_command(surface_id=other_surface),
            context=_context(),
            now=now,
        )
    assert exc.value.reason == "surface_mismatch"


@pytest.mark.unit
@given(status=_PERMITTED, now=aware_datetimes())
def test_take_clean_path_emits_single_event_with_injected_fields(
    status: VisitStatus,
    now: datetime,
) -> None:
    """A permitted status with a free Surface emits one event with injected fields."""
    state = make_visit(status)
    events = decide(
        state=state,
        command=_command(),
        context=_context(),
        now=now,
    )
    assert len(events) == 1
    [event] = events
    assert isinstance(event, VisitSurfaceControlTaken)
    assert event.visit_id == state.id
    assert event.surface_id == SURFACE_ID
    assert event.occurred_at == now


@pytest.mark.unit
@given(status=_PERMITTED, now=aware_datetimes())
def test_take_is_pure_same_input_same_output(
    status: VisitStatus,
    now: datetime,
) -> None:
    """Two calls with identical args return equal results (no clock/id leakage)."""
    state = make_visit(status)
    command = _command()
    context = _context()
    first = decide(state=state, command=command, context=context, now=now)
    second = decide(state=state, command=command, context=context, now=now)
    assert first == second
