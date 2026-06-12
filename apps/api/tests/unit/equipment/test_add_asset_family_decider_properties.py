"""Property-based tests for `add_asset_family.decide` (Equipment BC).

Complements the example-based `test_add_asset_family_decider.py` with
universal claims across generated inputs. The decider is a pure
family-mutation guard

    (state, command, now) -> list[AssetFamilyAdded]

Load-bearing properties:

  - state=None always raises `AssetNotFoundError` carrying command.asset_id.
  - A `Decommissioned` source always raises `AssetCannotAddFamilyError`
    carrying state.id, the command family_id, and a reason naming the
    Decommissioned lifecycle.
  - A family_id already in state.family_ids always raises
    `AssetCannotAddFamilyError` (strict-not-idempotent) carrying state.id,
    the family_id, and a reason naming "already".
  - Every non-Decommissioned lifecycle with a fresh family_id emits
    exactly one `AssetFamilyAdded` (asset_id=state.id, occurred_at=now),
    so a future lifecycle value cannot silently fall through the guard.
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
    AssetCannotAddFamilyError,
    AssetFamilyAdded,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import add_asset_family
from cora.equipment.features.add_asset_family import AddAssetFamily
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_ALLOWED_SOURCES = tuple(s for s in AssetLifecycle if s is not AssetLifecycle.DECOMMISSIONED)


def _asset(
    *,
    asset_id: UUID,
    lifecycle: AssetLifecycle,
    family_ids: frozenset[UUID] = frozenset(),
) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        tier=AssetTier.UNIT,
        parent_id=UUID(int=1),
        lifecycle=lifecycle,
        family_ids=family_ids,
    )


@pytest.mark.unit
@given(asset_id=st.uuids(), family_id=st.uuids(), now=aware_datetimes())
def test_add_family_with_none_state_always_raises_not_found(
    asset_id: UUID,
    family_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `AssetNotFoundError` carrying command.asset_id."""
    with pytest.raises(AssetNotFoundError) as exc:
        add_asset_family.decide(
            state=None,
            command=AddAssetFamily(asset_id=asset_id, family_id=family_id),
            now=now,
        )
    assert exc.value.asset_id == asset_id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    family_id=st.uuids(),
    source=st.sampled_from(_ALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_add_family_from_allowed_lifecycle_emits_single_event(
    asset_id: UUID,
    family_id: UUID,
    source: AssetLifecycle,
    now: datetime,
) -> None:
    """Every non-Decommissioned lifecycle with a fresh family emits one event."""
    events = add_asset_family.decide(
        state=_asset(asset_id=asset_id, lifecycle=source),
        command=AddAssetFamily(asset_id=asset_id, family_id=family_id),
        now=now,
    )
    assert events == [AssetFamilyAdded(asset_id=asset_id, family_id=family_id, occurred_at=now)]


@pytest.mark.unit
@given(asset_id=st.uuids(), family_id=st.uuids(), now=aware_datetimes())
def test_add_family_to_decommissioned_always_raises_cannot_add(
    asset_id: UUID,
    family_id: UUID,
    now: datetime,
) -> None:
    """A retired asset always raises, naming the Decommissioned lifecycle."""
    with pytest.raises(AssetCannotAddFamilyError) as exc:
        add_asset_family.decide(
            state=_asset(asset_id=asset_id, lifecycle=AssetLifecycle.DECOMMISSIONED),
            command=AddAssetFamily(asset_id=asset_id, family_id=family_id),
            now=now,
        )
    assert exc.value.asset_id == asset_id
    assert exc.value.family_id == family_id
    assert AssetLifecycle.DECOMMISSIONED.value in exc.value.reason


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    family_id=st.uuids(),
    source=st.sampled_from(_ALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_add_family_already_present_always_raises_cannot_add(
    asset_id: UUID,
    family_id: UUID,
    source: AssetLifecycle,
    now: datetime,
) -> None:
    """Strict-not-idempotent: re-adding a present family always raises 'already'."""
    with pytest.raises(AssetCannotAddFamilyError) as exc:
        add_asset_family.decide(
            state=_asset(
                asset_id=asset_id,
                lifecycle=source,
                family_ids=frozenset({family_id}),
            ),
            command=AddAssetFamily(asset_id=asset_id, family_id=family_id),
            now=now,
        )
    assert exc.value.asset_id == asset_id
    assert exc.value.family_id == family_id
    assert "already" in exc.value.reason


@pytest.mark.unit
@given(
    state_asset_id=st.uuids(),
    command_asset_id=st.uuids(),
    family_id=st.uuids(),
    now=aware_datetimes(),
)
def test_add_family_emits_event_with_state_id_not_command_asset_id(
    state_asset_id: UUID,
    command_asset_id: UUID,
    family_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's asset_id is state.id, not command.asset_id."""
    assume(state_asset_id != command_asset_id)
    events = add_asset_family.decide(
        state=_asset(asset_id=state_asset_id, lifecycle=AssetLifecycle.ACTIVE),
        command=AddAssetFamily(asset_id=command_asset_id, family_id=family_id),
        now=now,
    )
    assert events[0].asset_id == state_asset_id


@pytest.mark.unit
@given(asset_id=st.uuids(), family_id=st.uuids(), now=aware_datetimes())
def test_add_family_is_pure_same_input_same_output(
    asset_id: UUID,
    family_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _asset(asset_id=asset_id, lifecycle=AssetLifecycle.ACTIVE)
    command = AddAssetFamily(asset_id=asset_id, family_id=family_id)
    first = add_asset_family.decide(state=state, command=command, now=now)
    second = add_asset_family.decide(state=state, command=command, now=now)
    assert first == second
