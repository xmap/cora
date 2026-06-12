"""Property-based tests for `degrade_asset.decide` (Equipment BC).

Complements the example-based `test_degrade_asset_decider.py` with
universal claims across generated inputs. The decider is a pure,
guard-free condition transition (any condition -> Degraded), gated
only on existence

    (state, command, now) -> list[AssetDegraded]

Load-bearing properties:

  - state=None always raises `AssetNotFoundError` carrying command.asset_id.
  - The source-condition partition is total over `AssetCondition`:
    every non-Degraded condition emits exactly one `AssetDegraded`
    (asset_id=state.id, reason=command.reason, occurred_at=now), so a
    future condition value cannot silently fall through to a no-op.
  - Already-Degraded is the sole no-op: returns [] regardless of reason.
  - Condition transitions are lifecycle-independent: degrading emits in
    every `AssetLifecycle` state (including Decommissioned).
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
    AssetDegraded,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import degrade_asset
from cora.equipment.features.degrade_asset import DegradeAsset
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_PARENT_ID = UUID(int=1)

_DEGRADABLE_SOURCES = tuple(c for c in AssetCondition if c is not AssetCondition.DEGRADED)


def _asset(
    *,
    asset_id: UUID,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
    condition: AssetCondition = AssetCondition.NOMINAL,
) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("Detector-FLIR-Oryx-001"),
        tier=AssetTier.DEVICE,
        parent_id=_PARENT_ID,
        lifecycle=lifecycle,
        condition=condition,
    )


@pytest.mark.unit
@given(asset_id=st.uuids(), reason=printable_ascii_text(max_size=64), now=aware_datetimes())
def test_degrade_with_none_state_always_raises_not_found(
    asset_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Empty stream always raises `AssetNotFoundError` carrying command.asset_id."""
    with pytest.raises(AssetNotFoundError) as exc:
        degrade_asset.decide(
            state=None,
            command=DegradeAsset(asset_id=asset_id, reason=reason),
            now=now,
        )
    assert exc.value.asset_id == asset_id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    source=st.sampled_from(_DEGRADABLE_SOURCES),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_degrade_from_non_degraded_source_emits_single_event(
    asset_id: UUID,
    source: AssetCondition,
    reason: str,
    now: datetime,
) -> None:
    """Every non-Degraded condition emits exactly one AssetDegraded."""
    events = degrade_asset.decide(
        state=_asset(asset_id=asset_id, condition=source),
        command=DegradeAsset(asset_id=asset_id, reason=reason),
        now=now,
    )
    assert events == [AssetDegraded(asset_id=asset_id, reason=reason, occurred_at=now)]


@pytest.mark.unit
@given(asset_id=st.uuids(), reason=printable_ascii_text(max_size=64), now=aware_datetimes())
def test_degrade_when_already_degraded_returns_no_events(
    asset_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Re-degrading an already-Degraded asset is the sole no-op."""
    events = degrade_asset.decide(
        state=_asset(asset_id=asset_id, condition=AssetCondition.DEGRADED),
        command=DegradeAsset(asset_id=asset_id, reason=reason),
        now=now,
    )
    assert events == []


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    lifecycle=st.sampled_from(AssetLifecycle),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_degrade_in_any_lifecycle_state_emits_single_event(
    asset_id: UUID,
    lifecycle: AssetLifecycle,
    reason: str,
    now: datetime,
) -> None:
    """Condition transitions are lifecycle-independent; emits in every state."""
    events = degrade_asset.decide(
        state=_asset(asset_id=asset_id, lifecycle=lifecycle, condition=AssetCondition.NOMINAL),
        command=DegradeAsset(asset_id=asset_id, reason=reason),
        now=now,
    )
    assert len(events) == 1


@pytest.mark.unit
@given(
    state_asset_id=st.uuids(),
    command_asset_id=st.uuids(),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_degrade_emits_event_with_state_id_not_command_asset_id(
    state_asset_id: UUID,
    command_asset_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """The emitted event's asset_id is state.id, not command.asset_id."""
    assume(state_asset_id != command_asset_id)
    events = degrade_asset.decide(
        state=_asset(asset_id=state_asset_id, condition=AssetCondition.NOMINAL),
        command=DegradeAsset(asset_id=command_asset_id, reason=reason),
        now=now,
    )
    assert events[0].asset_id == state_asset_id


@pytest.mark.unit
@given(asset_id=st.uuids(), reason=printable_ascii_text(max_size=64), now=aware_datetimes())
def test_degrade_is_pure_same_input_same_output(
    asset_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _asset(asset_id=asset_id, condition=AssetCondition.NOMINAL)
    command = DegradeAsset(asset_id=asset_id, reason=reason)
    first = degrade_asset.decide(state=state, command=command, now=now)
    second = degrade_asset.decide(state=state, command=command, now=now)
    assert first == second
