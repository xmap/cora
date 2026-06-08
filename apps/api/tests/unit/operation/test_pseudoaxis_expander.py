"""Unit tests for `expand_pseudoaxis_steps`.

Pre-Conductor step expansion: walks a Step tuple, rewrites every
`SetpointStep` whose address starts with `pseudoaxis://` into N
sequential constituent `SetpointStep`s addressed
`epics_ca://<id>/setpoint`, and passes every other step
(ActionStep, CheckStep, non-PseudoAxis SetpointStep) through
unchanged. Coverage focus: pass-through invariants, single-rewrite
fan-out, default-resolver wiring-deferred error, multiple
independent rewrites, ordering preservation across mixed step
sequences.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates._partition_rule import Affine, Aggregation, AggregatorKind
from cora.equipment.aggregates.asset.events import (
    AssetFamilyAdded,
    AssetPartitionRuleUpdated,
    AssetRegistered,
    event_type_name,
    to_payload,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.operation._pseudoaxis_expander import expand_pseudoaxis_steps
from cora.operation.conductor import (
    ActionStep,
    CheckStep,
    EqualsCriterion,
    SetpointStep,
    Step,
)
from cora.operation.errors import PartitionRuleNotFoundError
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_PSEUDOAXIS_FAMILY_ID = UUID("01900000-0000-7000-8000-00000000f001")
_AFFINE_ASSET_ID = UUID("01900000-0000-7000-8000-00000000c001")
_AGGREGATION_ASSET_ID = UUID("01900000-0000-7000-8000-00000000c002")
_AFFINE_CONSTITUENT_ID = UUID("01900000-0000-7000-8000-00000000d001")
_AGG_CONSTITUENT_A = UUID("01900000-0000-7000-8000-00000000d002")
_AGG_CONSTITUENT_B = UUID("01900000-0000-7000-8000-00000000d003")


async def _seed_pseudoaxis_asset(
    store: InMemoryEventStore,
    *,
    asset_id: UUID,
    partition_rule: Affine | Aggregation,
) -> None:
    """Append AssetRegistered + AssetFamilyAdded + AssetPartitionRuleUpdated.

    Seeds the Asset directly through the event store so the test
    bypasses handler wiring and exercises the expander in isolation.
    Family attachment is preserved as scaffolding for the seeded
    Asset's audit trail; the expander self-gates on `partition_rule
    is not None` and does not consult Family membership.
    """
    registered = AssetRegistered(
        asset_id=asset_id,
        name="VirtualAxis",
        level="Device",
        parent_id=UUID("01900000-0000-7000-8000-00000000b000"),
        occurred_at=_NOW,
        commissioned_by=ActorId(uuid4()),
    )
    family_added = AssetFamilyAdded(
        asset_id=asset_id,
        family_id=_PSEUDOAXIS_FAMILY_ID,
        occurred_at=_NOW,
    )
    rule_set = AssetPartitionRuleUpdated(
        asset_id=asset_id,
        partition_rule=partition_rule,
        occurred_at=_NOW,
    )
    events = [
        to_new_event(
            event_type=event_type_name(registered),
            payload=to_payload(registered),
            occurred_at=_NOW,
            event_id=uuid4(),
            command_name="RegisterAsset",
            correlation_id=_CORRELATION_ID,
            principal_id=_PRINCIPAL_ID,
        ),
        to_new_event(
            event_type=event_type_name(family_added),
            payload=to_payload(family_added),
            occurred_at=_NOW,
            event_id=uuid4(),
            command_name="AddAssetFamily",
            correlation_id=_CORRELATION_ID,
            principal_id=_PRINCIPAL_ID,
        ),
        to_new_event(
            event_type=event_type_name(rule_set),
            payload=to_payload(rule_set),
            occurred_at=_NOW,
            event_id=uuid4(),
            command_name="UpdateAssetPartitionRule",
            correlation_id=_CORRELATION_ID,
            principal_id=_PRINCIPAL_ID,
        ),
    ]
    await store.append(
        stream_type="Asset",
        stream_id=asset_id,
        expected_version=0,
        events=events,
    )


def _pseudoaxis_address(asset_id: UUID) -> str:
    return f"pseudoaxis://{asset_id}/virtual"


def _constituent_address(asset_id: UUID) -> str:
    return f"epics_ca://{asset_id}/setpoint"


@pytest.mark.unit
async def test_expander_passes_through_action_step_unchanged() -> None:
    store = InMemoryEventStore()
    steps: tuple[Step, ...] = (ActionStep(name="open_shutter", params={"timeout": 5.0}),)

    result = await expand_pseudoaxis_steps(
        steps,
        event_store=store,
        correlation_id=_CORRELATION_ID,
    )

    assert result == steps


@pytest.mark.unit
async def test_expander_passes_through_check_step_unchanged() -> None:
    store = InMemoryEventStore()
    steps: tuple[Step, ...] = (
        CheckStep(address="epics_ca://motor-1/readback", criterion=EqualsCriterion(expected=0.0)),
    )

    result = await expand_pseudoaxis_steps(
        steps,
        event_store=store,
        correlation_id=_CORRELATION_ID,
    )

    assert result == steps


@pytest.mark.unit
async def test_expander_passes_through_non_pseudoaxis_setpoint_unchanged() -> None:
    store = InMemoryEventStore()
    steps: tuple[Step, ...] = (
        SetpointStep(address="epics_ca://motor-1/setpoint", value=1.0, verify=True),
    )

    result = await expand_pseudoaxis_steps(
        steps,
        event_store=store,
        correlation_id=_CORRELATION_ID,
    )

    assert result == steps


@pytest.mark.unit
async def test_expander_emits_one_constituent_setpoint_for_affine_rewrite() -> None:
    store = InMemoryEventStore()
    await _seed_pseudoaxis_asset(
        store,
        asset_id=_AFFINE_ASSET_ID,
        partition_rule=Affine(gain=2.0, offset=1.0),
    )
    steps: tuple[Step, ...] = (
        SetpointStep(address=_pseudoaxis_address(_AFFINE_ASSET_ID), value=3.0, verify=True),
    )

    result = await expand_pseudoaxis_steps(
        steps,
        event_store=store,
        correlation_id=_CORRELATION_ID,
        constituent_resolver=lambda _aid: (_AFFINE_CONSTITUENT_ID,),
    )

    assert len(result) == 1
    rewritten = result[0]
    assert isinstance(rewritten, SetpointStep)
    assert rewritten.address == _constituent_address(_AFFINE_CONSTITUENT_ID)
    assert rewritten.value == 7.0
    assert rewritten.verify is False


@pytest.mark.unit
async def test_expander_emits_n_constituent_setpoints_for_aggregation_rewrite() -> None:
    store = InMemoryEventStore()
    await _seed_pseudoaxis_asset(
        store,
        asset_id=_AGGREGATION_ASSET_ID,
        partition_rule=Aggregation(aggregator_kind=AggregatorKind.SUM, constituent_count=2),
    )
    constituents = (_AGG_CONSTITUENT_A, _AGG_CONSTITUENT_B)
    steps: tuple[Step, ...] = (
        SetpointStep(address=_pseudoaxis_address(_AGGREGATION_ASSET_ID), value=4.0),
    )

    result = await expand_pseudoaxis_steps(
        steps,
        event_store=store,
        correlation_id=_CORRELATION_ID,
        constituent_resolver=lambda _aid: constituents,
    )

    assert len(result) == 2
    first, second = result
    assert isinstance(first, SetpointStep)
    assert isinstance(second, SetpointStep)
    assert first.address == _constituent_address(_AGG_CONSTITUENT_A)
    assert second.address == _constituent_address(_AGG_CONSTITUENT_B)
    assert first.value == 2.0
    assert second.value == 2.0
    assert first.verify is False
    assert second.verify is False


@pytest.mark.unit
async def test_expander_default_resolver_raises_partition_rule_not_found_error() -> None:
    store = InMemoryEventStore()
    await _seed_pseudoaxis_asset(
        store,
        asset_id=_AFFINE_ASSET_ID,
        partition_rule=Affine(gain=2.0, offset=1.0),
    )
    steps: tuple[Step, ...] = (
        SetpointStep(address=_pseudoaxis_address(_AFFINE_ASSET_ID), value=3.0),
    )

    with pytest.raises(PartitionRuleNotFoundError) as exc_info:
        await expand_pseudoaxis_steps(
            steps,
            event_store=store,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.asset_id == _AFFINE_ASSET_ID


@pytest.mark.unit
async def test_expander_rewrites_multiple_pseudoaxis_steps_independently() -> None:
    store = InMemoryEventStore()
    await _seed_pseudoaxis_asset(
        store,
        asset_id=_AFFINE_ASSET_ID,
        partition_rule=Affine(gain=2.0, offset=1.0),
    )
    await _seed_pseudoaxis_asset(
        store,
        asset_id=_AGGREGATION_ASSET_ID,
        partition_rule=Aggregation(aggregator_kind=AggregatorKind.SUM, constituent_count=2),
    )
    agg_constituents = (_AGG_CONSTITUENT_A, _AGG_CONSTITUENT_B)

    def _resolver(asset_id: UUID) -> tuple[UUID, ...]:
        if asset_id == _AFFINE_ASSET_ID:
            return (_AFFINE_CONSTITUENT_ID,)
        return agg_constituents

    steps: tuple[Step, ...] = (
        SetpointStep(address=_pseudoaxis_address(_AFFINE_ASSET_ID), value=3.0),
        SetpointStep(address=_pseudoaxis_address(_AGGREGATION_ASSET_ID), value=4.0),
    )

    result = await expand_pseudoaxis_steps(
        steps,
        event_store=store,
        correlation_id=_CORRELATION_ID,
        constituent_resolver=_resolver,
    )

    assert len(result) == 3
    affine_step, agg_first, agg_second = result
    assert isinstance(affine_step, SetpointStep)
    assert isinstance(agg_first, SetpointStep)
    assert isinstance(agg_second, SetpointStep)
    assert affine_step.address == _constituent_address(_AFFINE_CONSTITUENT_ID)
    assert affine_step.value == 7.0
    assert agg_first.address == _constituent_address(_AGG_CONSTITUENT_A)
    assert agg_second.address == _constituent_address(_AGG_CONSTITUENT_B)
    assert agg_first.value == 2.0
    assert agg_second.value == 2.0


@pytest.mark.unit
async def test_expander_preserves_surrounding_steps_between_expansions() -> None:
    store = InMemoryEventStore()
    await _seed_pseudoaxis_asset(
        store,
        asset_id=_AFFINE_ASSET_ID,
        partition_rule=Affine(gain=2.0, offset=1.0),
    )
    await _seed_pseudoaxis_asset(
        store,
        asset_id=_AGGREGATION_ASSET_ID,
        partition_rule=Aggregation(aggregator_kind=AggregatorKind.SUM, constituent_count=2),
    )
    agg_constituents = (_AGG_CONSTITUENT_A, _AGG_CONSTITUENT_B)
    open_shutter = ActionStep(name="open_shutter")
    readback_check = CheckStep(
        address="epics_ca://detector-1/readback",
        criterion=EqualsCriterion(expected=1.0),
    )
    plain_setpoint = SetpointStep(address="epics_ca://motor-2/setpoint", value=5.0)

    def _resolver(asset_id: UUID) -> tuple[UUID, ...]:
        if asset_id == _AFFINE_ASSET_ID:
            return (_AFFINE_CONSTITUENT_ID,)
        return agg_constituents

    steps: tuple[Step, ...] = (
        open_shutter,
        SetpointStep(address=_pseudoaxis_address(_AFFINE_ASSET_ID), value=3.0),
        readback_check,
        SetpointStep(address=_pseudoaxis_address(_AGGREGATION_ASSET_ID), value=4.0),
        plain_setpoint,
    )

    result = await expand_pseudoaxis_steps(
        steps,
        event_store=store,
        correlation_id=_CORRELATION_ID,
        constituent_resolver=_resolver,
    )

    assert len(result) == 6
    assert result[0] is open_shutter
    assert isinstance(result[1], SetpointStep)
    assert result[1].address == _constituent_address(_AFFINE_CONSTITUENT_ID)
    assert result[1].value == 7.0
    assert result[2] is readback_check
    assert isinstance(result[3], SetpointStep)
    assert result[3].address == _constituent_address(_AGG_CONSTITUENT_A)
    assert result[3].value == 2.0
    assert isinstance(result[4], SetpointStep)
    assert result[4].address == _constituent_address(_AGG_CONSTITUENT_B)
    assert result[4].value == 2.0
    assert result[5] is plain_setpoint
