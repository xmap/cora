"""Property-based tests for `remove_asset_family.decide` (Equipment BC).

Complements the example-based `test_remove_asset_family_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source transition

    (state, command, now) -> list[AssetFamilyRemoved]

Load-bearing properties:

  - state=None always raises `AssetNotFoundError` carrying command.asset_id.
  - The lifecycle partition is total over `AssetLifecycle`: when the
    target family is present, only `Decommissioned` raises
    `AssetCannotRemoveFamilyError`; every other lifecycle emits exactly
    one `AssetFamilyRemoved` (asset_id=state.id, family_id=command.family_id,
    occurred_at=now), so a future lifecycle value cannot silently fall
    through.
  - A family not in `state.family_ids` raises `AssetCannotRemoveFamilyError`
    (strict-not-idempotent) carrying command.family_id, even on an
    otherwise-removable lifecycle.
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
    AssetCannotRemoveFamilyError,
    AssetFamilyRemoved,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import remove_asset_family
from cora.equipment.features.remove_asset_family import RemoveAssetFamily
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_PARENT_ID = UUID(int=1)

_REMOVABLE_SOURCES = tuple(lc for lc in AssetLifecycle if lc is not AssetLifecycle.DECOMMISSIONED)


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
        parent_id=_PARENT_ID,
        lifecycle=lifecycle,
        family_ids=family_ids,
    )


@pytest.mark.unit
@given(asset_id=st.uuids(), family_id=st.uuids(), now=aware_datetimes())
def test_remove_family_with_none_state_always_raises_not_found(
    asset_id: UUID,
    family_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `AssetNotFoundError` carrying command.asset_id."""
    with pytest.raises(AssetNotFoundError) as exc:
        remove_asset_family.decide(
            state=None,
            command=RemoveAssetFamily(asset_id=asset_id, family_id=family_id),
            now=now,
        )
    assert exc.value.asset_id == asset_id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    family_id=st.uuids(),
    lifecycle=st.sampled_from(_REMOVABLE_SOURCES),
    now=aware_datetimes(),
)
def test_remove_family_from_removable_lifecycle_emits_single_event(
    asset_id: UUID,
    family_id: UUID,
    lifecycle: AssetLifecycle,
    now: datetime,
) -> None:
    """Any non-Decommissioned lifecycle with the family present emits one event."""
    events = remove_asset_family.decide(
        state=_asset(
            asset_id=asset_id,
            lifecycle=lifecycle,
            family_ids=frozenset({family_id}),
        ),
        command=RemoveAssetFamily(asset_id=asset_id, family_id=family_id),
        now=now,
    )
    assert events == [AssetFamilyRemoved(asset_id=asset_id, family_id=family_id, occurred_at=now)]


@pytest.mark.unit
@given(asset_id=st.uuids(), family_id=st.uuids(), now=aware_datetimes())
def test_remove_family_from_decommissioned_always_raises_cannot_remove(
    asset_id: UUID,
    family_id: UUID,
    now: datetime,
) -> None:
    """Decommissioned raises even when the family is present, carrying ids."""
    with pytest.raises(AssetCannotRemoveFamilyError) as exc:
        remove_asset_family.decide(
            state=_asset(
                asset_id=asset_id,
                lifecycle=AssetLifecycle.DECOMMISSIONED,
                family_ids=frozenset({family_id}),
            ),
            command=RemoveAssetFamily(asset_id=asset_id, family_id=family_id),
            now=now,
        )
    assert exc.value.asset_id == asset_id
    assert exc.value.family_id == family_id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    present_family_id=st.uuids(),
    absent_family_id=st.uuids(),
    lifecycle=st.sampled_from(_REMOVABLE_SOURCES),
    now=aware_datetimes(),
)
def test_remove_absent_family_always_raises_cannot_remove(
    asset_id: UUID,
    present_family_id: UUID,
    absent_family_id: UUID,
    lifecycle: AssetLifecycle,
    now: datetime,
) -> None:
    """Strict-not-idempotent: removing an absent family raises, carrying family_id."""
    assume(present_family_id != absent_family_id)
    with pytest.raises(AssetCannotRemoveFamilyError) as exc:
        remove_asset_family.decide(
            state=_asset(
                asset_id=asset_id,
                lifecycle=lifecycle,
                family_ids=frozenset({present_family_id}),
            ),
            command=RemoveAssetFamily(asset_id=asset_id, family_id=absent_family_id),
            now=now,
        )
    assert exc.value.family_id == absent_family_id


@pytest.mark.unit
@given(state_asset_id=st.uuids(), command_asset_id=st.uuids(), now=aware_datetimes())
def test_remove_family_uses_state_id_not_command_asset_id(
    state_asset_id: UUID,
    command_asset_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's asset_id is state.id, not command.asset_id."""
    assume(state_asset_id != command_asset_id)
    family_id = UUID(int=7)
    events = remove_asset_family.decide(
        state=_asset(
            asset_id=state_asset_id,
            lifecycle=AssetLifecycle.ACTIVE,
            family_ids=frozenset({family_id}),
        ),
        command=RemoveAssetFamily(asset_id=command_asset_id, family_id=family_id),
        now=now,
    )
    assert events[0].asset_id == state_asset_id


@pytest.mark.unit
@given(asset_id=st.uuids(), family_id=st.uuids(), now=aware_datetimes())
def test_remove_family_is_pure_same_input_same_output(
    asset_id: UUID,
    family_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _asset(
        asset_id=asset_id,
        lifecycle=AssetLifecycle.ACTIVE,
        family_ids=frozenset({family_id}),
    )
    command = RemoveAssetFamily(asset_id=asset_id, family_id=family_id)
    first = remove_asset_family.decide(state=state, command=command, now=now)
    second = remove_asset_family.decide(state=state, command=command, now=now)
    assert first == second
