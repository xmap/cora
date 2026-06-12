"""Property-based tests for `fault_asset.decide` (Equipment BC).

Complements the example-based `test_fault_asset_decider.py` with
universal claims across generated inputs. The decider is a pure
target-state condition mutation

    (state, command, now) -> list[AssetFaulted]

Lifecycle is NOT gated; condition moves to Faulted from any source,
with a no-op when already Faulted.

Load-bearing properties:

  - state=None always raises `AssetNotFoundError` carrying
    command.asset_id.
  - The source-condition partition is total over `AssetCondition`:
    every non-Faulted condition (in any lifecycle) emits exactly one
    `AssetFaulted` (asset_id=state.id, reason=command.reason,
    occurred_at=now), and the already-Faulted source is the sole no-op
    returning [], so a future condition value cannot silently fall
    through.
  - The emitted event's asset_id is `state.id`, never command.asset_id.
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
    AssetCondition,
    AssetFaulted,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import fault_asset
from cora.equipment.features.fault_asset import FaultAsset
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_ASSET_NAME = AssetName("Pump-Edwards-XDS35i")

_FAULTABLE_SOURCES = tuple(c for c in AssetCondition if c is not AssetCondition.FAULTED)


def _asset(
    *,
    asset_id: UUID,
    lifecycle: AssetLifecycle,
    condition: AssetCondition,
) -> Asset:
    return Asset(
        id=asset_id,
        name=_ASSET_NAME,
        tier=AssetTier.DEVICE,
        parent_id=UUID(int=1),
        lifecycle=lifecycle,
        condition=condition,
    )


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_fault_with_none_state_always_raises_not_found(
    asset_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Empty stream always raises `AssetNotFoundError` carrying command.asset_id."""
    with pytest.raises(AssetNotFoundError) as exc:
        fault_asset.decide(
            state=None,
            command=FaultAsset(asset_id=asset_id, reason=reason),
            now=now,
        )
    assert exc.value.asset_id == asset_id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    lifecycle=st.sampled_from(AssetLifecycle),
    source=st.sampled_from(_FAULTABLE_SOURCES),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_fault_from_non_faulted_source_emits_single_event(
    asset_id: UUID,
    lifecycle: AssetLifecycle,
    source: AssetCondition,
    reason: str,
    now: datetime,
) -> None:
    """Any non-Faulted condition, in any lifecycle, emits one AssetFaulted."""
    events = fault_asset.decide(
        state=_asset(asset_id=asset_id, lifecycle=lifecycle, condition=source),
        command=FaultAsset(asset_id=asset_id, reason=reason),
        now=now,
    )
    assert events == [AssetFaulted(asset_id=asset_id, reason=reason, occurred_at=now)]


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    lifecycle=st.sampled_from(AssetLifecycle),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_fault_when_already_faulted_returns_no_event(
    asset_id: UUID,
    lifecycle: AssetLifecycle,
    reason: str,
    now: datetime,
) -> None:
    """Already-Faulted is the sole no-op source; returns no events."""
    events = fault_asset.decide(
        state=_asset(
            asset_id=asset_id,
            lifecycle=lifecycle,
            condition=AssetCondition.FAULTED,
        ),
        command=FaultAsset(asset_id=asset_id, reason=reason),
        now=now,
    )
    assert events == []


@pytest.mark.unit
@given(
    state_asset_id=st.uuids(),
    command_asset_id=st.uuids(),
    source=st.sampled_from(_FAULTABLE_SOURCES),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_fault_uses_state_id_not_command_asset_id(
    state_asset_id: UUID,
    command_asset_id: UUID,
    source: AssetCondition,
    reason: str,
    now: datetime,
) -> None:
    """The emitted event's asset_id is state.id, not command.asset_id."""
    assume(state_asset_id != command_asset_id)
    events = fault_asset.decide(
        state=_asset(
            asset_id=state_asset_id,
            lifecycle=AssetLifecycle.ACTIVE,
            condition=source,
        ),
        command=FaultAsset(asset_id=command_asset_id, reason=reason),
        now=now,
    )
    assert events[0].asset_id == state_asset_id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    source=st.sampled_from(_FAULTABLE_SOURCES),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_fault_is_pure_same_input_same_output(
    asset_id: UUID,
    source: AssetCondition,
    reason: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _asset(asset_id=asset_id, lifecycle=AssetLifecycle.ACTIVE, condition=source)
    command = FaultAsset(asset_id=asset_id, reason=reason)
    first = fault_asset.decide(state=state, command=command, now=now)
    second = fault_asset.decide(state=state, command=command, now=now)
    assert first == second
