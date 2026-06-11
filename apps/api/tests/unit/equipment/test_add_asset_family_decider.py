"""Unit tests for the `add_asset_family` slice's pure decider.

Two disqualifying conditions both surface as
`AssetCannotAddFamilyError` with a diagnostic `reason` string
(mirrors the relocate decider's collapsed-conditions pattern):

  - asset is `Decommissioned`
  - capability already in `state.family_ids` (strict-not-idempotent)
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

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
def test_decide_emits_asset_capability_added_for_active_asset_without_capability() -> None:
    state = _asset(lifecycle=AssetLifecycle.ACTIVE, family_ids=frozenset())
    new_cap = uuid4()
    events = add_asset_family.decide(
        state=state,
        command=AddAssetFamily(asset_id=state.id, family_id=new_cap),
        now=_NOW,
    )
    assert events == [AssetFamilyAdded(asset_id=state.id, family_id=new_cap, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        add_asset_family.decide(
            state=None,
            command=AddAssetFamily(asset_id=target_id, family_id=uuid4()),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_add_when_asset_is_decommissioned() -> None:
    """Retired-from-service assets cannot accept new capabilities."""
    state = _asset(lifecycle=AssetLifecycle.DECOMMISSIONED)
    new_cap = uuid4()
    with pytest.raises(AssetCannotAddFamilyError) as exc_info:
        add_asset_family.decide(
            state=state,
            command=AddAssetFamily(asset_id=state.id, family_id=new_cap),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.family_id == new_cap
    assert "Decommissioned" in exc_info.value.reason


@pytest.mark.unit
def test_decide_raises_cannot_add_when_capability_already_present() -> None:
    """Strict-not-idempotent: re-adding a capability already in the set
    raises rather than no-op. Operator can detect 'wait, this is
    already commissioned' rather than silently no-op."""
    cap1 = uuid4()
    state = _asset(family_ids=frozenset({cap1}))
    with pytest.raises(AssetCannotAddFamilyError) as exc_info:
        add_asset_family.decide(
            state=state,
            command=AddAssetFamily(asset_id=state.id, family_id=cap1),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.family_id == cap1
    assert "already" in exc_info.value.reason


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
    """Family changes are allowed in every lifecycle state EXCEPT
    Decommissioned. Pinned: a future change that narrowed the
    allowed-lifecycle set would silently break commissioning workflows
    (which often happen pre-Active during install/test phases)."""
    state = _asset(lifecycle=lifecycle, family_ids=frozenset())
    new_cap = uuid4()
    events = add_asset_family.decide(
        state=state,
        command=AddAssetFamily(asset_id=state.id, family_id=new_cap),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].family_id == new_cap


@pytest.mark.unit
def test_decide_does_not_validate_capability_existence() -> None:
    """Eventual-consistency stance: decider does NOT verify the
    referenced Family id refers to a real Family stream. Same
    precedent as Trust Conduit zone refs (3b) and
    Method.needed_family_ids (6a)."""
    state = _asset()
    bogus_cap = uuid4()
    events = add_asset_family.decide(
        state=state,
        command=AddAssetFamily(asset_id=state.id, family_id=bogus_cap),
        now=_NOW,
    )
    assert events[0].family_id == bogus_cap


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _asset()
    cap = uuid4()
    command = AddAssetFamily(asset_id=state.id, family_id=cap)
    first = add_asset_family.decide(state=state, command=command, now=_NOW)
    second = add_asset_family.decide(state=state, command=command, now=_NOW)
    assert first == second
