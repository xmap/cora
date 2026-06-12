"""Property-based tests for `activate_asset.decide` (Equipment BC).

Complements the example-based `test_activate_asset_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source lifecycle transition

    (state, command, now) -> list[AssetActivated]

Load-bearing properties:

  - state=None always raises `AssetNotFoundError` carrying command.asset_id.
  - The source-state partition is total over `AssetLifecycle`: only
    `Commissioned` emits exactly one `AssetActivated` (asset_id=state.id,
    occurred_at=now); every other lifecycle raises
    `AssetCannotActivateError` carrying the current lifecycle, so a
    future lifecycle value cannot silently fall through.
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
    AssetActivated,
    AssetCannotActivateError,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import activate_asset
from cora.equipment.features.activate_asset import ActivateAsset
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_PARENT_ID = UUID(int=1)

_ACTIVATABLE_SOURCES = (AssetLifecycle.COMMISSIONED,)
_DISALLOWED_SOURCES = tuple(
    lifecycle for lifecycle in AssetLifecycle if lifecycle not in frozenset(_ACTIVATABLE_SOURCES)
)


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
def test_activate_with_none_state_always_raises_not_found(
    asset_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `AssetNotFoundError` carrying command.asset_id."""
    with pytest.raises(AssetNotFoundError) as exc:
        activate_asset.decide(
            state=None,
            command=ActivateAsset(asset_id=asset_id),
            now=now,
        )
    assert exc.value.asset_id == asset_id


@pytest.mark.unit
@given(asset_id=st.uuids(), now=aware_datetimes())
def test_activate_from_commissioned_emits_single_event(
    asset_id: UUID,
    now: datetime,
) -> None:
    """Commissioned is the only activatable source; emits one AssetActivated."""
    events = activate_asset.decide(
        state=_asset(asset_id=asset_id, lifecycle=AssetLifecycle.COMMISSIONED),
        command=ActivateAsset(asset_id=asset_id),
        now=now,
    )
    assert events == [AssetActivated(asset_id=asset_id, occurred_at=now)]


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_activate_from_disallowed_source_always_raises_cannot_activate(
    asset_id: UUID,
    source: AssetLifecycle,
    now: datetime,
) -> None:
    """Any source other than Commissioned raises, carrying the current lifecycle."""
    with pytest.raises(AssetCannotActivateError) as exc:
        activate_asset.decide(
            state=_asset(asset_id=asset_id, lifecycle=source),
            command=ActivateAsset(asset_id=asset_id),
            now=now,
        )
    assert exc.value.asset_id == asset_id
    assert exc.value.current_lifecycle is source


@pytest.mark.unit
@given(state_asset_id=st.uuids(), command_asset_id=st.uuids(), now=aware_datetimes())
def test_activate_emits_event_with_state_id_not_command_asset_id(
    state_asset_id: UUID,
    command_asset_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's asset_id is state.id, not command.asset_id."""
    assume(state_asset_id != command_asset_id)
    events = activate_asset.decide(
        state=_asset(asset_id=state_asset_id, lifecycle=AssetLifecycle.COMMISSIONED),
        command=ActivateAsset(asset_id=command_asset_id),
        now=now,
    )
    assert events[0].asset_id == state_asset_id


@pytest.mark.unit
@given(asset_id=st.uuids(), now=aware_datetimes())
def test_activate_is_pure_same_input_same_output(
    asset_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _asset(asset_id=asset_id, lifecycle=AssetLifecycle.COMMISSIONED)
    command = ActivateAsset(asset_id=asset_id)
    first = activate_asset.decide(state=state, command=command, now=now)
    second = activate_asset.decide(state=state, command=command, now=now)
    assert first == second
