"""Property-based tests for `install_asset.decide` (Equipment BC).

Complements the example-based `test_install_asset_decider.py` with
universal claims across generated inputs. This is a cross-aggregate
decider: the handler loads an `InstallAssetContext` (Asset lifecycle +
back-lookup) before calling the pure decider.

    (state, command, context, now) -> list[MountAssetInstalled]

Load-bearing properties:

  - A None state always raises `MountNotFoundError` carrying the
    command's mount_id (existence guard).
  - A vacant Active Mount + an Active Asset with no cross-Mount
    collision emits exactly one `MountAssetInstalled` keyed on
    state.id with occurred_at=now.
  - An occupied Mount (slot holds a different Asset) always raises
    `MountAlreadyOccupiedError` (representative disallowed condition).
  - Pure: same inputs return equal results.

The full guard matrix (status, idempotency, lifecycle-None,
not-installable, elsewhere-collision, same-Mount back-lookup) is
pinned by the example test and not duplicated here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

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
    MountAlreadyOccupiedError,
    MountAssetInstalled,
    MountNotFoundError,
    MountStatus,
)
from cora.equipment.aggregates.mount.state import SlotCode
from cora.equipment.features import install_asset
from cora.equipment.features.install_asset import InstallAsset, InstallAssetContext
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


def _placement(parent_frame_id: object) -> Placement:
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
    installed_asset_id: object = None,
) -> Mount:
    return Mount(
        id=mount_id,
        slot_code=SlotCode("02-BM-A-K-01"),
        parent_id=None,
        placement=_placement(uuid4()),
        drawing=None,
        installed_asset_id=installed_asset_id,  # type: ignore[arg-type]
        status=status,
    )


def _ctx(
    *,
    asset_lifecycle: str | None = "Active",
    currently_installed_at_mount_id: object = None,
) -> InstallAssetContext:
    return InstallAssetContext(
        asset_lifecycle=asset_lifecycle,
        currently_installed_at_mount_id=currently_installed_at_mount_id,  # type: ignore[arg-type]
    )


@pytest.mark.unit
@given(mount_id=st.uuids(), asset_id=st.uuids(), now=aware_datetimes())
def test_install_asset_none_state_raises_mount_not_found(
    mount_id: UUID,
    asset_id: UUID,
    now: datetime,
) -> None:
    """A None state raises MountNotFoundError carrying the command mount_id."""
    with pytest.raises(MountNotFoundError) as exc:
        install_asset.decide(
            state=None,
            command=InstallAsset(mount_id=mount_id, asset_id=asset_id),
            context=_ctx(),
            now=now,
        )
    assert exc.value.mount_id == mount_id


@pytest.mark.unit
@given(mount_id=st.uuids(), asset_id=st.uuids(), now=aware_datetimes())
def test_install_asset_vacant_active_mount_emits_installed_event(
    mount_id: UUID,
    asset_id: UUID,
    now: datetime,
) -> None:
    """A vacant Active Mount + Active Asset emits one MountAssetInstalled keyed on state.id."""
    mount = _mount(mount_id=mount_id)
    events = install_asset.decide(
        state=mount,
        command=InstallAsset(mount_id=mount_id, asset_id=asset_id),
        context=_ctx(),
        now=now,
    )
    assert events == [
        MountAssetInstalled(
            mount_id=mount_id,
            asset_id=asset_id,
            previously_installed_asset_id=None,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(mount_id=st.uuids(), asset_id=st.uuids(), occupant_id=st.uuids(), now=aware_datetimes())
def test_install_asset_occupied_mount_raises_already_occupied(
    mount_id: UUID,
    asset_id: UUID,
    occupant_id: UUID,
    now: datetime,
) -> None:
    """A slot holding a different Asset raises MountAlreadyOccupiedError with all three ids."""
    assume(occupant_id != asset_id)
    mount = _mount(mount_id=mount_id, installed_asset_id=occupant_id)
    with pytest.raises(MountAlreadyOccupiedError) as exc:
        install_asset.decide(
            state=mount,
            command=InstallAsset(mount_id=mount_id, asset_id=asset_id),
            context=_ctx(),
            now=now,
        )
    assert exc.value.mount_id == mount_id
    assert exc.value.installed_asset_id == occupant_id
    assert exc.value.attempted_asset_id == asset_id


@pytest.mark.unit
@given(mount_id=st.uuids(), asset_id=st.uuids(), now=aware_datetimes())
def test_install_asset_is_pure_same_input_same_output(
    mount_id: UUID,
    asset_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal results (no clock leakage)."""
    mount = _mount(mount_id=mount_id)
    command = InstallAsset(mount_id=mount_id, asset_id=asset_id)
    first = install_asset.decide(state=mount, command=command, context=_ctx(), now=now)
    second = install_asset.decide(state=mount, command=command, context=_ctx(), now=now)
    assert first == second
