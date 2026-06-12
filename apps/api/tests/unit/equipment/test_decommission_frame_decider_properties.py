"""Property-based tests for `decommission_frame.decide` (Equipment BC).

Complements the example-based `test_decommission_frame_decider.py` with
universal claims across generated inputs. This is a cross-aggregate
decider: it takes a `DecommissionFrameContext` snapshot of the frame's
active consumers (loaded from the `frame_consumers` projection by the
handler) alongside the Frame state.

    (state, command, context, now) -> list[FrameDecommissioned]

Load-bearing properties:

  - An Active frame with no active consumers emits exactly one
    FrameDecommissioned keyed on state.id, carrying the command reason
    and occurred_at=now.
  - A None state always raises FrameNotFoundError carrying the command
    frame_id.
  - A non-Active frame always raises FrameCannotDecommissionError
    carrying state.id and naming the offending status.
  - A frame with a non-empty context.active_consumer_ids always raises
    FrameInUseError carrying state.id and the offending consumer ids.
  - Pure: same inputs return equal results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates._placement import (
    Placement,
    ReferenceSurface,
    UnitSystem,
)
from cora.equipment.aggregates.frame import (
    Frame,
    FrameCannotDecommissionError,
    FrameDecommissioned,
    FrameInUseError,
    FrameNotFoundError,
    FrameStatus,
)
from cora.equipment.aggregates.frame.state import FrameName
from cora.equipment.features import decommission_frame
from cora.equipment.features.decommission_frame import (
    DecommissionFrame,
    DecommissionFrameContext,
)
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NON_ACTIVE_SOURCES = (FrameStatus.DECOMMISSIONED,)


def _placement(parent: object) -> Placement:
    return Placement(
        x=0.0,
        y=0.0,
        z=259313.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame_id=parent,  # type: ignore[arg-type]
        reference_surface=ReferenceSurface.SHIELDING_FACE,
        tol_x=0.25,
        tol_y=0.25,
        tol_z=5.0,
        tol_rx=0.0,
        tol_ry=0.0,
        tol_rz=0.0,
        units=UnitSystem.SI_MM_RAD,
    )


def _frame(*, frame_id: UUID, status: FrameStatus = FrameStatus.ACTIVE) -> Frame:
    parent = uuid4()
    return Frame(
        id=frame_id,
        name=FrameName("centerline_5p1_mrad"),
        parent_id=parent,
        placement=_placement(parent),
        status=status,
    )


@pytest.mark.unit
@given(
    frame_id=st.uuids(),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_decommission_frame_active_no_consumers_emits_decommissioned_with_id_and_now(
    frame_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """An Active frame with no consumers emits one FrameDecommissioned keyed on state.id."""
    frame = _frame(frame_id=frame_id)
    events = decommission_frame.decide(
        state=frame,
        command=DecommissionFrame(frame_id=frame_id, reason=reason),
        context=DecommissionFrameContext(active_consumer_ids=()),
        now=now,
    )
    assert events == [FrameDecommissioned(frame_id=frame_id, reason=reason, occurred_at=now)]


@pytest.mark.unit
@given(
    frame_id=st.uuids(),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_decommission_frame_none_state_always_raises_not_found(
    frame_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """A None state raises FrameNotFoundError carrying the command frame_id."""
    with pytest.raises(FrameNotFoundError) as exc:
        decommission_frame.decide(
            state=None,
            command=DecommissionFrame(frame_id=frame_id, reason=reason),
            context=DecommissionFrameContext(active_consumer_ids=()),
            now=now,
        )
    assert exc.value.frame_id == frame_id


@pytest.mark.unit
@given(
    frame_id=st.uuids(),
    reason=printable_ascii_text(max_size=64),
    source=st.sampled_from(_NON_ACTIVE_SOURCES),
    now=aware_datetimes(),
)
def test_decommission_frame_non_active_status_always_raises_cannot_decommission(
    frame_id: UUID,
    reason: str,
    source: FrameStatus,
    now: datetime,
) -> None:
    """A non-Active frame raises FrameCannotDecommissionError naming the status."""
    frame = _frame(frame_id=frame_id, status=source)
    with pytest.raises(FrameCannotDecommissionError) as exc:
        decommission_frame.decide(
            state=frame,
            command=DecommissionFrame(frame_id=frame_id, reason=reason),
            context=DecommissionFrameContext(active_consumer_ids=()),
            now=now,
        )
    assert exc.value.frame_id == frame_id
    assert source.value in exc.value.reason


@pytest.mark.unit
@given(
    frame_id=st.uuids(),
    reason=printable_ascii_text(max_size=64),
    consumer_ids=st.lists(st.uuids(), min_size=1, max_size=5).map(tuple),
    now=aware_datetimes(),
)
def test_decommission_frame_active_consumers_always_raises_in_use_with_consumer_ids(
    frame_id: UUID,
    reason: str,
    consumer_ids: tuple[UUID, ...],
    now: datetime,
) -> None:
    """A non-empty active_consumer_ids raises FrameInUseError carrying the offenders."""
    frame = _frame(frame_id=frame_id)
    with pytest.raises(FrameInUseError) as exc:
        decommission_frame.decide(
            state=frame,
            command=DecommissionFrame(frame_id=frame_id, reason=reason),
            context=DecommissionFrameContext(active_consumer_ids=consumer_ids),
            now=now,
        )
    assert exc.value.frame_id == frame_id
    assert exc.value.consumer_ids == consumer_ids


@pytest.mark.unit
@given(
    frame_id=st.uuids(),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_decommission_frame_is_pure_same_input_returns_equal_output(
    frame_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal results (no clock leakage)."""
    frame = _frame(frame_id=frame_id)
    command = DecommissionFrame(frame_id=frame_id, reason=reason)
    context = DecommissionFrameContext(active_consumer_ids=())
    first = decommission_frame.decide(state=frame, command=command, context=context, now=now)
    second = decommission_frame.decide(state=frame, command=command, context=context, now=now)
    assert first == second
