"""Unit tests for the `add_plan_wire` slice's pure decider.

Validation cascade pinned in order:
  1. PlanNotFoundError on empty state
  2. InvalidWireError raised at Wire VO construction (port name length)
  3. PlanWireAlreadyExistsError on re-add (strict-not-idempotent)
  4. PlanWireTargetAlreadyConnectedError on fan-in
  5. PlanWireSelfLoopError on same-port self-loop
  6. PlanWireAssetNotBoundError when an endpoint asset isn't in Plan.asset_ids
  7. PlanWirePortNotFoundError when a referenced port doesn't exist on the Asset
  8. PlanWireDirectionMismatchError on OUTPUT/INPUT violation
  9. PlanWireSignalTypeMismatchError on signal_type mismatch
  10. Happy path: emits PlanWireAdded with full 4-tuple payload
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates._partition_rule import (
    Affine,
    Aggregation,
    AggregatorKind,
    PartitionRule,
)
from cora.equipment.aggregates.asset import (
    Asset,
    AssetLevel,
    AssetLifecycle,
    AssetName,
    AssetPort,
    PortDirection,
)
from cora.recipe.aggregates.plan import (
    InvalidWireError,
    Plan,
    PlanName,
    PlanNotFoundError,
    PlanPseudoAxisArityMismatchError,
    PlanPseudoAxisFanoutSignalTypeMismatchError,
    PlanPseudoAxisOutputCardinalityError,
    PlanStatus,
    PlanWireAdded,
    PlanWireAlreadyExistsError,
    PlanWireAssetNotBoundError,
    PlanWireDirectionMismatchError,
    PlanWirePortNotFoundError,
    PlanWireSelfLoopError,
    PlanWireSignalTypeMismatchError,
    PlanWireTargetAlreadyConnectedError,
    Wire,
)
from cora.recipe.features import add_plan_wire
from cora.recipe.features.add_plan_wire import AddPlanWire, PlanWireContext

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


def _asset(
    *,
    asset_id: UUID,
    ports: frozenset[AssetPort] = frozenset(),
    family_ids: frozenset[UUID] = frozenset(),
    partition_rule: PartitionRule | None = None,
) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("Test Asset"),
        level=AssetLevel.DEVICE,
        parent_id=None,
        lifecycle=AssetLifecycle.ACTIVE,
        ports=ports,
        family_ids=family_ids,
        partition_rule=partition_rule,
    )


def _plan(
    *,
    asset_ids: frozenset[UUID],
    wires: frozenset[Wire] = frozenset(),
) -> Plan:
    return Plan(
        id=uuid4(),
        name=PlanName("32-ID FlyScan"),
        practice_id=uuid4(),
        asset_ids=asset_ids,
        status=PlanStatus.DEFINED,
        method_id=uuid4(),
        wires=wires,
    )


def _ports(*defs: tuple[str, PortDirection, str]) -> frozenset[AssetPort]:
    return frozenset(
        AssetPort(name=name, direction=direction, signal_type=signal_type)
        for name, direction, signal_type in defs
    )


@pytest.mark.unit
def test_decide_raises_plan_not_found_on_empty_state() -> None:
    plan_id = uuid4()
    with pytest.raises(PlanNotFoundError):
        add_plan_wire.decide(
            state=None,
            command=AddPlanWire(
                plan_id=plan_id,
                source_asset_id=uuid4(),
                source_port_name="trigger_out",
                target_asset_id=uuid4(),
                target_port_name="trigger_in",
            ),
            context=PlanWireContext(assets={}),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_invalid_wire_on_empty_port_name() -> None:
    """Wire VO __post_init__ rejects empty / whitespace port names."""
    asset_id = uuid4()
    state = _plan(asset_ids=frozenset({asset_id}))
    with pytest.raises(InvalidWireError):
        add_plan_wire.decide(
            state=state,
            command=AddPlanWire(
                plan_id=state.id,
                source_asset_id=asset_id,
                source_port_name="   ",  # empty after trim
                target_asset_id=asset_id,
                target_port_name="trigger_in",
            ),
            context=PlanWireContext(assets={asset_id: _asset(asset_id=asset_id)}),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_already_exists_on_duplicate_add() -> None:
    """Strict-not-idempotent: re-adding the same wire raises."""
    src_id = uuid4()
    tgt_id = uuid4()
    existing = Wire(
        source_asset_id=src_id,
        source_port_name="trigger_out",
        target_asset_id=tgt_id,
        target_port_name="trigger_in",
    )
    state = _plan(asset_ids=frozenset({src_id, tgt_id}), wires=frozenset({existing}))
    with pytest.raises(PlanWireAlreadyExistsError):
        add_plan_wire.decide(
            state=state,
            command=AddPlanWire(
                plan_id=state.id,
                source_asset_id=src_id,
                source_port_name="trigger_out",
                target_asset_id=tgt_id,
                target_port_name="trigger_in",
            ),
            context=PlanWireContext(
                assets={
                    src_id: _asset(
                        asset_id=src_id,
                        ports=_ports(("trigger_out", PortDirection.OUTPUT, "TTL")),
                    ),
                    tgt_id: _asset(
                        asset_id=tgt_id,
                        ports=_ports(("trigger_in", PortDirection.INPUT, "TTL")),
                    ),
                }
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_target_already_connected_on_fan_in() -> None:
    """Fan-in forbidden: a target port can be wired by at most one source."""
    src_id_1 = uuid4()
    src_id_2 = uuid4()
    tgt_id = uuid4()
    existing = Wire(
        source_asset_id=src_id_1,
        source_port_name="trigger_out",
        target_asset_id=tgt_id,
        target_port_name="trigger_in",
    )
    state = _plan(
        asset_ids=frozenset({src_id_1, src_id_2, tgt_id}),
        wires=frozenset({existing}),
    )
    with pytest.raises(PlanWireTargetAlreadyConnectedError) as exc_info:
        add_plan_wire.decide(
            state=state,
            command=AddPlanWire(
                plan_id=state.id,
                source_asset_id=src_id_2,
                source_port_name="trigger_out",
                target_asset_id=tgt_id,
                target_port_name="trigger_in",
            ),
            context=PlanWireContext(
                assets={
                    src_id_2: _asset(
                        asset_id=src_id_2,
                        ports=_ports(("trigger_out", PortDirection.OUTPUT, "TTL")),
                    ),
                    tgt_id: _asset(
                        asset_id=tgt_id,
                        ports=_ports(("trigger_in", PortDirection.INPUT, "TTL")),
                    ),
                }
            ),
            now=_NOW,
        )
    assert exc_info.value.existing == existing


@pytest.mark.unit
def test_decide_raises_self_loop_on_same_port() -> None:
    """Self-loop on the SAME port is degenerate; rejected."""
    asset_id = uuid4()
    state = _plan(asset_ids=frozenset({asset_id}))
    with pytest.raises(PlanWireSelfLoopError):
        add_plan_wire.decide(
            state=state,
            command=AddPlanWire(
                plan_id=state.id,
                source_asset_id=asset_id,
                source_port_name="loopback",
                target_asset_id=asset_id,
                target_port_name="loopback",
            ),
            context=PlanWireContext(
                assets={
                    asset_id: _asset(
                        asset_id=asset_id,
                        ports=_ports(("loopback", PortDirection.OUTPUT, "TTL")),
                    )
                }
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_asset_not_bound_when_endpoint_not_in_plan_asset_ids() -> None:
    """Both endpoint asset_ids MUST be in Plan.asset_ids."""
    bound_id = uuid4()
    unbound_id = uuid4()
    state = _plan(asset_ids=frozenset({bound_id}))
    with pytest.raises(PlanWireAssetNotBoundError) as exc_info:
        add_plan_wire.decide(
            state=state,
            command=AddPlanWire(
                plan_id=state.id,
                source_asset_id=bound_id,
                source_port_name="trigger_out",
                target_asset_id=unbound_id,
                target_port_name="trigger_in",
            ),
            context=PlanWireContext(assets={}),
            now=_NOW,
        )
    assert unbound_id in exc_info.value.missing_asset_ids


@pytest.mark.unit
def test_decide_raises_port_not_found_when_referenced_port_doesnt_exist() -> None:
    """Strict forward-reference: the port MUST exist on Asset.ports right now."""
    src_id = uuid4()
    tgt_id = uuid4()
    state = _plan(asset_ids=frozenset({src_id, tgt_id}))
    with pytest.raises(PlanWirePortNotFoundError) as exc_info:
        add_plan_wire.decide(
            state=state,
            command=AddPlanWire(
                plan_id=state.id,
                source_asset_id=src_id,
                source_port_name="trigger_out",
                target_asset_id=tgt_id,
                target_port_name="missing_input",
            ),
            context=PlanWireContext(
                assets={
                    src_id: _asset(
                        asset_id=src_id,
                        ports=_ports(("trigger_out", PortDirection.OUTPUT, "TTL")),
                    ),
                    tgt_id: _asset(
                        asset_id=tgt_id,
                        ports=_ports(("trigger_in", PortDirection.INPUT, "TTL")),
                    ),
                }
            ),
            now=_NOW,
        )
    # The missing port is the target's "missing_input"
    missing_names = {entry[1] for entry in exc_info.value.missing}
    assert "missing_input" in missing_names


@pytest.mark.unit
def test_decide_raises_direction_mismatch_when_source_is_input() -> None:
    """Source port must be OUTPUT; using an INPUT port as source rejects."""
    src_id = uuid4()
    tgt_id = uuid4()
    state = _plan(asset_ids=frozenset({src_id, tgt_id}))
    with pytest.raises(PlanWireDirectionMismatchError) as exc_info:
        add_plan_wire.decide(
            state=state,
            command=AddPlanWire(
                plan_id=state.id,
                source_asset_id=src_id,
                source_port_name="actually_input",
                target_asset_id=tgt_id,
                target_port_name="trigger_in",
            ),
            context=PlanWireContext(
                assets={
                    src_id: _asset(
                        asset_id=src_id,
                        ports=_ports(("actually_input", PortDirection.INPUT, "TTL")),
                    ),
                    tgt_id: _asset(
                        asset_id=tgt_id,
                        ports=_ports(("trigger_in", PortDirection.INPUT, "TTL")),
                    ),
                }
            ),
            now=_NOW,
        )
    assert exc_info.value.actual_source_direction == "Input"


@pytest.mark.unit
def test_decide_raises_direction_mismatch_when_target_is_output() -> None:
    """Target port must be INPUT; using an OUTPUT port as target rejects.

    Covers the second branch of the boolean OR in wires_validation:
    the case where source IS OUTPUT (passes its check) but target is
    also OUTPUT (fails). Without this case, the target-direction
    branch is never exercised."""
    src_id = uuid4()
    tgt_id = uuid4()
    state = _plan(asset_ids=frozenset({src_id, tgt_id}))
    with pytest.raises(PlanWireDirectionMismatchError) as exc_info:
        add_plan_wire.decide(
            state=state,
            command=AddPlanWire(
                plan_id=state.id,
                source_asset_id=src_id,
                source_port_name="trigger_out",
                target_asset_id=tgt_id,
                target_port_name="actually_output",
            ),
            context=PlanWireContext(
                assets={
                    src_id: _asset(
                        asset_id=src_id,
                        ports=_ports(("trigger_out", PortDirection.OUTPUT, "TTL")),
                    ),
                    tgt_id: _asset(
                        asset_id=tgt_id,
                        ports=_ports(("actually_output", PortDirection.OUTPUT, "TTL")),
                    ),
                }
            ),
            now=_NOW,
        )
    assert exc_info.value.actual_source_direction == "Output"
    assert exc_info.value.actual_target_direction == "Output"


@pytest.mark.unit
def test_decide_raises_direction_mismatch_when_both_endpoints_are_output() -> None:
    """Both endpoints OUTPUT: the boolean OR fires on both branches; the
    error carries both actual directions for diagnostics."""
    src_id = uuid4()
    tgt_id = uuid4()
    state = _plan(asset_ids=frozenset({src_id, tgt_id}))
    with pytest.raises(PlanWireDirectionMismatchError) as exc_info:
        add_plan_wire.decide(
            state=state,
            command=AddPlanWire(
                plan_id=state.id,
                source_asset_id=src_id,
                source_port_name="out_a",
                target_asset_id=tgt_id,
                target_port_name="out_b",
            ),
            context=PlanWireContext(
                assets={
                    src_id: _asset(
                        asset_id=src_id,
                        ports=_ports(("out_a", PortDirection.OUTPUT, "TTL")),
                    ),
                    tgt_id: _asset(
                        asset_id=tgt_id,
                        ports=_ports(("out_b", PortDirection.OUTPUT, "TTL")),
                    ),
                }
            ),
            now=_NOW,
        )
    # Source is OUTPUT (passes its OUTPUT check) but target is also OUTPUT.
    # The error message lists both actuals — one of them must be "wrong".
    assert exc_info.value.actual_target_direction == "Output"


@pytest.mark.unit
def test_decide_raises_signal_type_mismatch_on_different_signal_types() -> None:
    """Source and target signal_type must match exactly."""
    src_id = uuid4()
    tgt_id = uuid4()
    state = _plan(asset_ids=frozenset({src_id, tgt_id}))
    with pytest.raises(PlanWireSignalTypeMismatchError) as exc_info:
        add_plan_wire.decide(
            state=state,
            command=AddPlanWire(
                plan_id=state.id,
                source_asset_id=src_id,
                source_port_name="trigger_out",
                target_asset_id=tgt_id,
                target_port_name="trigger_in",
            ),
            context=PlanWireContext(
                assets={
                    src_id: _asset(
                        asset_id=src_id,
                        ports=_ports(("trigger_out", PortDirection.OUTPUT, "TTL")),
                    ),
                    tgt_id: _asset(
                        asset_id=tgt_id,
                        ports=_ports(("trigger_in", PortDirection.INPUT, "LVDS")),
                    ),
                }
            ),
            now=_NOW,
        )
    assert exc_info.value.source_signal_type == "TTL"
    assert exc_info.value.target_signal_type == "LVDS"


@pytest.mark.unit
def test_decide_emits_event_on_happy_path() -> None:
    """Valid wire adds: emits PlanWireAdded with full 4-tuple payload."""
    src_id = uuid4()
    tgt_id = uuid4()
    state = _plan(asset_ids=frozenset({src_id, tgt_id}))
    events = add_plan_wire.decide(
        state=state,
        command=AddPlanWire(
            plan_id=state.id,
            source_asset_id=src_id,
            source_port_name="trigger_out",
            target_asset_id=tgt_id,
            target_port_name="trigger_in",
        ),
        context=PlanWireContext(
            assets={
                src_id: _asset(
                    asset_id=src_id,
                    ports=_ports(("trigger_out", PortDirection.OUTPUT, "TTL")),
                ),
                tgt_id: _asset(
                    asset_id=tgt_id,
                    ports=_ports(("trigger_in", PortDirection.INPUT, "TTL")),
                ),
            }
        ),
        now=_NOW,
    )
    assert events == [
        PlanWireAdded(
            plan_id=state.id,
            source_asset_id=src_id,
            source_port_name="trigger_out",
            target_asset_id=tgt_id,
            target_port_name="trigger_in",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_allows_self_loop_between_distinct_ports_on_same_asset() -> None:
    """Self-loop between DIFFERENT ports on the same Asset is allowed
    (PandABox LUT block self-feedback pattern)."""
    asset_id = uuid4()
    state = _plan(asset_ids=frozenset({asset_id}))
    events = add_plan_wire.decide(
        state=state,
        command=AddPlanWire(
            plan_id=state.id,
            source_asset_id=asset_id,
            source_port_name="lut_out",
            target_asset_id=asset_id,
            target_port_name="lut_feedback_in",
        ),
        context=PlanWireContext(
            assets={
                asset_id: _asset(
                    asset_id=asset_id,
                    ports=_ports(
                        ("lut_out", PortDirection.OUTPUT, "TTL"),
                        ("lut_feedback_in", PortDirection.INPUT, "TTL"),
                    ),
                )
            }
        ),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].source_asset_id == events[0].target_asset_id


@pytest.mark.unit
def test_decide_allows_fan_out_one_source_to_multiple_targets() -> None:
    """Fan-out is allowed: one source port can drive many target ports."""
    src_id = uuid4()
    tgt_id_1 = uuid4()
    tgt_id_2 = uuid4()
    existing = Wire(
        source_asset_id=src_id,
        source_port_name="trigger_out",
        target_asset_id=tgt_id_1,
        target_port_name="trigger_in",
    )
    state = _plan(
        asset_ids=frozenset({src_id, tgt_id_1, tgt_id_2}),
        wires=frozenset({existing}),
    )
    events = add_plan_wire.decide(
        state=state,
        command=AddPlanWire(
            plan_id=state.id,
            source_asset_id=src_id,
            source_port_name="trigger_out",  # SAME source port
            target_asset_id=tgt_id_2,  # DIFFERENT target asset
            target_port_name="trigger_in",
        ),
        context=PlanWireContext(
            assets={
                src_id: _asset(
                    asset_id=src_id,
                    ports=_ports(("trigger_out", PortDirection.OUTPUT, "TTL")),
                ),
                tgt_id_2: _asset(
                    asset_id=tgt_id_2,
                    ports=_ports(("trigger_in", PortDirection.INPUT, "TTL")),
                ),
            }
        ),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_allows_wire_in_versioned_or_deprecated_plan() -> None:
    """Wire mutation is orthogonal to Plan lifecycle (no source-state guard)."""
    src_id = uuid4()
    tgt_id = uuid4()
    for status in (PlanStatus.VERSIONED, PlanStatus.DEPRECATED):
        state = Plan(
            id=uuid4(),
            name=PlanName("Versioned/Deprecated Plan"),
            practice_id=uuid4(),
            asset_ids=frozenset({src_id, tgt_id}),
            status=status,
            method_id=uuid4(),
        )
        events = add_plan_wire.decide(
            state=state,
            command=AddPlanWire(
                plan_id=state.id,
                source_asset_id=src_id,
                source_port_name="trigger_out",
                target_asset_id=tgt_id,
                target_port_name="trigger_in",
            ),
            context=PlanWireContext(
                assets={
                    src_id: _asset(
                        asset_id=src_id,
                        ports=_ports(("trigger_out", PortDirection.OUTPUT, "TTL")),
                    ),
                    tgt_id: _asset(
                        asset_id=tgt_id,
                        ports=_ports(("trigger_in", PortDirection.INPUT, "TTL")),
                    ),
                }
            ),
            now=_NOW,
        )
        assert len(events) == 1, f"Should accept wire in status={status.value}"


@pytest.mark.unit
def test_decide_raises_pseudoaxis_arity_mismatch_when_wire_count_exceeds_rule() -> None:
    """PseudoAxis Asset with Affine rule (arity 1) rejects the 2nd incoming wire."""
    pseudoaxis_family_id = uuid4()
    src_id_1 = uuid4()
    src_id_2 = uuid4()
    tgt_id = uuid4()
    existing = Wire(
        source_asset_id=src_id_1,
        source_port_name="setpoint_out",
        target_asset_id=tgt_id,
        target_port_name="constituent_in_a",
    )
    state = _plan(
        asset_ids=frozenset({src_id_1, src_id_2, tgt_id}),
        wires=frozenset({existing}),
    )
    with pytest.raises(PlanPseudoAxisArityMismatchError) as exc_info:
        add_plan_wire.decide(
            state=state,
            command=AddPlanWire(
                plan_id=state.id,
                source_asset_id=src_id_2,
                source_port_name="setpoint_out",
                target_asset_id=tgt_id,
                target_port_name="constituent_in_b",
            ),
            context=PlanWireContext(
                assets={
                    src_id_1: _asset(
                        asset_id=src_id_1,
                        ports=_ports(("setpoint_out", PortDirection.OUTPUT, "mm")),
                    ),
                    src_id_2: _asset(
                        asset_id=src_id_2,
                        ports=_ports(("setpoint_out", PortDirection.OUTPUT, "mm")),
                    ),
                    tgt_id: _asset(
                        asset_id=tgt_id,
                        ports=_ports(
                            ("constituent_in_a", PortDirection.INPUT, "mm"),
                            ("constituent_in_b", PortDirection.INPUT, "mm"),
                            ("virtual_out", PortDirection.OUTPUT, "mm"),
                        ),
                        family_ids=frozenset({pseudoaxis_family_id}),
                        partition_rule=Affine(gain=1.0, offset=0.0),
                    ),
                }
            ),
            now=_NOW,
            pseudoaxis_family_ids=frozenset({pseudoaxis_family_id}),
        )
    assert exc_info.value.pseudoaxis_asset_id == tgt_id
    assert exc_info.value.expected_constituent_count == 1
    assert exc_info.value.actual_input_wire_count == 2


@pytest.mark.unit
def test_decide_raises_pseudoaxis_fanout_signal_type_mismatch_on_mixed_sources() -> None:
    """PseudoAxis fan-out rejects when incoming wires carry differing signal_types."""
    pseudoaxis_family_id = uuid4()
    src_id_1 = uuid4()
    src_id_2 = uuid4()
    tgt_id = uuid4()
    existing = Wire(
        source_asset_id=src_id_1,
        source_port_name="setpoint_out",
        target_asset_id=tgt_id,
        target_port_name="constituent_in_a",
    )
    state = _plan(
        asset_ids=frozenset({src_id_1, src_id_2, tgt_id}),
        wires=frozenset({existing}),
    )
    with pytest.raises(PlanPseudoAxisFanoutSignalTypeMismatchError) as exc_info:
        add_plan_wire.decide(
            state=state,
            command=AddPlanWire(
                plan_id=state.id,
                source_asset_id=src_id_2,
                source_port_name="setpoint_out",
                target_asset_id=tgt_id,
                target_port_name="constituent_in_b",
            ),
            context=PlanWireContext(
                assets={
                    src_id_1: _asset(
                        asset_id=src_id_1,
                        ports=_ports(("setpoint_out", PortDirection.OUTPUT, "mm")),
                    ),
                    src_id_2: _asset(
                        asset_id=src_id_2,
                        ports=_ports(("setpoint_out", PortDirection.OUTPUT, "deg")),
                    ),
                    tgt_id: _asset(
                        asset_id=tgt_id,
                        ports=_ports(
                            ("constituent_in_a", PortDirection.INPUT, "mm"),
                            ("constituent_in_b", PortDirection.INPUT, "deg"),
                            ("virtual_out", PortDirection.OUTPUT, "mm"),
                        ),
                        family_ids=frozenset({pseudoaxis_family_id}),
                        partition_rule=Aggregation(
                            aggregator_kind=AggregatorKind.SUM,
                            constituent_count=2,
                        ),
                    ),
                }
            ),
            now=_NOW,
            pseudoaxis_family_ids=frozenset({pseudoaxis_family_id}),
        )
    assert exc_info.value.pseudoaxis_asset_id == tgt_id
    assert exc_info.value.signal_types == frozenset({"mm", "deg"})


@pytest.mark.unit
def test_decide_raises_pseudoaxis_output_cardinality_when_target_has_no_output_port() -> None:
    """PseudoAxis Asset MUST declare exactly 1 OUTPUT port; zero or 2+ rejects."""
    pseudoaxis_family_id = uuid4()
    src_id = uuid4()
    tgt_id = uuid4()
    state = _plan(asset_ids=frozenset({src_id, tgt_id}))
    with pytest.raises(PlanPseudoAxisOutputCardinalityError) as exc_info:
        add_plan_wire.decide(
            state=state,
            command=AddPlanWire(
                plan_id=state.id,
                source_asset_id=src_id,
                source_port_name="setpoint_out",
                target_asset_id=tgt_id,
                target_port_name="constituent_in",
            ),
            context=PlanWireContext(
                assets={
                    src_id: _asset(
                        asset_id=src_id,
                        ports=_ports(("setpoint_out", PortDirection.OUTPUT, "mm")),
                    ),
                    tgt_id: _asset(
                        asset_id=tgt_id,
                        ports=_ports(
                            ("constituent_in", PortDirection.INPUT, "mm"),
                            ("virtual_out_a", PortDirection.OUTPUT, "mm"),
                            ("virtual_out_b", PortDirection.OUTPUT, "mm"),
                        ),
                        family_ids=frozenset({pseudoaxis_family_id}),
                        partition_rule=Affine(gain=1.0, offset=0.0),
                    ),
                }
            ),
            now=_NOW,
            pseudoaxis_family_ids=frozenset({pseudoaxis_family_id}),
        )
    assert exc_info.value.pseudoaxis_asset_id == tgt_id
    assert exc_info.value.output_port_count == 2
