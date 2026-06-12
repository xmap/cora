"""Property-based tests for `uninstall_asset.decide` (Equipment BC).

Complements the example-based `test_uninstall_asset_decider.py` with
universal claims across generated inputs. This is a cross-aggregate
decider: it takes an `UninstallAssetContext` carrying the installed
Asset's Fixture back-reference peeked from the Asset stream.

    (state, command, context, now) -> list[MountAssetUninstalled]

Load-bearing properties:

  - A None state always raises `MountNotFoundError` carrying the
    command's mount_id (existence guard).
  - A Decommissioned Mount always raises `MountCannotUpdateError`
    carrying the current status in its reason.
  - A vacant slot always raises `MountIsEmptyError`, and this
    precedence holds even when the context carries a fixture_id.
  - An Active, occupied Mount whose installed Asset still carries a
    Fixture back-reference always raises `MountHasFixtureBoundAssetError`
    keyed on the mount, occupant, and fixture ids.
  - An Active, occupied Mount with an empty context emits exactly one
    `MountAssetUninstalled` keyed on state.id and state.installed_asset_id
    with occurred_at=now.
  - Pure: same inputs return equal results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

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
    MountAssetUninstalled,
    MountCannotUpdateError,
    MountHasFixtureBoundAssetError,
    MountIsEmptyError,
    MountNotFoundError,
    MountStatus,
)
from cora.equipment.aggregates.mount.state import SlotCode
from cora.equipment.features import uninstall_asset
from cora.equipment.features.uninstall_asset import (
    UninstallAsset,
    UninstallAssetContext,
)
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_EMPTY_CONTEXT = UninstallAssetContext(installed_asset_fixture_id=None)


def _placement(parent_frame_id: UUID) -> Placement:
    return Placement(
        x=0.0,
        y=0.0,
        z=0.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame_id=parent_frame_id,
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
        placement=_placement(uuid4()),
        drawing=None,
        installed_asset_id=installed_asset_id,
        status=status,
    )


@pytest.mark.unit
@given(mount_id=st.uuids(), reason=printable_ascii_text(max_size=32), now=aware_datetimes())
def test_uninstall_none_state_always_raises_mount_not_found(
    mount_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """A None state raises MountNotFoundError carrying the command's mount_id."""
    with pytest.raises(MountNotFoundError) as exc:
        uninstall_asset.decide(
            state=None,
            command=UninstallAsset(mount_id=mount_id, reason=reason),
            context=_EMPTY_CONTEXT,
            now=now,
        )
    assert exc.value.mount_id == mount_id


@pytest.mark.unit
@given(
    mount_id=st.uuids(),
    occupant=st.uuids(),
    reason=printable_ascii_text(max_size=32),
    now=aware_datetimes(),
)
def test_uninstall_decommissioned_mount_always_raises_cannot_update(
    mount_id: UUID,
    occupant: UUID,
    reason: str,
    now: datetime,
) -> None:
    """A Decommissioned Mount raises MountCannotUpdateError carrying its status."""
    mount = _mount(
        mount_id=mount_id,
        status=MountStatus.DECOMMISSIONED,
        installed_asset_id=occupant,
    )
    with pytest.raises(MountCannotUpdateError) as exc:
        uninstall_asset.decide(
            state=mount,
            command=UninstallAsset(mount_id=mount_id, reason=reason),
            context=_EMPTY_CONTEXT,
            now=now,
        )
    assert MountStatus.DECOMMISSIONED.value in exc.value.reason


@pytest.mark.unit
@given(mount_id=st.uuids(), reason=printable_ascii_text(max_size=32), now=aware_datetimes())
def test_uninstall_vacant_slot_always_raises_is_empty(
    mount_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """An Active Mount with a vacant slot raises MountIsEmptyError."""
    mount = _mount(mount_id=mount_id, installed_asset_id=None)
    with pytest.raises(MountIsEmptyError) as exc:
        uninstall_asset.decide(
            state=mount,
            command=UninstallAsset(mount_id=mount_id, reason=reason),
            context=_EMPTY_CONTEXT,
            now=now,
        )
    assert exc.value.mount_id == mount_id


@pytest.mark.unit
@given(
    mount_id=st.uuids(),
    fixture_id=st.uuids(),
    reason=printable_ascii_text(max_size=32),
    now=aware_datetimes(),
)
def test_uninstall_vacant_slot_takes_precedence_over_fixture_context_raises_is_empty(
    mount_id: UUID,
    fixture_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """A vacant slot raises MountIsEmptyError even when the context carries a fixture_id."""
    mount = _mount(mount_id=mount_id, installed_asset_id=None)
    context = UninstallAssetContext(installed_asset_fixture_id=fixture_id)
    with pytest.raises(MountIsEmptyError):
        uninstall_asset.decide(
            state=mount,
            command=UninstallAsset(mount_id=mount_id, reason=reason),
            context=context,
            now=now,
        )


@pytest.mark.unit
@given(
    mount_id=st.uuids(),
    occupant=st.uuids(),
    fixture_id=st.uuids(),
    reason=printable_ascii_text(max_size=32),
    now=aware_datetimes(),
)
def test_uninstall_fixture_bound_asset_always_raises_has_fixture_bound_asset(
    mount_id: UUID,
    occupant: UUID,
    fixture_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """An installed Asset with a Fixture back-reference raises MountHasFixtureBoundAssetError."""
    mount = _mount(mount_id=mount_id, installed_asset_id=occupant)
    context = UninstallAssetContext(installed_asset_fixture_id=fixture_id)
    with pytest.raises(MountHasFixtureBoundAssetError) as exc:
        uninstall_asset.decide(
            state=mount,
            command=UninstallAsset(mount_id=mount_id, reason=reason),
            context=context,
            now=now,
        )
    assert exc.value.mount_id == mount_id
    assert exc.value.asset_id == occupant
    assert exc.value.fixture_id == fixture_id


@pytest.mark.unit
@given(
    mount_id=st.uuids(),
    occupant=st.uuids(),
    reason=printable_ascii_text(max_size=32),
    now=aware_datetimes(),
)
def test_uninstall_active_occupied_mount_emits_uninstalled_keyed_on_state(
    mount_id: UUID,
    occupant: UUID,
    reason: str,
    now: datetime,
) -> None:
    """An Active, occupied Mount with empty context emits one MountAssetUninstalled."""
    mount = _mount(mount_id=mount_id, installed_asset_id=occupant)
    events = uninstall_asset.decide(
        state=mount,
        command=UninstallAsset(mount_id=mount_id, reason=reason),
        context=_EMPTY_CONTEXT,
        now=now,
    )
    assert events == [
        MountAssetUninstalled(
            mount_id=mount_id,
            asset_id=occupant,
            reason=reason,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    mount_id=st.uuids(),
    occupant=st.uuids(),
    reason=printable_ascii_text(max_size=32),
    now=aware_datetimes(),
)
def test_uninstall_is_pure_same_input_same_output(
    mount_id: UUID,
    occupant: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal results (no clock leakage)."""
    mount = _mount(mount_id=mount_id, installed_asset_id=occupant)
    command = UninstallAsset(mount_id=mount_id, reason=reason)
    first = uninstall_asset.decide(state=mount, command=command, context=_EMPTY_CONTEXT, now=now)
    second = uninstall_asset.decide(state=mount, command=command, context=_EMPTY_CONTEXT, now=now)
    assert first == second
