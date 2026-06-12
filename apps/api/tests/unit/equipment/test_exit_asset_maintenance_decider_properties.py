"""Property-based tests for `exit_asset_maintenance.decide` (Equipment BC).

Complements the example-based `test_exit_asset_maintenance_decider.py`
with universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, now) -> list[AssetMaintenanceExited]

Load-bearing properties:

  - state=None always raises `AssetNotFoundError` carrying command.asset_id.
  - The source-state partition is total over `AssetLifecycle`: only
    `Maintenance` emits exactly one `AssetMaintenanceExited`
    (asset_id=state.id, occurred_at=now); every other lifecycle raises
    `AssetCannotExitMaintenanceError` carrying the current lifecycle, so
    a future lifecycle value cannot silently fall through.
  - The emitted event's asset_id is `state.id`, never `command.asset_id`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotExitMaintenanceError,
    AssetLifecycle,
    AssetMaintenanceExited,
    AssetName,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import exit_asset_maintenance
from cora.equipment.features.exit_asset_maintenance import ExitAssetMaintenance
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_PARENT_ID = UUID(int=1)

_EXITABLE_SOURCES = (AssetLifecycle.MAINTENANCE,)
_DISALLOWED_SOURCES = tuple(s for s in AssetLifecycle if s not in frozenset(_EXITABLE_SOURCES))


def _asset(*, asset_id: UUID, lifecycle: AssetLifecycle) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        tier=AssetTier.UNIT,
        parent_id=_PARENT_ID,
        lifecycle=lifecycle,
    )


@pytest.mark.unit
@given(asset_id=st.uuids(), now=aware_datetimes())
def test_exit_maintenance_with_none_state_always_raises_not_found(
    asset_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `AssetNotFoundError` carrying command.asset_id."""
    with pytest.raises(AssetNotFoundError) as exc:
        exit_asset_maintenance.decide(
            state=None,
            command=ExitAssetMaintenance(asset_id=asset_id),
            now=now,
        )
    assert exc.value.asset_id == asset_id


@pytest.mark.unit
@given(asset_id=st.uuids(), now=aware_datetimes())
def test_exit_maintenance_from_maintenance_emits_single_event(
    asset_id: UUID,
    now: datetime,
) -> None:
    """Maintenance is the only exitable source; emits one AssetMaintenanceExited."""
    events = exit_asset_maintenance.decide(
        state=_asset(asset_id=asset_id, lifecycle=AssetLifecycle.MAINTENANCE),
        command=ExitAssetMaintenance(asset_id=asset_id),
        now=now,
    )
    assert events == [AssetMaintenanceExited(asset_id=asset_id, occurred_at=now)]


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_exit_maintenance_from_disallowed_source_always_raises_cannot_exit(
    asset_id: UUID,
    source: AssetLifecycle,
    now: datetime,
) -> None:
    """Any source other than Maintenance raises, carrying the current lifecycle."""
    with pytest.raises(AssetCannotExitMaintenanceError) as exc:
        exit_asset_maintenance.decide(
            state=_asset(asset_id=asset_id, lifecycle=source),
            command=ExitAssetMaintenance(asset_id=asset_id),
            now=now,
        )
    assert exc.value.asset_id == asset_id
    assert exc.value.current_lifecycle is source


@pytest.mark.unit
@given(state_asset_id=st.uuids(), command_asset_id=st.uuids(), now=aware_datetimes())
def test_exit_maintenance_emits_event_with_state_id_not_command_id(
    state_asset_id: UUID,
    command_asset_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's asset_id is state.id, not command.asset_id."""
    assume(state_asset_id != command_asset_id)
    events = exit_asset_maintenance.decide(
        state=_asset(asset_id=state_asset_id, lifecycle=AssetLifecycle.MAINTENANCE),
        command=ExitAssetMaintenance(asset_id=command_asset_id),
        now=now,
    )
    assert events[0].asset_id == state_asset_id


@pytest.mark.unit
@given(asset_id=st.uuids(), now=aware_datetimes())
def test_exit_maintenance_is_pure_same_input_same_output(
    asset_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _asset(asset_id=asset_id, lifecycle=AssetLifecycle.MAINTENANCE)
    command = ExitAssetMaintenance(asset_id=asset_id)
    first = exit_asset_maintenance.decide(state=state, command=command, now=now)
    second = exit_asset_maintenance.decide(state=state, command=command, now=now)
    assert first == second
