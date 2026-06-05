"""Unit tests for the `update_asset_partition_rule` slice's pure decider.

The decider:
  - Raises AssetNotFoundError on empty state
  - Raises AssetCannotUpdatePartitionRuleError when the Asset is
    Decommissioned (immutable once retired)
  - No-ops (returns []) when the new rule equals the current rule
    (idempotent re-submission carries no audit value)
  - Otherwise emits AssetPartitionRuleUpdated with the command's
    partition_rule payload (None clears)

Genesis (None -> rule), mutation (rule -> rule'), and clearing
(rule -> None) all flow through the same event, mirroring the
AssetSettingsUpdated precedent. Cross-aggregate invariants
(Family membership, constituent existence, nesting prevention,
Calibration revision availability) live in the handler tier per
the cross-aggregate-validating-create pattern; the decider stays
pure and operates only on Asset state.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates._partition_rule import Affine, PartitionRule
from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotUpdatePartitionRuleError,
    AssetCondition,
    AssetLevel,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetPartitionRuleUpdated,
)
from cora.equipment.features import update_asset_partition_rule
from cora.equipment.features.update_asset_partition_rule import (
    UpdateAssetPartitionRule,
)

_NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


def _asset(
    *,
    partition_rule: PartitionRule | None = None,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
) -> Asset:
    family_id = uuid4()
    return Asset(
        id=uuid4(),
        name=AssetName("PseudoAxis-Y"),
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        condition=AssetCondition.NOMINAL,
        family_ids=frozenset({family_id}),
        partition_rule=partition_rule,
    )


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        update_asset_partition_rule.decide(
            state=None,
            command=UpdateAssetPartitionRule(
                asset_id=target_id,
                partition_rule=Affine(gain=2.0, offset=0.0),
            ),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_update_when_asset_is_decommissioned() -> None:
    state = _asset(lifecycle=AssetLifecycle.DECOMMISSIONED)
    with pytest.raises(AssetCannotUpdatePartitionRuleError) as exc_info:
        update_asset_partition_rule.decide(
            state=state,
            command=UpdateAssetPartitionRule(
                asset_id=state.id,
                partition_rule=Affine(gain=2.0, offset=0.0),
            ),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id


@pytest.mark.unit
def test_decide_no_op_when_rule_equals_current_rule() -> None:
    rule = Affine(gain=1.5, offset=0.25, unit_in="mm", unit_out="deg")
    state = _asset(partition_rule=rule)
    events = update_asset_partition_rule.decide(
        state=state,
        command=UpdateAssetPartitionRule(asset_id=state.id, partition_rule=rule),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_decide_no_op_when_clearing_already_absent_rule() -> None:
    state = _asset(partition_rule=None)
    events = update_asset_partition_rule.decide(
        state=state,
        command=UpdateAssetPartitionRule(asset_id=state.id, partition_rule=None),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_decide_emits_event_when_setting_first_rule() -> None:
    state = _asset(partition_rule=None)
    rule = Affine(gain=2.0, offset=0.0, unit_in="mm", unit_out="deg")
    events = update_asset_partition_rule.decide(
        state=state,
        command=UpdateAssetPartitionRule(asset_id=state.id, partition_rule=rule),
        now=_NOW,
    )
    assert events == [
        AssetPartitionRuleUpdated(
            asset_id=state.id,
            partition_rule=rule,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_emits_event_when_mutating_existing_rule() -> None:
    state = _asset(partition_rule=Affine(gain=1.0, offset=0.0))
    new_rule = Affine(gain=3.5, offset=1.0)
    events = update_asset_partition_rule.decide(
        state=state,
        command=UpdateAssetPartitionRule(asset_id=state.id, partition_rule=new_rule),
        now=_NOW,
    )
    assert events == [
        AssetPartitionRuleUpdated(
            asset_id=state.id,
            partition_rule=new_rule,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_emits_event_when_clearing_existing_rule() -> None:
    state = _asset(partition_rule=Affine(gain=2.0, offset=0.0))
    events = update_asset_partition_rule.decide(
        state=state,
        command=UpdateAssetPartitionRule(asset_id=state.id, partition_rule=None),
        now=_NOW,
    )
    assert events == [
        AssetPartitionRuleUpdated(
            asset_id=state.id,
            partition_rule=None,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _asset(partition_rule=None)
    command = UpdateAssetPartitionRule(
        asset_id=state.id,
        partition_rule=Affine(gain=2.0, offset=0.0),
    )
    first = update_asset_partition_rule.decide(state=state, command=command, now=_NOW)
    second = update_asset_partition_rule.decide(state=state, command=command, now=_NOW)
    assert first == second
