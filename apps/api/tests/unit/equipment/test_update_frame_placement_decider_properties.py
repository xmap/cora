"""Property-based tests for `update_frame_placement.decide` (Equipment BC).

Complements the example-based `test_update_frame_placement_decider.py`
with universal claims across generated inputs. The decider is a pure
in-place placement mutation guarded by a source-state partition

    (state, command, now) -> list[FramePlacementUpdated]

Load-bearing properties:

  - state=None always raises `FrameNotFoundError` carrying command.frame_id.
  - The source-state partition is total over `FrameStatus`: only
    `Active` is updatable; every other status raises
    `FrameCannotUpdateError` carrying state.id and naming the current
    status, so a future status value cannot silently fall through.
  - A child Active frame whose new_placement differs emits exactly one
    `FramePlacementUpdated` (frame_id=state.id, occurred_at=now).
  - The emitted event's frame_id is `state.id`, never `command.frame_id`.
  - No-op idempotent contract: new_placement == current_placement
    returns `[]`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.equipment.aggregates._placement import (
    Placement,
    ReferenceSurface,
    UnitSystem,
)
from cora.equipment.aggregates.frame import (
    Frame,
    FrameCannotUpdateError,
    FrameNotFoundError,
    FramePlacementUpdated,
    FrameStatus,
)
from cora.equipment.aggregates.frame.state import FrameName
from cora.equipment.features import update_frame_placement
from cora.equipment.features.update_frame_placement import UpdateFramePlacement
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_UPDATABLE_SOURCES = (FrameStatus.ACTIVE,)
_DISALLOWED_SOURCES = tuple(s for s in FrameStatus if s not in frozenset(_UPDATABLE_SOURCES))


def _placement(parent: UUID, *, z: float = 259313.0) -> Placement:
    return Placement(
        x=0.0,
        y=0.0,
        z=z,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame_id=parent,
        reference_surface=ReferenceSurface.SHIELDING_FACE,
        tol_x=0.25,
        tol_y=0.25,
        tol_z=5.0,
        tol_rx=0.0,
        tol_ry=0.0,
        tol_rz=0.0,
        units=UnitSystem.SI_MM_RAD,
    )


def _frame(*, frame_id: UUID, parent: UUID, status: FrameStatus = FrameStatus.ACTIVE) -> Frame:
    return Frame(
        id=frame_id,
        name=FrameName("centerline_5p1_mrad"),
        parent_id=parent,
        placement=_placement(parent),
        status=status,
    )


@pytest.mark.unit
@given(frame_id=st.uuids(), parent=st.uuids(), now=aware_datetimes())
def test_update_with_none_state_always_raises_not_found(
    frame_id: UUID,
    parent: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `FrameNotFoundError` carrying command.frame_id."""
    with pytest.raises(FrameNotFoundError) as exc:
        update_frame_placement.decide(
            state=None,
            command=UpdateFramePlacement(
                frame_id=frame_id,
                new_placement=_placement(parent),
                survey=None,
            ),
            now=now,
        )
    assert exc.value.frame_id == frame_id


@pytest.mark.unit
@given(frame_id=st.uuids(), parent=st.uuids(), now=aware_datetimes())
def test_update_from_active_child_emits_single_event(
    frame_id: UUID,
    parent: UUID,
    now: datetime,
) -> None:
    """Active is the only updatable source; a changed placement emits one event."""
    frame = _frame(frame_id=frame_id, parent=parent)
    new_placement = _placement(parent, z=259999.0)
    events = update_frame_placement.decide(
        state=frame,
        command=UpdateFramePlacement(frame_id=frame_id, new_placement=new_placement, survey=None),
        now=now,
    )
    assert events == [
        FramePlacementUpdated(
            frame_id=frame_id,
            new_placement=new_placement,
            survey=None,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    frame_id=st.uuids(),
    parent=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_update_from_disallowed_source_always_raises_cannot_update(
    frame_id: UUID,
    parent: UUID,
    source: FrameStatus,
    now: datetime,
) -> None:
    """Any source other than Active raises, carrying state.id and the current status."""
    frame = _frame(frame_id=frame_id, parent=parent, status=source)
    with pytest.raises(FrameCannotUpdateError) as exc:
        update_frame_placement.decide(
            state=frame,
            command=UpdateFramePlacement(
                frame_id=frame_id,
                new_placement=_placement(parent, z=259999.0),
                survey=None,
            ),
            now=now,
        )
    assert exc.value.frame_id == frame_id
    assert source.value in exc.value.reason


@pytest.mark.unit
@given(
    state_frame_id=st.uuids(),
    command_frame_id=st.uuids(),
    parent=st.uuids(),
    now=aware_datetimes(),
)
def test_update_emits_event_with_state_id_not_command_frame_id(
    state_frame_id: UUID,
    command_frame_id: UUID,
    parent: UUID,
    now: datetime,
) -> None:
    """The emitted event's frame_id is state.id, not command.frame_id."""
    assume(state_frame_id != command_frame_id)
    frame = _frame(frame_id=state_frame_id, parent=parent)
    events = update_frame_placement.decide(
        state=frame,
        command=UpdateFramePlacement(
            frame_id=command_frame_id,
            new_placement=_placement(parent, z=259999.0),
            survey=None,
        ),
        now=now,
    )
    assert events[0].frame_id == state_frame_id


@pytest.mark.unit
@given(frame_id=st.uuids(), parent=st.uuids(), now=aware_datetimes())
def test_update_with_unchanged_placement_returns_no_op(
    frame_id: UUID,
    parent: UUID,
    now: datetime,
) -> None:
    """new_placement == current_placement returns an empty event list."""
    frame = _frame(frame_id=frame_id, parent=parent)
    same_placement = _placement(parent)
    assert frame.placement == same_placement
    events = update_frame_placement.decide(
        state=frame,
        command=UpdateFramePlacement(frame_id=frame_id, new_placement=same_placement, survey=None),
        now=now,
    )
    assert events == []


@pytest.mark.unit
@given(frame_id=st.uuids(), parent=st.uuids(), now=aware_datetimes())
def test_update_is_pure_same_input_returns_equal_output(
    frame_id: UUID,
    parent: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    frame = _frame(frame_id=frame_id, parent=parent)
    command = UpdateFramePlacement(
        frame_id=frame_id,
        new_placement=_placement(parent, z=259999.0),
        survey=None,
    )
    first = update_frame_placement.decide(state=frame, command=command, now=now)
    second = update_frame_placement.decide(state=frame, command=command, now=now)
    assert first == second
