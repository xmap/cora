"""Unit tests for `validate_pseudoaxis_fanout`.

Pins the four checks layered on top of `validate_wire_endpoints` for a
PseudoAxis Asset's incoming wire set:

  (a) rule-is-None no-op
  (b) output cardinality (PseudoAxis MUST declare exactly 1 OUTPUT port)
  (c) arity match against `expected_constituent_count(rule)`
      (Affine=1, Aggregation=N, CompositePartition=N; SolverReference skips)
  (d) signal_type homogeneity across the incoming wires' source ports
"""

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates._partition_rule import (
    Affine,
    Aggregation,
    AggregatorKind,
    CompositePartition,
    PartitionKind,
    ReadbackAggregatorKind,
    SolverReference,
    SolverTransportKind,
)
from cora.equipment.aggregates.asset.state import (
    Asset,
    AssetLevel,
    AssetLifecycle,
    AssetName,
    AssetPort,
    PortDirection,
)
from cora.recipe.aggregates.plan import (
    PlanPseudoAxisArityMismatchError,
    PlanPseudoAxisFanoutSignalTypeMismatchError,
    PlanPseudoAxisOutputCardinalityError,
    Wire,
    validate_pseudoaxis_fanout,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


def _asset(
    *,
    asset_id: UUID,
    ports: frozenset[AssetPort] = frozenset(),
) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("Test Asset"),
        level=AssetLevel.DEVICE,
        parent_id=None,
        lifecycle=AssetLifecycle.ACTIVE,
        ports=ports,
    )


def _ports(*defs: tuple[str, PortDirection, str]) -> frozenset[AssetPort]:
    return frozenset(
        AssetPort(name=name, direction=direction, signal_type=signal_type)
        for name, direction, signal_type in defs
    )


def _wire_into(
    pseudoaxis_id: UUID,
    target_port_name: str,
    *,
    source_asset_id: UUID,
    source_port_name: str,
) -> Wire:
    return Wire(
        source_asset_id=source_asset_id,
        source_port_name=source_port_name,
        target_asset_id=pseudoaxis_id,
        target_port_name=target_port_name,
    )


def _solver_reference(invertible: bool = True) -> SolverReference:
    """Build a minimal valid SolverReference for arity-skip tests."""
    return SolverReference(
        solver_id="vendor.hexapod",
        solver_version="1.0.0",
        solver_transport_kind=SolverTransportKind.SOFT_IOC_RECORD,
        residual_tolerance_limit=1e-6,
        singularity_threshold=1e-3,
        invertible=invertible,
        readback_aggregator_kind=(None if invertible else ReadbackAggregatorKind.SELECT_INDEX_0),
    )


def _composite(constituent_count: int) -> CompositePartition:
    return CompositePartition(
        partition_kind=PartitionKind.PROPORTIONAL_FILL,
        constituent_count=constituent_count,
        partition_parameters=(),
        readback_aggregator_kind=ReadbackAggregatorKind.SUM,
    )


@pytest.mark.unit
def test_validate_pseudoaxis_fanout_no_ops_when_rule_is_none() -> None:
    pseudoaxis_id = uuid4()
    pseudoaxis = _asset(
        asset_id=pseudoaxis_id,
        ports=_ports(("virtual_out", PortDirection.OUTPUT, "mm")),
    )
    validate_pseudoaxis_fanout(
        pseudoaxis_asset=pseudoaxis,
        partition_rule=None,
        incoming_wires=frozenset(),
        assets_by_id={pseudoaxis_id: pseudoaxis},
    )


@pytest.mark.unit
def test_validate_pseudoaxis_fanout_no_ops_when_rule_is_none_even_with_bad_cardinality() -> None:
    """Rule-None short-circuits BEFORE the output-cardinality check fires."""
    pseudoaxis_id = uuid4()
    pseudoaxis = _asset(
        asset_id=pseudoaxis_id,
        ports=_ports(
            ("virtual_out_a", PortDirection.OUTPUT, "mm"),
            ("virtual_out_b", PortDirection.OUTPUT, "mm"),
        ),
    )
    validate_pseudoaxis_fanout(
        pseudoaxis_asset=pseudoaxis,
        partition_rule=None,
        incoming_wires=frozenset(),
        assets_by_id={pseudoaxis_id: pseudoaxis},
    )


@pytest.mark.unit
def test_validate_pseudoaxis_fanout_raises_output_cardinality_when_zero_output_ports() -> None:
    pseudoaxis_id = uuid4()
    pseudoaxis = _asset(
        asset_id=pseudoaxis_id,
        ports=_ports(("constituent_in", PortDirection.INPUT, "mm")),
    )
    with pytest.raises(PlanPseudoAxisOutputCardinalityError) as exc_info:
        validate_pseudoaxis_fanout(
            pseudoaxis_asset=pseudoaxis,
            partition_rule=Affine(),
            incoming_wires=frozenset(),
            assets_by_id={pseudoaxis_id: pseudoaxis},
        )
    assert exc_info.value.pseudoaxis_asset_id == pseudoaxis_id
    assert exc_info.value.output_port_count == 0


@pytest.mark.unit
def test_validate_pseudoaxis_fanout_raises_output_cardinality_when_two_output_ports() -> None:
    pseudoaxis_id = uuid4()
    pseudoaxis = _asset(
        asset_id=pseudoaxis_id,
        ports=_ports(
            ("virtual_out_a", PortDirection.OUTPUT, "mm"),
            ("virtual_out_b", PortDirection.OUTPUT, "mm"),
            ("constituent_in", PortDirection.INPUT, "mm"),
        ),
    )
    with pytest.raises(PlanPseudoAxisOutputCardinalityError) as exc_info:
        validate_pseudoaxis_fanout(
            pseudoaxis_asset=pseudoaxis,
            partition_rule=Affine(),
            incoming_wires=frozenset(),
            assets_by_id={pseudoaxis_id: pseudoaxis},
        )
    assert exc_info.value.output_port_count == 2


@pytest.mark.unit
def test_validate_pseudoaxis_fanout_passes_output_cardinality_when_exactly_one_output_port() -> (
    None
):
    """Single OUTPUT port + matching Affine arity (1) is the canonical happy path."""
    pseudoaxis_id = uuid4()
    source_id = uuid4()
    pseudoaxis = _asset(
        asset_id=pseudoaxis_id,
        ports=_ports(
            ("virtual_out", PortDirection.OUTPUT, "mm"),
            ("constituent_in", PortDirection.INPUT, "mm"),
        ),
    )
    source = _asset(
        asset_id=source_id,
        ports=_ports(("motor_readback", PortDirection.OUTPUT, "mm")),
    )
    wire = _wire_into(
        pseudoaxis_id,
        "constituent_in",
        source_asset_id=source_id,
        source_port_name="motor_readback",
    )
    validate_pseudoaxis_fanout(
        pseudoaxis_asset=pseudoaxis,
        partition_rule=Affine(),
        incoming_wires=frozenset({wire}),
        assets_by_id={pseudoaxis_id: pseudoaxis, source_id: source},
    )


@pytest.mark.unit
def test_validate_pseudoaxis_fanout_raises_arity_mismatch_for_affine_with_two_wires() -> None:
    """Affine declares arity 1; two incoming wires fail."""
    pseudoaxis_id = uuid4()
    src_a = uuid4()
    src_b = uuid4()
    pseudoaxis = _asset(
        asset_id=pseudoaxis_id,
        ports=_ports(
            ("virtual_out", PortDirection.OUTPUT, "mm"),
            ("constituent_in_a", PortDirection.INPUT, "mm"),
            ("constituent_in_b", PortDirection.INPUT, "mm"),
        ),
    )
    source_a = _asset(asset_id=src_a, ports=_ports(("rb", PortDirection.OUTPUT, "mm")))
    source_b = _asset(asset_id=src_b, ports=_ports(("rb", PortDirection.OUTPUT, "mm")))
    wires = frozenset(
        {
            _wire_into(
                pseudoaxis_id, "constituent_in_a", source_asset_id=src_a, source_port_name="rb"
            ),
            _wire_into(
                pseudoaxis_id, "constituent_in_b", source_asset_id=src_b, source_port_name="rb"
            ),
        }
    )
    assets: Mapping[UUID, Asset] = {
        pseudoaxis_id: pseudoaxis,
        src_a: source_a,
        src_b: source_b,
    }
    with pytest.raises(PlanPseudoAxisArityMismatchError) as exc_info:
        validate_pseudoaxis_fanout(
            pseudoaxis_asset=pseudoaxis,
            partition_rule=Affine(),
            incoming_wires=wires,
            assets_by_id=assets,
        )
    assert exc_info.value.expected_constituent_count == 1
    assert exc_info.value.actual_input_wire_count == 2
    assert exc_info.value.rule_kind == "Affine"


@pytest.mark.unit
def test_validate_pseudoaxis_fanout_passes_arity_for_affine_with_one_wire() -> None:
    pseudoaxis_id = uuid4()
    source_id = uuid4()
    pseudoaxis = _asset(
        asset_id=pseudoaxis_id,
        ports=_ports(
            ("virtual_out", PortDirection.OUTPUT, "mm"),
            ("constituent_in", PortDirection.INPUT, "mm"),
        ),
    )
    source = _asset(asset_id=source_id, ports=_ports(("rb", PortDirection.OUTPUT, "mm")))
    wire = _wire_into(
        pseudoaxis_id, "constituent_in", source_asset_id=source_id, source_port_name="rb"
    )
    validate_pseudoaxis_fanout(
        pseudoaxis_asset=pseudoaxis,
        partition_rule=Affine(),
        incoming_wires=frozenset({wire}),
        assets_by_id={pseudoaxis_id: pseudoaxis, source_id: source},
    )


@pytest.mark.unit
def test_validate_pseudoaxis_fanout_passes_arity_for_aggregation_with_matching_wire_count() -> None:
    pseudoaxis_id = uuid4()
    src_a = uuid4()
    src_b = uuid4()
    src_c = uuid4()
    pseudoaxis = _asset(
        asset_id=pseudoaxis_id,
        ports=_ports(
            ("virtual_out", PortDirection.OUTPUT, "mm"),
            ("in_a", PortDirection.INPUT, "mm"),
            ("in_b", PortDirection.INPUT, "mm"),
            ("in_c", PortDirection.INPUT, "mm"),
        ),
    )
    sources = {
        src_a: _asset(asset_id=src_a, ports=_ports(("rb", PortDirection.OUTPUT, "mm"))),
        src_b: _asset(asset_id=src_b, ports=_ports(("rb", PortDirection.OUTPUT, "mm"))),
        src_c: _asset(asset_id=src_c, ports=_ports(("rb", PortDirection.OUTPUT, "mm"))),
    }
    wires = frozenset(
        {
            _wire_into(pseudoaxis_id, "in_a", source_asset_id=src_a, source_port_name="rb"),
            _wire_into(pseudoaxis_id, "in_b", source_asset_id=src_b, source_port_name="rb"),
            _wire_into(pseudoaxis_id, "in_c", source_asset_id=src_c, source_port_name="rb"),
        }
    )
    validate_pseudoaxis_fanout(
        pseudoaxis_asset=pseudoaxis,
        partition_rule=Aggregation(aggregator_kind=AggregatorKind.SUM, constituent_count=3),
        incoming_wires=wires,
        assets_by_id={pseudoaxis_id: pseudoaxis, **sources},
    )


@pytest.mark.unit
def test_validate_pseudoaxis_fanout_accepts_under_wired_aggregation_during_incremental_bind() -> (
    None
):
    pseudoaxis_id = uuid4()
    src_a = uuid4()
    pseudoaxis = _asset(
        asset_id=pseudoaxis_id,
        ports=_ports(
            ("virtual_out", PortDirection.OUTPUT, "mm"),
            ("in_a", PortDirection.INPUT, "mm"),
            ("in_b", PortDirection.INPUT, "mm"),
        ),
    )
    source_a = _asset(asset_id=src_a, ports=_ports(("rb", PortDirection.OUTPUT, "mm")))
    wires = frozenset(
        {_wire_into(pseudoaxis_id, "in_a", source_asset_id=src_a, source_port_name="rb")}
    )
    validate_pseudoaxis_fanout(
        pseudoaxis_asset=pseudoaxis,
        partition_rule=Aggregation(aggregator_kind=AggregatorKind.SUM, constituent_count=2),
        incoming_wires=wires,
        assets_by_id={pseudoaxis_id: pseudoaxis, src_a: source_a},
    )


@pytest.mark.unit
def test_validate_pseudoaxis_fanout_passes_arity_for_composite_partition_with_two_wires() -> None:
    pseudoaxis_id = uuid4()
    src_a = uuid4()
    src_b = uuid4()
    pseudoaxis = _asset(
        asset_id=pseudoaxis_id,
        ports=_ports(
            ("virtual_out", PortDirection.OUTPUT, "mm"),
            ("hexapod_in", PortDirection.INPUT, "mm"),
            ("table_in", PortDirection.INPUT, "mm"),
        ),
    )
    source_a = _asset(asset_id=src_a, ports=_ports(("rb", PortDirection.OUTPUT, "mm")))
    source_b = _asset(asset_id=src_b, ports=_ports(("rb", PortDirection.OUTPUT, "mm")))
    wires = frozenset(
        {
            _wire_into(pseudoaxis_id, "hexapod_in", source_asset_id=src_a, source_port_name="rb"),
            _wire_into(pseudoaxis_id, "table_in", source_asset_id=src_b, source_port_name="rb"),
        }
    )
    validate_pseudoaxis_fanout(
        pseudoaxis_asset=pseudoaxis,
        partition_rule=_composite(constituent_count=2),
        incoming_wires=wires,
        assets_by_id={pseudoaxis_id: pseudoaxis, src_a: source_a, src_b: source_b},
    )


@pytest.mark.unit
def test_validate_pseudoaxis_fanout_raises_arity_mismatch_for_composite_partition_over_wired() -> (
    None
):
    pseudoaxis_id = uuid4()
    src_a = uuid4()
    src_b = uuid4()
    src_c = uuid4()
    pseudoaxis = _asset(
        asset_id=pseudoaxis_id,
        ports=_ports(
            ("virtual_out", PortDirection.OUTPUT, "mm"),
            ("in_a", PortDirection.INPUT, "mm"),
            ("in_b", PortDirection.INPUT, "mm"),
            ("in_c", PortDirection.INPUT, "mm"),
        ),
    )
    sources = {
        src_a: _asset(asset_id=src_a, ports=_ports(("rb", PortDirection.OUTPUT, "mm"))),
        src_b: _asset(asset_id=src_b, ports=_ports(("rb", PortDirection.OUTPUT, "mm"))),
        src_c: _asset(asset_id=src_c, ports=_ports(("rb", PortDirection.OUTPUT, "mm"))),
    }
    wires = frozenset(
        {
            _wire_into(pseudoaxis_id, "in_a", source_asset_id=src_a, source_port_name="rb"),
            _wire_into(pseudoaxis_id, "in_b", source_asset_id=src_b, source_port_name="rb"),
            _wire_into(pseudoaxis_id, "in_c", source_asset_id=src_c, source_port_name="rb"),
        }
    )
    with pytest.raises(PlanPseudoAxisArityMismatchError) as exc_info:
        validate_pseudoaxis_fanout(
            pseudoaxis_asset=pseudoaxis,
            partition_rule=_composite(constituent_count=2),
            incoming_wires=wires,
            assets_by_id={pseudoaxis_id: pseudoaxis, **sources},
        )
    assert exc_info.value.expected_constituent_count == 2
    assert exc_info.value.actual_input_wire_count == 3
    assert exc_info.value.rule_kind == "CompositePartition"


@pytest.mark.unit
def test_validate_pseudoaxis_fanout_skips_arity_check_for_solver_reference() -> None:
    """SolverReference declares no arity; any incoming wire count passes."""
    pseudoaxis_id = uuid4()
    src_a = uuid4()
    src_b = uuid4()
    src_c = uuid4()
    pseudoaxis = _asset(
        asset_id=pseudoaxis_id,
        ports=_ports(
            ("virtual_out", PortDirection.OUTPUT, "mm"),
            ("leg_1", PortDirection.INPUT, "mm"),
            ("leg_2", PortDirection.INPUT, "mm"),
            ("leg_3", PortDirection.INPUT, "mm"),
        ),
    )
    sources = {
        src_a: _asset(asset_id=src_a, ports=_ports(("rb", PortDirection.OUTPUT, "mm"))),
        src_b: _asset(asset_id=src_b, ports=_ports(("rb", PortDirection.OUTPUT, "mm"))),
        src_c: _asset(asset_id=src_c, ports=_ports(("rb", PortDirection.OUTPUT, "mm"))),
    }
    wires = frozenset(
        {
            _wire_into(pseudoaxis_id, "leg_1", source_asset_id=src_a, source_port_name="rb"),
            _wire_into(pseudoaxis_id, "leg_2", source_asset_id=src_b, source_port_name="rb"),
            _wire_into(pseudoaxis_id, "leg_3", source_asset_id=src_c, source_port_name="rb"),
        }
    )
    validate_pseudoaxis_fanout(
        pseudoaxis_asset=pseudoaxis,
        partition_rule=_solver_reference(),
        incoming_wires=wires,
        assets_by_id={pseudoaxis_id: pseudoaxis, **sources},
    )


@pytest.mark.unit
def test_validate_pseudoaxis_fanout_passes_signal_type_homogeneity_with_single_type() -> None:
    pseudoaxis_id = uuid4()
    src_a = uuid4()
    src_b = uuid4()
    pseudoaxis = _asset(
        asset_id=pseudoaxis_id,
        ports=_ports(
            ("virtual_out", PortDirection.OUTPUT, "mm"),
            ("in_a", PortDirection.INPUT, "mm"),
            ("in_b", PortDirection.INPUT, "mm"),
        ),
    )
    source_a = _asset(asset_id=src_a, ports=_ports(("rb", PortDirection.OUTPUT, "mm")))
    source_b = _asset(asset_id=src_b, ports=_ports(("rb", PortDirection.OUTPUT, "mm")))
    wires = frozenset(
        {
            _wire_into(pseudoaxis_id, "in_a", source_asset_id=src_a, source_port_name="rb"),
            _wire_into(pseudoaxis_id, "in_b", source_asset_id=src_b, source_port_name="rb"),
        }
    )
    validate_pseudoaxis_fanout(
        pseudoaxis_asset=pseudoaxis,
        partition_rule=Aggregation(aggregator_kind=AggregatorKind.SUM, constituent_count=2),
        incoming_wires=wires,
        assets_by_id={pseudoaxis_id: pseudoaxis, src_a: source_a, src_b: source_b},
    )


@pytest.mark.unit
def test_validate_pseudoaxis_fanout_raises_signal_type_mismatch_for_mixed_sources() -> None:
    pseudoaxis_id = uuid4()
    src_mm = uuid4()
    src_deg = uuid4()
    pseudoaxis = _asset(
        asset_id=pseudoaxis_id,
        ports=_ports(
            ("virtual_out", PortDirection.OUTPUT, "mm"),
            ("in_a", PortDirection.INPUT, "mm"),
            ("in_b", PortDirection.INPUT, "mm"),
        ),
    )
    source_mm = _asset(asset_id=src_mm, ports=_ports(("rb", PortDirection.OUTPUT, "mm")))
    source_deg = _asset(asset_id=src_deg, ports=_ports(("rb", PortDirection.OUTPUT, "deg")))
    wires = frozenset(
        {
            _wire_into(pseudoaxis_id, "in_a", source_asset_id=src_mm, source_port_name="rb"),
            _wire_into(pseudoaxis_id, "in_b", source_asset_id=src_deg, source_port_name="rb"),
        }
    )
    with pytest.raises(PlanPseudoAxisFanoutSignalTypeMismatchError) as exc_info:
        validate_pseudoaxis_fanout(
            pseudoaxis_asset=pseudoaxis,
            partition_rule=Aggregation(aggregator_kind=AggregatorKind.SUM, constituent_count=2),
            incoming_wires=wires,
            assets_by_id={pseudoaxis_id: pseudoaxis, src_mm: source_mm, src_deg: source_deg},
        )
    assert exc_info.value.signal_types == frozenset({"mm", "deg"})
    assert exc_info.value.rule_kind == "Aggregation"
    assert exc_info.value.pseudoaxis_asset_id == pseudoaxis_id


@pytest.mark.unit
def test_validate_pseudoaxis_fanout_signal_type_payload_is_frozenset() -> None:
    """The error carries a frozenset, not a list/tuple, for stable equality."""
    pseudoaxis_id = uuid4()
    src_a = uuid4()
    src_b = uuid4()
    pseudoaxis = _asset(
        asset_id=pseudoaxis_id,
        ports=_ports(
            ("virtual_out", PortDirection.OUTPUT, "mm"),
            ("in_a", PortDirection.INPUT, "mm"),
            ("in_b", PortDirection.INPUT, "mm"),
        ),
    )
    source_a = _asset(asset_id=src_a, ports=_ports(("rb", PortDirection.OUTPUT, "TTL")))
    source_b = _asset(asset_id=src_b, ports=_ports(("rb", PortDirection.OUTPUT, "LVDS")))
    wires = frozenset(
        {
            _wire_into(pseudoaxis_id, "in_a", source_asset_id=src_a, source_port_name="rb"),
            _wire_into(pseudoaxis_id, "in_b", source_asset_id=src_b, source_port_name="rb"),
        }
    )
    with pytest.raises(PlanPseudoAxisFanoutSignalTypeMismatchError) as exc_info:
        validate_pseudoaxis_fanout(
            pseudoaxis_asset=pseudoaxis,
            partition_rule=Aggregation(aggregator_kind=AggregatorKind.SUM, constituent_count=2),
            incoming_wires=wires,
            assets_by_id={pseudoaxis_id: pseudoaxis, src_a: source_a, src_b: source_b},
        )
    assert isinstance(exc_info.value.signal_types, frozenset)
