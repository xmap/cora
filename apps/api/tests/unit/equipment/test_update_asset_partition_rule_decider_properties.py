"""Property-based tests for `update_asset_partition_rule.decide`.

Complements example-based decider tests with universal claims across
generated inputs. The decider's pure shape

    (state, command, now) -> list[AssetPartitionRuleUpdated]

makes the slice's invariants mechanical to express:

  - Any non-Decommissioned Asset + any PartitionRule (or None) whose
    value differs from the current rule -> exactly one
    AssetPartitionRuleUpdated carrying the injected rule and timestamp.
  - Decommissioned Asset -> AssetCannotUpdatePartitionRuleError
    regardless of the proposed rule (lifecycle guard fires first).
  - state=None -> AssetNotFoundError regardless of the proposed rule.
  - Idempotency: current state.partition_rule == command.partition_rule
    -> decider returns [].

Codec / round-trip properties for the PartitionRule shapes themselves
live in test_partition_rule.py; this file pins decider behavior only.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.equipment.aggregates._partition_rule import (
    Affine,
    Aggregation,
    AggregatorKind,
    PartitionRule,
)
from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotUpdatePartitionRuleError,
    AssetLevel,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetPartitionRuleUpdated,
)
from cora.equipment.features import update_asset_partition_rule
from cora.equipment.features.update_asset_partition_rule import UpdateAssetPartitionRule

if TYPE_CHECKING:
    from uuid import UUID

_NON_DECOMMISSIONED_LIFECYCLE = st.sampled_from(
    [lc for lc in AssetLifecycle if lc is not AssetLifecycle.DECOMMISSIONED]
)
_FINITE_FLOAT = st.floats(allow_nan=False, allow_infinity=False, width=32)
_DT_BASE = datetime(2026, 6, 5, 0, 0, 0, tzinfo=UTC)


@st.composite
def _affine(draw: st.DrawFn) -> Affine:
    return Affine(
        gain=draw(_FINITE_FLOAT),
        offset=draw(_FINITE_FLOAT),
        unit_in=draw(st.sampled_from(["", "mm", "deg", "um"])),
        unit_out=draw(st.sampled_from(["", "mm", "deg", "um"])),
    )


@st.composite
def _aggregation(draw: st.DrawFn) -> Aggregation:
    aggregator_kind = draw(st.sampled_from(list(AggregatorKind)))
    if aggregator_kind in (AggregatorKind.DIFFERENCE, AggregatorKind.MID_RANGE):
        constituent_count = 2
    else:
        constituent_count = draw(st.integers(min_value=1, max_value=6))
    return Aggregation(
        aggregator_kind=aggregator_kind,
        constituent_count=constituent_count,
    )


_PARTITION_RULE: st.SearchStrategy[PartitionRule] = st.one_of(_affine(), _aggregation())
_PARTITION_RULE_OR_NONE: st.SearchStrategy[PartitionRule | None] = st.one_of(
    st.none(), _PARTITION_RULE
)


def _asset(
    asset_id: UUID,
    *,
    lifecycle: AssetLifecycle,
    partition_rule: PartitionRule | None,
) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("PseudoAxis-A"),
        level=AssetLevel.DEVICE,
        parent_id=asset_id,  # any UUID; non-Enterprise requires non-null
        lifecycle=lifecycle,
        partition_rule=partition_rule,
    )


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    current_rule=_PARTITION_RULE_OR_NONE,
    new_rule=_PARTITION_RULE_OR_NONE,
    lifecycle=_NON_DECOMMISSIONED_LIFECYCLE,
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_changing_rule_emits_one_event_with_injected_fields(
    asset_id: UUID,
    current_rule: PartitionRule | None,
    new_rule: PartitionRule | None,
    lifecycle: AssetLifecycle,
    seconds_offset: int,
) -> None:
    """Non-Decommissioned state + new rule differs from current ->
    single AssetPartitionRuleUpdated with the injected rule and
    timestamp."""
    assume(current_rule != new_rule)
    state = _asset(asset_id, lifecycle=lifecycle, partition_rule=current_rule)
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    events = update_asset_partition_rule.decide(
        state=state,
        command=UpdateAssetPartitionRule(asset_id=asset_id, partition_rule=new_rule),
        now=now,
    )
    assert events == [
        AssetPartitionRuleUpdated(
            asset_id=asset_id,
            partition_rule=new_rule,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    rule=_PARTITION_RULE_OR_NONE,
    lifecycle=_NON_DECOMMISSIONED_LIFECYCLE,
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_unchanged_rule_returns_no_events(
    asset_id: UUID,
    rule: PartitionRule | None,
    lifecycle: AssetLifecycle,
    seconds_offset: int,
) -> None:
    """Idempotent re-submission: command.partition_rule equal to the
    current state.partition_rule -> decider returns []. Holds whether
    the rule is None or any concrete shape."""
    state = _asset(asset_id, lifecycle=lifecycle, partition_rule=rule)
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    events = update_asset_partition_rule.decide(
        state=state,
        command=UpdateAssetPartitionRule(asset_id=asset_id, partition_rule=rule),
        now=now,
    )
    assert events == []


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    current_rule=_PARTITION_RULE_OR_NONE,
    new_rule=_PARTITION_RULE_OR_NONE,
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_decommissioned_asset_always_raises_cannot_update(
    asset_id: UUID,
    current_rule: PartitionRule | None,
    new_rule: PartitionRule | None,
    seconds_offset: int,
) -> None:
    """Lifecycle guard fires regardless of whether the new rule equals
    the current rule: Decommissioned Assets reject all partition-rule
    updates to preserve the audit trail of the final-state rule that
    was in effect at decommissioning."""
    state = _asset(
        asset_id,
        lifecycle=AssetLifecycle.DECOMMISSIONED,
        partition_rule=current_rule,
    )
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    with pytest.raises(AssetCannotUpdatePartitionRuleError) as exc:
        update_asset_partition_rule.decide(
            state=state,
            command=UpdateAssetPartitionRule(asset_id=asset_id, partition_rule=new_rule),
            now=now,
        )
    assert exc.value.asset_id == asset_id
    assert "Decommissioned" in exc.value.reason


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    rule=_PARTITION_RULE_OR_NONE,
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_state_none_always_raises_asset_not_found(
    asset_id: UUID,
    rule: PartitionRule | None,
    seconds_offset: int,
) -> None:
    """state=None -> AssetNotFoundError regardless of the proposed rule
    or timestamp; the not-found guard fires before the lifecycle guard."""
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    with pytest.raises(AssetNotFoundError) as exc:
        update_asset_partition_rule.decide(
            state=None,
            command=UpdateAssetPartitionRule(asset_id=asset_id, partition_rule=rule),
            now=now,
        )
    assert exc.value.asset_id == asset_id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    current_rule=_PARTITION_RULE_OR_NONE,
    new_rule=_PARTITION_RULE_OR_NONE,
    lifecycle=_NON_DECOMMISSIONED_LIFECYCLE,
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_decide_is_pure_same_input_same_output(
    asset_id: UUID,
    current_rule: PartitionRule | None,
    new_rule: PartitionRule | None,
    lifecycle: AssetLifecycle,
    seconds_offset: int,
) -> None:
    """Two calls with identical (state, command, now) return identical
    events; no hidden clock or id leakage."""
    state = _asset(asset_id, lifecycle=lifecycle, partition_rule=current_rule)
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    command = UpdateAssetPartitionRule(asset_id=asset_id, partition_rule=new_rule)
    first = update_asset_partition_rule.decide(state=state, command=command, now=now)
    second = update_asset_partition_rule.decide(state=state, command=command, now=now)
    assert first == second
