"""Property-based tests for `update_mount_placement.decide` (Equipment BC).

Complements the example-based `test_update_mount_placement_decider.py`
with universal claims across generated inputs. The decider is a pure
in-place-mutation slice on the Mount aggregate

    (state, command, now) -> list[MountPlacementUpdated]

Load-bearing properties:

  - state=None always raises `MountNotFoundError` carrying command.mount_id.
  - The source-state partition is total over `MountStatus`: only `Active`
    can emit; every other status raises `MountCannotUpdateError` whose
    `reason` names the current status `.value`, so a future status value
    cannot silently fall through.
  - From `Active`, a genuine placement change (same parent_frame_id, but
    a differing field) emits exactly one `MountPlacementUpdated` carrying
    occurred_at=now.
  - The emitted event's mount_id is `state.id`, never `command.mount_id`.
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
from cora.equipment.aggregates.mount import (
    Mount,
    MountCannotUpdateError,
    MountNotFoundError,
    MountPlacementUpdated,
    MountStatus,
)
from cora.equipment.aggregates.mount.state import SlotCode
from cora.equipment.features import update_mount_placement
from cora.equipment.features.update_mount_placement import UpdateMountPlacement
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_UPDATABLE_SOURCES = (MountStatus.ACTIVE,)
_DISALLOWED_SOURCES = tuple(s for s in MountStatus if s not in frozenset(_UPDATABLE_SOURCES))


def _placement(parent_frame_id: object, *, z: float = 259313.0) -> Placement:
    return Placement(
        x=0.0,
        y=0.0,
        z=z,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame_id=parent_frame_id,  # type: ignore[arg-type]
        reference_surface=ReferenceSurface.SHIELDING_FACE,
        tol_x=0.25,
        tol_y=0.25,
        tol_z=5.0,
        tol_rx=0.0,
        tol_ry=0.0,
        tol_rz=0.0,
        units=UnitSystem.SI_MM_RAD,
    )


def _mount(*, mount_id: UUID, frame_id: object, status: MountStatus) -> Mount:
    return Mount(
        id=mount_id,
        slot_code=SlotCode("02-BM-A-K-01"),
        parent_id=None,
        placement=_placement(frame_id),
        drawing=None,
        installed_asset_id=None,
        status=status,
    )


@pytest.mark.unit
@given(mount_id=st.uuids(), frame_id=st.uuids(), now=aware_datetimes())
def test_update_placement_with_none_state_always_raises_not_found(
    mount_id: UUID,
    frame_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `MountNotFoundError` carrying command.mount_id."""
    with pytest.raises(MountNotFoundError) as exc:
        update_mount_placement.decide(
            state=None,
            command=UpdateMountPlacement(
                mount_id=mount_id,
                new_placement=_placement(frame_id),
                survey=None,
            ),
            now=now,
        )
    assert exc.value.mount_id == mount_id


@pytest.mark.unit
@given(mount_id=st.uuids(), frame_id=st.uuids(), now=aware_datetimes())
def test_update_placement_from_active_emits_single_event(
    mount_id: UUID,
    frame_id: UUID,
    now: datetime,
) -> None:
    """Active is the only updatable source; a genuine change emits one event."""
    mount = _mount(mount_id=mount_id, frame_id=frame_id, status=MountStatus.ACTIVE)
    changed = _placement(frame_id, z=259999.0)
    events = update_mount_placement.decide(
        state=mount,
        command=UpdateMountPlacement(
            mount_id=mount_id,
            new_placement=changed,
            survey=None,
        ),
        now=now,
    )
    assert events == [
        MountPlacementUpdated(
            mount_id=mount_id,
            new_placement=changed,
            survey=None,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    mount_id=st.uuids(),
    frame_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_update_placement_from_disallowed_source_always_raises_cannot_update(
    mount_id: UUID,
    frame_id: UUID,
    source: MountStatus,
    now: datetime,
) -> None:
    """Any source other than Active raises, the reason naming current status."""
    mount = _mount(mount_id=mount_id, frame_id=frame_id, status=source)
    with pytest.raises(MountCannotUpdateError) as exc:
        update_mount_placement.decide(
            state=mount,
            command=UpdateMountPlacement(
                mount_id=mount_id,
                new_placement=_placement(frame_id, z=999.0),
                survey=None,
            ),
            now=now,
        )
    assert exc.value.mount_id == mount_id
    assert source.value in exc.value.reason


@pytest.mark.unit
@given(
    state_mount_id=st.uuids(),
    command_mount_id=st.uuids(),
    frame_id=st.uuids(),
    now=aware_datetimes(),
)
def test_update_placement_emits_event_with_state_id_not_command_mount_id(
    state_mount_id: UUID,
    command_mount_id: UUID,
    frame_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's mount_id is state.id, not command.mount_id."""
    assume(state_mount_id != command_mount_id)
    mount = _mount(mount_id=state_mount_id, frame_id=frame_id, status=MountStatus.ACTIVE)
    events = update_mount_placement.decide(
        state=mount,
        command=UpdateMountPlacement(
            mount_id=command_mount_id,
            new_placement=_placement(frame_id, z=259999.0),
            survey=None,
        ),
        now=now,
    )
    assert events[0].mount_id == state_mount_id


@pytest.mark.unit
@given(mount_id=st.uuids(), frame_id=st.uuids(), now=aware_datetimes())
def test_update_placement_is_pure_same_input_same_output(
    mount_id: UUID,
    frame_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    mount = _mount(mount_id=mount_id, frame_id=frame_id, status=MountStatus.ACTIVE)
    command = UpdateMountPlacement(
        mount_id=mount_id,
        new_placement=_placement(frame_id, z=259999.0),
        survey=None,
    )
    first = update_mount_placement.decide(state=mount, command=command, now=now)
    second = update_mount_placement.decide(state=mount, command=command, now=now)
    assert first == second
