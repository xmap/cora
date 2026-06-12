"""Property-based tests for `relocate_asset.decide` (Equipment BC).

Complements the example-based `test_relocate_asset_decider.py` with
universal claims across generated inputs. The decider is a pure
hierarchy mutation

    (state, command, now) -> list[AssetRelocated]

with FOUR disqualifying conditions collapsed into one error class
(`AssetCannotRelocateError`) plus the standard `AssetNotFoundError`
guard.

Load-bearing properties:

  - state=None always raises `AssetNotFoundError` carrying
    command.asset_id.
  - A root Asset (parent_id=None) always raises
    `AssetCannotRelocateError` carrying state.id (root-anchoring
    invariant).
  - A `Decommissioned` Asset always raises `AssetCannotRelocateError`
    carrying state.id (retired; no hierarchy changes).
  - target == asset_id (self-loop) always raises
    `AssetCannotRelocateError`.
  - target == current parent_id (no-op) always raises
    `AssetCannotRelocateError`.
  - Any non-Decommissioned, non-root Asset with a distinct, non-self
    target emits exactly one `AssetRelocated`
    (from_parent_id=state.parent_id, to_parent_id=command.to_parent_id,
    occurred_at=now).
  - The emitted event's asset_id is `state.id`, never command.asset_id.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotRelocateError,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetRelocated,
    AssetTier,
)
from cora.equipment.features import relocate_asset
from cora.equipment.features.relocate_asset import RelocateAsset
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_RELOCATABLE_LIFECYCLES = tuple(
    lifecycle for lifecycle in AssetLifecycle if lifecycle is not AssetLifecycle.DECOMMISSIONED
)


def _asset(
    *,
    asset_id: UUID,
    parent_id: UUID | None,
    lifecycle: AssetLifecycle = AssetLifecycle.COMMISSIONED,
    tier: AssetTier = AssetTier.DEVICE,
) -> Asset:
    """Build an Asset with generated id + parent; bounded fields fixed.

    Mirrors the example test's `_asset` helper but drives `id` and
    `parent_id` from Hypothesis draws so error-payload and event-id
    assertions can compare against them.
    """
    return Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        tier=tier,
        parent_id=parent_id,
        lifecycle=lifecycle,
    )


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    to_parent_id=st.uuids(),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_relocate_with_none_state_always_raises_not_found(
    asset_id: UUID,
    to_parent_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Empty stream always raises `AssetNotFoundError` carrying command.asset_id."""
    with pytest.raises(AssetNotFoundError) as exc:
        relocate_asset.decide(
            state=None,
            command=RelocateAsset(asset_id=asset_id, to_parent_id=to_parent_id, reason=reason),
            now=now,
        )
    assert exc.value.asset_id == asset_id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    to_parent_id=st.uuids(),
    reason=printable_ascii_text(max_size=64),
    lifecycle=st.sampled_from(_RELOCATABLE_LIFECYCLES),
    now=aware_datetimes(),
)
def test_relocate_root_asset_always_raises_cannot_relocate(
    asset_id: UUID,
    to_parent_id: UUID,
    reason: str,
    lifecycle: AssetLifecycle,
    now: datetime,
) -> None:
    """A root Asset (parent_id=None) always raises, carrying state.id."""
    assume(to_parent_id != asset_id)
    state = _asset(asset_id=asset_id, parent_id=None, lifecycle=lifecycle)
    with pytest.raises(AssetCannotRelocateError) as exc:
        relocate_asset.decide(
            state=state,
            command=RelocateAsset(asset_id=asset_id, to_parent_id=to_parent_id, reason=reason),
            now=now,
        )
    assert exc.value.asset_id == state.id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    parent_id=st.uuids(),
    to_parent_id=st.uuids(),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_relocate_decommissioned_asset_always_raises_cannot_relocate(
    asset_id: UUID,
    parent_id: UUID,
    to_parent_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """A Decommissioned Asset always raises, carrying state.id."""
    assume(to_parent_id != asset_id)
    assume(to_parent_id != parent_id)
    state = _asset(
        asset_id=asset_id,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.DECOMMISSIONED,
    )
    with pytest.raises(AssetCannotRelocateError) as exc:
        relocate_asset.decide(
            state=state,
            command=RelocateAsset(asset_id=asset_id, to_parent_id=to_parent_id, reason=reason),
            now=now,
        )
    assert exc.value.asset_id == state.id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    parent_id=st.uuids(),
    reason=printable_ascii_text(max_size=64),
    lifecycle=st.sampled_from(_RELOCATABLE_LIFECYCLES),
    now=aware_datetimes(),
)
def test_relocate_self_loop_target_always_raises_cannot_relocate(
    asset_id: UUID,
    parent_id: UUID,
    reason: str,
    lifecycle: AssetLifecycle,
    now: datetime,
) -> None:
    """Target == asset_id (self-loop) always raises, carrying state.id."""
    state = _asset(asset_id=asset_id, parent_id=parent_id, lifecycle=lifecycle)
    with pytest.raises(AssetCannotRelocateError) as exc:
        relocate_asset.decide(
            state=state,
            command=RelocateAsset(asset_id=asset_id, to_parent_id=state.id, reason=reason),
            now=now,
        )
    assert exc.value.asset_id == state.id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    parent_id=st.uuids(),
    reason=printable_ascii_text(max_size=64),
    lifecycle=st.sampled_from(_RELOCATABLE_LIFECYCLES),
    now=aware_datetimes(),
)
def test_relocate_to_current_parent_always_raises_cannot_relocate(
    asset_id: UUID,
    parent_id: UUID,
    reason: str,
    lifecycle: AssetLifecycle,
    now: datetime,
) -> None:
    """Target == current parent_id (no-op) always raises, carrying state.id."""
    assume(parent_id != asset_id)
    state = _asset(asset_id=asset_id, parent_id=parent_id, lifecycle=lifecycle)
    with pytest.raises(AssetCannotRelocateError) as exc:
        relocate_asset.decide(
            state=state,
            command=RelocateAsset(asset_id=asset_id, to_parent_id=parent_id, reason=reason),
            now=now,
        )
    assert exc.value.asset_id == state.id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    parent_id=st.uuids(),
    to_parent_id=st.uuids(),
    reason=printable_ascii_text(max_size=64),
    lifecycle=st.sampled_from(_RELOCATABLE_LIFECYCLES),
    now=aware_datetimes(),
)
def test_relocate_with_valid_target_emits_single_event(
    asset_id: UUID,
    parent_id: UUID,
    to_parent_id: UUID,
    reason: str,
    lifecycle: AssetLifecycle,
    now: datetime,
) -> None:
    """Any non-Decommissioned, non-root Asset with a distinct, non-self
    target emits exactly one AssetRelocated carrying both parents."""
    assume(to_parent_id != asset_id)
    assume(to_parent_id != parent_id)
    state = _asset(asset_id=asset_id, parent_id=parent_id, lifecycle=lifecycle)
    events = relocate_asset.decide(
        state=state,
        command=RelocateAsset(asset_id=asset_id, to_parent_id=to_parent_id, reason=reason),
        now=now,
    )
    assert events == [
        AssetRelocated(
            asset_id=state.id,
            from_parent_id=parent_id,
            to_parent_id=to_parent_id,
            reason=reason,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    state_asset_id=st.uuids(),
    command_asset_id=st.uuids(),
    parent_id=st.uuids(),
    to_parent_id=st.uuids(),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_relocate_emits_event_with_state_id_not_command_asset_id(
    state_asset_id: UUID,
    command_asset_id: UUID,
    parent_id: UUID,
    to_parent_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """The emitted event's asset_id is state.id, not command.asset_id."""
    assume(state_asset_id != command_asset_id)
    assume(to_parent_id != state_asset_id)
    assume(to_parent_id != parent_id)
    state = _asset(asset_id=state_asset_id, parent_id=parent_id)
    events = relocate_asset.decide(
        state=state,
        command=RelocateAsset(asset_id=command_asset_id, to_parent_id=to_parent_id, reason=reason),
        now=now,
    )
    assert events[0].asset_id == state_asset_id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    parent_id=st.uuids(),
    to_parent_id=st.uuids(),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_relocate_is_pure_same_input_same_output(
    asset_id: UUID,
    parent_id: UUID,
    to_parent_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    assume(to_parent_id != asset_id)
    assume(to_parent_id != parent_id)
    state = _asset(asset_id=asset_id, parent_id=parent_id)
    command = RelocateAsset(asset_id=asset_id, to_parent_id=to_parent_id, reason=reason)
    first = relocate_asset.decide(state=state, command=command, now=now)
    second = relocate_asset.decide(state=state, command=command, now=now)
    assert first == second
