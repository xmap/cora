"""End-to-end integration test for PseudoAxis fan-out validation on
the `add_plan_wire` handler against `InMemoryEventStore`.

Exercises the full handler closure (Plan load + Asset loads + Family
name lookup for PseudoAxis membership + `validate_pseudoaxis_fanout`
call site) by seeding raw events for Family, Asset, and Plan streams
then driving the real `add_plan_wire.bind(deps)` handler.

Slice 3 contract reminder: the fan-out validator enforces STRICT
equality between the count of incoming wires that target the
PseudoAxis Asset's INPUT ports and the partition rule's declared
arity. Under-arity AND over-arity both raise
`PlanPseudoAxisArityMismatchError`. That means incremental wiring of
an N-constituent PseudoAxis Asset cannot proceed one wire at a time
when the rule is already set: each intermediate state (1 wire, 2
wires, ..., N-1 wires) is rejected. To stage the over-arity case the
tests seed the prior `PlanWireAdded` events directly into the Plan
stream before invoking the handler for the (N+1)-th wire.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates._partition_rule import (
    Affine,
    Aggregation,
    AggregatorKind,
)
from cora.equipment.aggregates.asset.events import (
    AssetFamilyAdded,
    AssetPartitionRuleUpdated,
    AssetPortAdded,
    AssetRegistered,
)
from cora.equipment.aggregates.asset.events import (
    event_type_name as asset_event_type_name,
)
from cora.equipment.aggregates.asset.events import (
    to_payload as asset_to_payload,
)
from cora.equipment.aggregates.family.affordance import Affordance
from cora.equipment.aggregates.family.events import FamilyDefined
from cora.equipment.aggregates.family.events import (
    event_type_name as family_event_type_name,
)
from cora.equipment.aggregates.family.events import (
    to_payload as family_to_payload,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.event_store import EventStore
from cora.recipe.aggregates.plan import (
    PlanPseudoAxisArityMismatchError,
    Wire,
    load_plan,
)
from cora.recipe.aggregates.plan.events import (
    PlanDefined,
    PlanWireAdded,
)
from cora.recipe.aggregates.plan.events import (
    event_type_name as plan_event_type_name,
)
from cora.recipe.aggregates.plan.events import (
    to_payload as plan_to_payload,
)
from cora.recipe.features import add_plan_wire
from cora.recipe.features.add_plan_wire import AddPlanWire
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_family(
    event_store: EventStore,
    family_id: UUID,
    *,
    name: str,
    affordances: frozenset[Affordance],
) -> None:
    event = FamilyDefined(
        family_id=family_id,
        name=name,
        occurred_at=_NOW,
        affordances=affordances,
    )
    await event_store.append(
        stream_type="Family",
        stream_id=family_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=family_event_type_name(event),
                payload=family_to_payload(event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="DefineFamily",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


async def _seed_asset(
    event_store: EventStore,
    asset_id: UUID,
    *,
    name: str,
    family_ids: tuple[UUID, ...],
    ports: tuple[tuple[str, str, str], ...],
    partition_rule: Affine | Aggregation | None = None,
) -> None:
    """Seed an Asset stream with family memberships, ports, and optional rule.

    `ports` items are `(port_name, direction, signal_type)` triples;
    direction strings mirror `PortDirection.value` (`"Input"` /
    `"Output"`). Asset.partition_rule applies only when the Asset is
    PseudoAxis-shaped; passing `None` leaves the rule unset.
    """
    events: list[
        AssetRegistered | AssetFamilyAdded | AssetPortAdded | AssetPartitionRuleUpdated
    ] = [
        AssetRegistered(
            asset_id=asset_id,
            name=name,
            level="Device",
            parent_id=None,
            occurred_at=_NOW,
        )
    ]
    for family_id in family_ids:
        events.append(
            AssetFamilyAdded(
                asset_id=asset_id,
                family_id=family_id,
                occurred_at=_NOW,
            )
        )
    for port_name, direction, signal_type in ports:
        events.append(
            AssetPortAdded(
                asset_id=asset_id,
                port_name=port_name,
                direction=direction,
                signal_type=signal_type,
                occurred_at=_NOW,
            )
        )
    if partition_rule is not None:
        events.append(
            AssetPartitionRuleUpdated(
                asset_id=asset_id,
                partition_rule=partition_rule,
                occurred_at=_NOW,
            )
        )
    new_events = [
        to_new_event(
            event_type=asset_event_type_name(ev),
            payload=asset_to_payload(ev),
            occurred_at=_NOW,
            event_id=uuid4(),
            command_name="Seed",
            correlation_id=_CORRELATION_ID,
            principal_id=_PRINCIPAL_ID,
        )
        for ev in events
    ]
    await event_store.append(
        stream_type="Asset",
        stream_id=asset_id,
        expected_version=0,
        events=new_events,
    )


async def _seed_plan_with_wires(
    event_store: EventStore,
    plan_id: UUID,
    *,
    asset_ids: tuple[UUID, ...],
    seeded_wires: tuple[Wire, ...] = (),
) -> None:
    """Seed a Plan stream with an optional list of pre-existing wires.

    The PlanDefined event lands first followed by one PlanWireAdded
    event per `seeded_wires` entry. Wires seeded this way bypass the
    `add_plan_wire` decider; the test uses this path only to stage
    pre-existing fan-out into a PseudoAxis target so the next handler
    invocation reaches the over-arity surface.
    """
    practice_id = uuid4()
    method_id = uuid4()
    define = PlanDefined(
        plan_id=plan_id,
        name="PseudoAxis FanOut Plan",
        practice_id=practice_id,
        asset_ids=asset_ids,
        method_id=method_id,
        method_needed_family_ids_snapshot=(),
        asset_families_snapshot={a: () for a in asset_ids},
        occurred_at=_NOW,
    )
    plan_events: list[PlanDefined | PlanWireAdded] = [define]
    for wire in seeded_wires:
        plan_events.append(
            PlanWireAdded(
                plan_id=plan_id,
                source_asset_id=wire.source_asset_id,
                source_port_name=wire.source_port_name,
                target_asset_id=wire.target_asset_id,
                target_port_name=wire.target_port_name,
                occurred_at=_NOW,
            )
        )
    new_events = [
        to_new_event(
            event_type=plan_event_type_name(ev),
            payload=plan_to_payload(ev),
            occurred_at=_NOW,
            event_id=uuid4(),
            command_name="Seed",
            correlation_id=_CORRELATION_ID,
            principal_id=_PRINCIPAL_ID,
        )
        for ev in plan_events
    ]
    await event_store.append(
        stream_type="Plan",
        stream_id=plan_id,
        expected_version=0,
        events=new_events,
    )


async def _seed_two_constituent_topology(
    deps: Kernel,
) -> tuple[UUID, UUID, UUID, UUID, UUID]:
    """Seed the two-arity PseudoAxis topology used by the over-arity test.

    Returns `(plan_id, pseudo_id, motor_a_id, motor_b_id, motor_c_id)`.
    The PseudoAxis Asset declares three INPUT ports (so the third leg
    can target a real port and reach the arity check) plus one OUTPUT
    port, with an `Aggregation(Sum, constituent_count=2)` rule. Three
    motors stand in for the constituents; the Plan binds all four
    Assets.
    """
    pseudoaxis_family_id = uuid4()
    linear_stage_family_id = uuid4()
    pseudo_id = uuid4()
    motor_a_id = uuid4()
    motor_b_id = uuid4()
    motor_c_id = uuid4()
    plan_id = uuid4()

    await _seed_family(
        deps.event_store,
        pseudoaxis_family_id,
        name="PseudoAxis",
        affordances=frozenset({Affordance.TRANSLATABLE}),
    )
    await _seed_family(
        deps.event_store,
        linear_stage_family_id,
        name="LinearStage",
        affordances=frozenset({Affordance.TRANSLATABLE}),
    )
    await _seed_asset(
        deps.event_store,
        pseudo_id,
        name="virtual_y_pseudoaxis",
        family_ids=(pseudoaxis_family_id,),
        ports=(
            ("constituent_in_0", "Input", "mm"),
            ("constituent_in_1", "Input", "mm"),
            ("constituent_in_2", "Input", "mm"),
            ("virtual_out", "Output", "mm"),
        ),
        partition_rule=Aggregation(
            aggregator_kind=AggregatorKind.SUM,
            constituent_count=2,
        ),
    )
    for motor_id, motor_name in (
        (motor_a_id, "motor_a"),
        (motor_b_id, "motor_b"),
        (motor_c_id, "motor_c"),
    ):
        await _seed_asset(
            deps.event_store,
            motor_id,
            name=motor_name,
            family_ids=(linear_stage_family_id,),
            ports=(("readback_out", "Output", "mm"),),
        )

    pre_wires = (
        Wire(
            source_asset_id=motor_a_id,
            source_port_name="readback_out",
            target_asset_id=pseudo_id,
            target_port_name="constituent_in_0",
        ),
        Wire(
            source_asset_id=motor_b_id,
            source_port_name="readback_out",
            target_asset_id=pseudo_id,
            target_port_name="constituent_in_1",
        ),
    )
    await _seed_plan_with_wires(
        deps.event_store,
        plan_id,
        asset_ids=(pseudo_id, motor_a_id, motor_b_id, motor_c_id),
        seeded_wires=pre_wires,
    )
    return plan_id, pseudo_id, motor_a_id, motor_b_id, motor_c_id


@pytest.mark.integration
async def test_add_plan_wire_single_constituent_rule_accepts_first_wire_to_pseudoaxis() -> None:
    """Affine declares arity 1: the first (and only) constituent wire
    lands without raising. Exercises the happy path through the
    PseudoAxis branch when the count after the add equals expected."""
    pseudoaxis_family_id = uuid4()
    linear_stage_family_id = uuid4()
    pseudo_id = uuid4()
    motor_a_id = uuid4()
    plan_id = uuid4()

    deps = build_deps(ids=[uuid4()])

    await _seed_family(
        deps.event_store,
        pseudoaxis_family_id,
        name="PseudoAxis",
        affordances=frozenset({Affordance.TRANSLATABLE}),
    )
    await _seed_family(
        deps.event_store,
        linear_stage_family_id,
        name="LinearStage",
        affordances=frozenset({Affordance.TRANSLATABLE}),
    )
    await _seed_asset(
        deps.event_store,
        pseudo_id,
        name="virtual_y_pseudoaxis",
        family_ids=(pseudoaxis_family_id,),
        ports=(
            ("constituent_in_0", "Input", "mm"),
            ("virtual_out", "Output", "mm"),
        ),
        partition_rule=Affine(gain=1.0, offset=0.0, unit_in="mm", unit_out="mm"),
    )
    await _seed_asset(
        deps.event_store,
        motor_a_id,
        name="motor_a",
        family_ids=(linear_stage_family_id,),
        ports=(("readback_out", "Output", "mm"),),
    )
    await _seed_plan_with_wires(
        deps.event_store,
        plan_id,
        asset_ids=(pseudo_id, motor_a_id),
    )

    await add_plan_wire.bind(deps)(
        AddPlanWire(
            plan_id=plan_id,
            source_asset_id=motor_a_id,
            source_port_name="readback_out",
            target_asset_id=pseudo_id,
            target_port_name="constituent_in_0",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    loaded = await load_plan(deps.event_store, plan_id)
    assert loaded is not None
    assert loaded.wires == frozenset(
        {
            Wire(
                source_asset_id=motor_a_id,
                source_port_name="readback_out",
                target_asset_id=pseudo_id,
                target_port_name="constituent_in_0",
            )
        }
    )


@pytest.mark.integration
async def test_add_plan_wire_over_arity_third_wire_raises_arity_mismatch() -> None:
    """Two wires already target the PseudoAxis Asset's first two
    constituent ports; the rule declares `constituent_count=2`.
    Adding a third constituent wire (port `constituent_in_2`,
    distinct source) trips the over-arity branch of
    `PlanPseudoAxisArityMismatchError`."""
    deps = build_deps(ids=[uuid4()])
    plan_id, pseudo_id, _motor_a_id, _motor_b_id, motor_c_id = await _seed_two_constituent_topology(
        deps
    )

    with pytest.raises(PlanPseudoAxisArityMismatchError) as exc_info:
        await add_plan_wire.bind(deps)(
            AddPlanWire(
                plan_id=plan_id,
                source_asset_id=motor_c_id,
                source_port_name="readback_out",
                target_asset_id=pseudo_id,
                target_port_name="constituent_in_2",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.pseudoaxis_asset_id == pseudo_id
    assert exc_info.value.expected_constituent_count == 2
    assert exc_info.value.actual_input_wire_count == 3
    assert exc_info.value.rule_kind == "Aggregation"

    loaded = await load_plan(deps.event_store, plan_id)
    assert loaded is not None
    assert len(loaded.wires) == 2
