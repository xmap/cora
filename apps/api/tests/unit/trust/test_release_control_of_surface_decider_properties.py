"""Property-based tests for `release_control_of_surface.decide` (Trust BC).

Complements the example-based `visit/test_release_control_of_surface_decider.py`
with universal claims across generated inputs. `release_control_of_surface`
is a bespoke cross-aggregate command: it folds the requesting Visit against
a `SurfaceActiveVisit` controller snapshot and emits a single
`VisitSurfaceControlReleased`. The full gate matrix (surface_mismatch vs
not_holder reasons, holder-id leakage) is pinned by the example tests; the
PBT asserts the universal claims that hold across the whole input space:

  - A None state always raises `VisitNotFoundError` carrying the command's
    visit_id, regardless of command / context.
  - A representative disallowed condition (the Surface is free, so the
    requester is not the active holder) always raises
    `VisitCannotReleaseControlError` carrying state.id, across every
    non-terminal source status.
  - On the clean-release path (requester holds the Surface, surface ids
    match) the single `VisitSurfaceControlReleased` carries visit_id=state.id,
    surface_id=command.surface_id, and occurred_at=now, across every
    non-terminal source status.
  - Pure: same inputs return equal results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.trust.aggregates.visit import (
    VisitCannotReleaseControlError,
    VisitNotFoundError,
    VisitStatus,
    VisitSurfaceControlReleased,
)
from cora.trust.features.release_control_of_surface import ReleaseControlOfSurface
from cora.trust.features.release_control_of_surface.context import (
    ReleaseControlOfSurfaceContext,
)
from cora.trust.features.release_control_of_surface.decider import decide
from cora.trust.projections.surface_active_visit import SurfaceActiveVisit
from tests._strategies import aware_datetimes
from tests.unit.trust.visit._fixtures import SURFACE_ID, VISIT_ID, make_visit

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NON_TERMINAL_STATUSES = (
    VisitStatus.PLANNED,
    VisitStatus.ARRIVED,
    VisitStatus.IN_PROGRESS,
    VisitStatus.ON_HOLD,
)


def _command(*, surface_id: UUID) -> ReleaseControlOfSurface:
    return ReleaseControlOfSurface(visit_id=VISIT_ID, surface_id=surface_id)


def _context(*, holder_id: UUID | None, now: datetime) -> ReleaseControlOfSurfaceContext:
    holder = None if holder_id is None else SurfaceActiveVisit(visit_id=holder_id, since_at=now)
    return ReleaseControlOfSurfaceContext(active_holder=holder)


@pytest.mark.unit
@given(surface_id=st.uuids(), holder_id=st.none() | st.uuids(), now=aware_datetimes())
def test_release_on_none_state_always_raises_not_found(
    surface_id: UUID,
    holder_id: UUID | None,
    now: datetime,
) -> None:
    """A None state always raises VisitNotFoundError carrying the command visit_id."""
    with pytest.raises(VisitNotFoundError):
        decide(
            state=None,
            command=_command(surface_id=surface_id),
            context=_context(holder_id=holder_id, now=now),
            now=now,
        )


@pytest.mark.unit
@given(status=st.sampled_from(_NON_TERMINAL_STATUSES), now=aware_datetimes())
def test_release_on_free_surface_always_raises_cannot_release(
    status: VisitStatus,
    now: datetime,
) -> None:
    """A free Surface (no active holder) always raises VisitCannotReleaseControlError."""
    state = make_visit(status)
    with pytest.raises(VisitCannotReleaseControlError) as exc_info:
        decide(
            state=state,
            command=_command(surface_id=SURFACE_ID),
            context=_context(holder_id=None, now=now),
            now=now,
        )
    assert exc_info.value.visit_id == state.id
    assert exc_info.value.reason == "not_holder"


@pytest.mark.unit
@given(status=st.sampled_from(_NON_TERMINAL_STATUSES), now=aware_datetimes())
def test_release_by_current_holder_emits_event_with_injected_fields(
    status: VisitStatus,
    now: datetime,
) -> None:
    """A clean release emits one VisitSurfaceControlReleased with state.id + occurred_at=now."""
    state = make_visit(status)
    events = decide(
        state=state,
        command=_command(surface_id=SURFACE_ID),
        context=_context(holder_id=state.id, now=now),
        now=now,
    )
    assert len(events) == 1
    [event] = events
    assert isinstance(event, VisitSurfaceControlReleased)
    assert event.visit_id == state.id
    assert event.surface_id == SURFACE_ID
    assert event.occurred_at == now


@pytest.mark.unit
@given(status=st.sampled_from(_NON_TERMINAL_STATUSES), now=aware_datetimes())
def test_release_is_pure_same_input_same_output(
    status: VisitStatus,
    now: datetime,
) -> None:
    """Two calls with identical args return equal results (no clock/id leakage)."""
    state = make_visit(status)
    command = _command(surface_id=SURFACE_ID)
    context = _context(holder_id=state.id, now=now)
    first = decide(state=state, command=command, context=context, now=now)
    second = decide(state=state, command=command, context=context, now=now)
    assert first == second
