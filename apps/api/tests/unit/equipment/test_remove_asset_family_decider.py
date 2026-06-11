"""Unit tests for the `remove_asset_family` slice's pure decider.

Mirror of `test_add_asset_family_decider.py`. Two disqualifying
conditions surface as `AssetCannotRemoveFamilyError`:

  - asset is `Decommissioned`
  - capability NOT in `state.family_ids` (strict-not-idempotent)
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

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

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _asset(
    *,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
    family_ids: frozenset[uuid4] = frozenset(),  # type: ignore[assignment]
) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("APS-2BM"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        family_ids=family_ids,  # type: ignore[arg-type]
    )


@pytest.mark.unit
def test_decide_emits_asset_capability_removed_for_present_capability() -> None:
    cap1 = uuid4()
    state = _asset(family_ids=frozenset({cap1}))
    events = remove_asset_family.decide(
        state=state,
        command=RemoveAssetFamily(asset_id=state.id, family_id=cap1),
        now=_NOW,
    )
    assert events == [AssetFamilyRemoved(asset_id=state.id, family_id=cap1, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        remove_asset_family.decide(
            state=None,
            command=RemoveAssetFamily(asset_id=target_id, family_id=uuid4()),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_remove_when_asset_is_decommissioned() -> None:
    cap1 = uuid4()
    # Even though the capability is present, Decommissioned takes precedence
    # over the not-present check (decommission guard ordered first in the decider).
    state = _asset(lifecycle=AssetLifecycle.DECOMMISSIONED, family_ids=frozenset({cap1}))
    with pytest.raises(AssetCannotRemoveFamilyError) as exc_info:
        remove_asset_family.decide(
            state=state,
            command=RemoveAssetFamily(asset_id=state.id, family_id=cap1),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.family_id == cap1
    assert "Decommissioned" in exc_info.value.reason


@pytest.mark.unit
def test_decide_raises_cannot_remove_when_capability_not_present() -> None:
    """Strict-not-idempotent: removing a capability not in the set
    raises rather than no-op."""
    cap_present = uuid4()
    cap_absent = uuid4()
    state = _asset(family_ids=frozenset({cap_present}))
    with pytest.raises(AssetCannotRemoveFamilyError) as exc_info:
        remove_asset_family.decide(
            state=state,
            command=RemoveAssetFamily(asset_id=state.id, family_id=cap_absent),
            now=_NOW,
        )
    assert exc_info.value.family_id == cap_absent
    assert "not in" in exc_info.value.reason


@pytest.mark.unit
@pytest.mark.parametrize(
    "lifecycle",
    [
        AssetLifecycle.COMMISSIONED,
        AssetLifecycle.ACTIVE,
        AssetLifecycle.MAINTENANCE,
    ],
)
def test_decide_succeeds_for_every_non_decommissioned_lifecycle(
    lifecycle: AssetLifecycle,
) -> None:
    cap1 = uuid4()
    state = _asset(lifecycle=lifecycle, family_ids=frozenset({cap1}))
    events = remove_asset_family.decide(
        state=state,
        command=RemoveAssetFamily(asset_id=state.id, family_id=cap1),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].family_id == cap1


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    cap1 = uuid4()
    state = _asset(family_ids=frozenset({cap1}))
    command = RemoveAssetFamily(asset_id=state.id, family_id=cap1)
    first = remove_asset_family.decide(state=state, command=command, now=_NOW)
    second = remove_asset_family.decide(state=state, command=command, now=_NOW)
    assert first == second
