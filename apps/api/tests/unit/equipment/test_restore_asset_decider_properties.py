"""Property-based tests for `restore_asset.decide` (Equipment BC).

Complements the example-based `test_restore_asset_decider.py` with
universal claims across generated inputs. The decider is a pure
guard-free condition transition

    (state, command, now) -> list[AssetRestored]

Load-bearing properties:

  - state=None always raises `AssetNotFoundError` carrying command.asset_id.
  - The condition partition is total over `AssetCondition`: Nominal is a
    no-op (returns []), every other condition emits exactly one
    `AssetRestored` (asset_id=state.id, reason=command.reason,
    occurred_at=now). Lifecycle is never gated, so any lifecycle yields
    the same outcome.
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
    AssetCondition,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetRestored,
    AssetTier,
)
from cora.equipment.features import restore_asset
from cora.equipment.features.restore_asset import RestoreAsset
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_RESTORABLE_SOURCES = tuple(c for c in AssetCondition if c is not AssetCondition.NOMINAL)


def _asset(
    *,
    condition: AssetCondition,
    asset_id: UUID,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("Stage-Aerotech-A3200"),
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
def test_restore_with_none_state_always_raises_not_found(
    asset_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Empty stream always raises `AssetNotFoundError` carrying command.asset_id."""
    with pytest.raises(AssetNotFoundError) as exc:
        restore_asset.decide(
            state=None,
            command=RestoreAsset(asset_id=asset_id, reason=reason),
            now=now,
        )
    assert exc.value.asset_id == asset_id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    source=st.sampled_from(_RESTORABLE_SOURCES),
    lifecycle=st.sampled_from(AssetLifecycle),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_restore_from_non_nominal_source_emits_single_event(
    asset_id: UUID,
    source: AssetCondition,
    lifecycle: AssetLifecycle,
    reason: str,
    now: datetime,
) -> None:
    """Any condition other than Nominal emits one AssetRestored, any lifecycle."""
    events = restore_asset.decide(
        state=_asset(condition=source, asset_id=asset_id, lifecycle=lifecycle),
        command=RestoreAsset(asset_id=asset_id, reason=reason),
        now=now,
    )
    assert events == [AssetRestored(asset_id=asset_id, reason=reason, occurred_at=now)]


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    lifecycle=st.sampled_from(AssetLifecycle),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_restore_when_already_nominal_returns_no_events(
    asset_id: UUID,
    lifecycle: AssetLifecycle,
    reason: str,
    now: datetime,
) -> None:
    """A Nominal source is a no-op: the decider returns [] for any lifecycle."""
    events = restore_asset.decide(
        state=_asset(
            condition=AssetCondition.NOMINAL,
            asset_id=asset_id,
            lifecycle=lifecycle,
        ),
        command=RestoreAsset(asset_id=asset_id, reason=reason),
        now=now,
    )
    assert events == []


@pytest.mark.unit
@given(
    state_asset_id=st.uuids(),
    command_asset_id=st.uuids(),
    source=st.sampled_from(_RESTORABLE_SOURCES),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_restore_emits_event_with_state_id_not_command_asset_id(
    state_asset_id: UUID,
    command_asset_id: UUID,
    source: AssetCondition,
    reason: str,
    now: datetime,
) -> None:
    """The emitted event's asset_id is state.id, not command.asset_id."""
    assume(state_asset_id != command_asset_id)
    events = restore_asset.decide(
        state=_asset(condition=source, asset_id=state_asset_id),
        command=RestoreAsset(asset_id=command_asset_id, reason=reason),
        now=now,
    )
    assert events[0].asset_id == state_asset_id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    source=st.sampled_from(_RESTORABLE_SOURCES),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_restore_is_pure_same_input_same_output(
    asset_id: UUID,
    source: AssetCondition,
    reason: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _asset(condition=source, asset_id=asset_id)
    command = RestoreAsset(asset_id=asset_id, reason=reason)
    first = restore_asset.decide(state=state, command=command, now=now)
    second = restore_asset.decide(state=state, command=command, now=now)
    assert first == second
