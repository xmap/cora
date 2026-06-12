"""Property-based tests for `decommission_mount.decide` (Equipment BC).

Complements the example-based `test_decommission_mount_decider.py` with
universal claims across generated inputs. This is a cross-aggregate
decider: it reads a `DecommissionMountContext` (active child mount ids
loaded from the mount_children projection) alongside the Mount state.

    (state, command, context, now) -> list[MountDecommissioned]

Load-bearing properties:

  - An Active, vacant, childless Mount emits exactly one
    MountDecommissioned keyed on state.id, carrying command.reason and
    occurred_at=now.
  - A None state always raises MountNotFoundError carrying the
    command's mount_id (existence guard).
  - A Decommissioned Mount always raises MountCannotDecommissionError
    carrying state.id (re-decommission rejected).
  - A Mount with an installed Asset always raises
    MountHasAssetInstalledError carrying the occupant id (slot must be
    vacant; no implicit eviction).
  - A Mount with active children always raises
    MountHasActiveChildrenError carrying the child ids (no
    cascade-decommission).
  - Pure: same inputs return equal results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates._placement import (
    Placement,
    ReferenceSurface,
    UnitSystem,
)
from cora.equipment.aggregates.mount import (
    Mount,
    MountCannotDecommissionError,
    MountDecommissioned,
    MountHasActiveChildrenError,
    MountHasAssetInstalledError,
    MountNotFoundError,
    MountStatus,
)
from cora.equipment.aggregates.mount.state import SlotCode
from cora.equipment.features import decommission_mount
from cora.equipment.features.decommission_mount import (
    DecommissionMount,
    DecommissionMountContext,
)
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime


def _placement(parent_frame_id: UUID) -> Placement:
    return Placement(
        x=0.0,
        y=0.0,
        z=0.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame_id=parent_frame_id,  # type: ignore[arg-type]
        reference_surface=ReferenceSurface.SHIELDING_FACE,
        tol_x=0.0,
        tol_y=0.0,
        tol_z=0.0,
        tol_rx=0.0,
        tol_ry=0.0,
        tol_rz=0.0,
        units=UnitSystem.SI_MM_RAD,
    )


def _mount(
    *,
    mount_id: UUID,
    status: MountStatus = MountStatus.ACTIVE,
    installed_asset_id: UUID | None = None,
) -> Mount:
    return Mount(
        id=mount_id,
        slot_code=SlotCode("02-BM-A-K-01"),
        parent_id=None,
        placement=_placement(UUID(int=7)),
        drawing=None,
        installed_asset_id=installed_asset_id,  # type: ignore[arg-type]
        status=status,
    )


@pytest.mark.unit
@given(
    mount_id=st.uuids(),
    reason=printable_ascii_text(max_size=32),
    now=aware_datetimes(),
)
def test_decommission_mount_active_vacant_childless_emits_decommissioned(
    mount_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """An Active, vacant, childless Mount emits one MountDecommissioned with id+reason+now."""
    mount = _mount(mount_id=mount_id)
    events = decommission_mount.decide(
        state=mount,
        command=DecommissionMount(mount_id=mount_id, reason=reason),
        context=DecommissionMountContext(active_child_mount_ids=()),
        now=now,
    )
    assert events == [MountDecommissioned(mount_id=mount_id, reason=reason, occurred_at=now)]


@pytest.mark.unit
@given(
    mount_id=st.uuids(),
    reason=printable_ascii_text(max_size=32),
    now=aware_datetimes(),
)
def test_decommission_mount_missing_state_raises_not_found(
    mount_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """A None state raises MountNotFoundError carrying the command's mount_id."""
    with pytest.raises(MountNotFoundError) as exc:
        decommission_mount.decide(
            state=None,
            command=DecommissionMount(mount_id=mount_id, reason=reason),
            context=DecommissionMountContext(active_child_mount_ids=()),
            now=now,
        )
    assert exc.value.mount_id == mount_id


@pytest.mark.unit
@given(
    mount_id=st.uuids(),
    reason=printable_ascii_text(max_size=32),
    now=aware_datetimes(),
)
def test_decommission_mount_already_decommissioned_raises_cannot_decommission(
    mount_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """A Decommissioned Mount raises MountCannotDecommissionError carrying state.id."""
    mount = _mount(mount_id=mount_id, status=MountStatus.DECOMMISSIONED)
    with pytest.raises(MountCannotDecommissionError) as exc:
        decommission_mount.decide(
            state=mount,
            command=DecommissionMount(mount_id=mount_id, reason=reason),
            context=DecommissionMountContext(active_child_mount_ids=()),
            now=now,
        )
    assert exc.value.mount_id == mount_id
    assert MountStatus.DECOMMISSIONED.value in exc.value.reason


@pytest.mark.unit
@given(
    mount_id=st.uuids(),
    occupant_id=st.uuids(),
    reason=printable_ascii_text(max_size=32),
    now=aware_datetimes(),
)
def test_decommission_mount_occupied_slot_raises_has_asset_installed(
    mount_id: UUID,
    occupant_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """A Mount with an installed Asset raises MountHasAssetInstalledError with the occupant id."""
    mount = _mount(mount_id=mount_id, installed_asset_id=occupant_id)
    with pytest.raises(MountHasAssetInstalledError) as exc:
        decommission_mount.decide(
            state=mount,
            command=DecommissionMount(mount_id=mount_id, reason=reason),
            context=DecommissionMountContext(active_child_mount_ids=()),
            now=now,
        )
    assert exc.value.mount_id == mount_id
    assert exc.value.installed_asset_id == occupant_id


@pytest.mark.unit
@given(
    mount_id=st.uuids(),
    child_ids=st.lists(st.uuids(), min_size=1, max_size=4).map(tuple),
    reason=printable_ascii_text(max_size=32),
    now=aware_datetimes(),
)
def test_decommission_mount_with_active_children_raises_has_active_children(
    mount_id: UUID,
    child_ids: tuple[UUID, ...],
    reason: str,
    now: datetime,
) -> None:
    """A Mount with active children raises MountHasActiveChildrenError carrying the child ids."""
    mount = _mount(mount_id=mount_id)
    with pytest.raises(MountHasActiveChildrenError) as exc:
        decommission_mount.decide(
            state=mount,
            command=DecommissionMount(mount_id=mount_id, reason=reason),
            context=DecommissionMountContext(active_child_mount_ids=child_ids),
            now=now,
        )
    assert exc.value.mount_id == mount_id
    assert exc.value.active_child_mount_ids == child_ids


@pytest.mark.unit
@given(
    mount_id=st.uuids(),
    reason=printable_ascii_text(max_size=32),
    now=aware_datetimes(),
)
def test_decommission_mount_is_pure_same_input_same_output(
    mount_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal results (no clock leakage)."""
    mount = _mount(mount_id=mount_id)
    command = DecommissionMount(mount_id=mount_id, reason=reason)
    context = DecommissionMountContext(active_child_mount_ids=())
    first = decommission_mount.decide(state=mount, command=command, context=context, now=now)
    second = decommission_mount.decide(state=mount, command=command, context=context, now=now)
    assert first == second
