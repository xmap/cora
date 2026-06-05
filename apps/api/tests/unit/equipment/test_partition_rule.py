"""Unit tests for the PartitionRule value object: 5 shapes, 7 enums, codec helpers.

Tests the closed discriminated union of frozen-dataclass shapes (Affine,
Aggregation, LookupTable, CompositePartition, SolverReference) and the
serialization/deserialization helpers (partition_rule_to_payload /
partition_rule_from_payload).
"""

from dataclasses import FrozenInstanceError
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates._partition_rule import (
    PARTITION_RULE_SOLVER_ID_MAX_LENGTH,
    PARTITION_RULE_SOLVER_VERSION_MAX_LENGTH,
    Affine,
    Aggregation,
    AggregatorKind,
    CompositePartition,
    ExtrapolationKind,
    InterpolationKind,
    InvalidPartitionRuleError,
    LookupTable,
    PartitionKind,
    PartitionRuleKind,
    ReadbackAggregatorKind,
    SolverReference,
    SolverTransportKind,
    expected_constituent_count,
    partition_rule_from_payload,
    partition_rule_to_payload,
)

# =============================================================================
# AFFINE SHAPE TESTS
# =============================================================================


@pytest.mark.unit
def test_affine_constructs_happy_path_with_all_fields() -> None:
    rule = Affine(gain=2.5, offset=10.0, unit_in="mm", unit_out="deg")
    assert rule.gain == 2.5
    assert rule.offset == 10.0
    assert rule.unit_in == "mm"
    assert rule.unit_out == "deg"
    assert rule.kind == PartitionRuleKind.AFFINE


@pytest.mark.unit
def test_affine_default_field_values() -> None:
    rule = Affine()
    assert rule.gain == 1.0
    assert rule.offset == 0.0
    assert rule.unit_in == ""
    assert rule.unit_out == ""


@pytest.mark.unit
def test_affine_kind_discriminator_set_by_default_and_not_passable() -> None:
    rule = Affine(gain=1.0, offset=0.0)
    assert rule.kind == PartitionRuleKind.AFFINE
    # Attempting to pass kind raises TypeError because init=False
    with pytest.raises(TypeError):
        Affine(kind=PartitionRuleKind.AFFINE)  # type: ignore[call-arg]


@pytest.mark.unit
def test_affine_rejects_gain_nan() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        Affine(gain=float("nan"))
    assert info.value.sub_code == "numeric_not_finite"
    assert "gain" in info.value.reason


@pytest.mark.unit
def test_affine_rejects_gain_inf() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        Affine(gain=float("inf"))
    assert info.value.sub_code == "numeric_not_finite"


@pytest.mark.unit
def test_affine_rejects_gain_neg_inf() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        Affine(gain=float("-inf"))
    assert info.value.sub_code == "numeric_not_finite"


@pytest.mark.unit
def test_affine_rejects_offset_nan() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        Affine(offset=float("nan"))
    assert info.value.sub_code == "numeric_not_finite"
    assert "offset" in info.value.reason


@pytest.mark.unit
def test_affine_rejects_offset_inf() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        Affine(offset=float("inf"))
    assert info.value.sub_code == "numeric_not_finite"


@pytest.mark.unit
def test_affine_accepts_zero_gain() -> None:
    rule = Affine(gain=0.0)
    assert rule.gain == 0.0


@pytest.mark.unit
def test_affine_accepts_negative_gain() -> None:
    rule = Affine(gain=-1.5)
    assert rule.gain == -1.5


@pytest.mark.unit
def test_affine_accepts_negative_offset() -> None:
    rule = Affine(offset=-99.5)
    assert rule.offset == -99.5


@pytest.mark.unit
def test_affine_is_frozen() -> None:
    rule = Affine(gain=2.0)
    with pytest.raises(FrozenInstanceError):
        rule.gain = 3.0  # type: ignore[misc]


@pytest.mark.unit
def test_affine_equality_is_structural() -> None:
    a = Affine(gain=2.0, offset=5.0, unit_in="mm", unit_out="deg")
    b = Affine(gain=2.0, offset=5.0, unit_in="mm", unit_out="deg")
    assert a == b
    assert hash(a) == hash(b)


@pytest.mark.unit
def test_affine_in_frozenset() -> None:
    rule = Affine(gain=1.5)
    assert rule in {rule}


# =============================================================================
# AGGREGATION SHAPE TESTS
# =============================================================================


@pytest.mark.unit
def test_aggregation_constructs_happy_path() -> None:
    rule = Aggregation(aggregator_kind=AggregatorKind.SUM, constituent_count=3)
    assert rule.aggregator_kind == AggregatorKind.SUM
    assert rule.constituent_count == 3
    assert rule.kind == PartitionRuleKind.AGGREGATION


@pytest.mark.unit
def test_aggregation_default_field_values() -> None:
    rule = Aggregation()
    assert rule.aggregator_kind == AggregatorKind.SUM
    assert rule.constituent_count == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    "aggregator_kind",
    [
        AggregatorKind.SUM,
        AggregatorKind.DIFFERENCE,
        AggregatorKind.MID_RANGE,
        AggregatorKind.PRODUCT,
    ],
)
def test_aggregation_accepts_all_aggregator_kinds(
    aggregator_kind: AggregatorKind,
) -> None:
    # SUM and PRODUCT accept any constituent_count >= 1
    if aggregator_kind in (AggregatorKind.SUM, AggregatorKind.PRODUCT):
        rule = Aggregation(aggregator_kind=aggregator_kind, constituent_count=1)
        assert rule.aggregator_kind == aggregator_kind
    # DIFFERENCE and MID_RANGE require exactly 2
    else:
        rule = Aggregation(aggregator_kind=aggregator_kind, constituent_count=2)
        assert rule.aggregator_kind == aggregator_kind


@pytest.mark.unit
def test_aggregation_rejects_constituent_count_below_minimum() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        Aggregation(constituent_count=0)
    assert info.value.sub_code == "constituent_count_below_minimum"
    assert "constituent_count must be >= 1" in info.value.reason


@pytest.mark.unit
def test_aggregation_rejects_negative_constituent_count() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        Aggregation(constituent_count=-1)
    assert info.value.sub_code == "constituent_count_below_minimum"


@pytest.mark.unit
def test_aggregation_rejects_difference_with_constituent_count_not_2() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        Aggregation(aggregator_kind=AggregatorKind.DIFFERENCE, constituent_count=1)
    assert info.value.sub_code == "aggregator_constituent_count_mismatch"
    assert "Difference" in info.value.reason
    assert "constituent_count == 2" in info.value.reason


@pytest.mark.unit
def test_aggregation_rejects_difference_with_constituent_count_3() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        Aggregation(aggregator_kind=AggregatorKind.DIFFERENCE, constituent_count=3)
    assert info.value.sub_code == "aggregator_constituent_count_mismatch"


@pytest.mark.unit
def test_aggregation_rejects_mid_range_with_constituent_count_not_2() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        Aggregation(aggregator_kind=AggregatorKind.MID_RANGE, constituent_count=1)
    assert info.value.sub_code == "aggregator_constituent_count_mismatch"
    assert "MidRange" in info.value.reason


@pytest.mark.unit
def test_aggregation_rejects_mid_range_with_constituent_count_3() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        Aggregation(aggregator_kind=AggregatorKind.MID_RANGE, constituent_count=3)
    assert info.value.sub_code == "aggregator_constituent_count_mismatch"


@pytest.mark.unit
def test_aggregation_accepts_sum_with_any_constituent_count_gte_1() -> None:
    for count in [1, 2, 10, 100]:
        rule = Aggregation(aggregator_kind=AggregatorKind.SUM, constituent_count=count)
        assert rule.constituent_count == count


@pytest.mark.unit
def test_aggregation_accepts_product_with_any_constituent_count_gte_1() -> None:
    for count in [1, 2, 10, 100]:
        rule = Aggregation(aggregator_kind=AggregatorKind.PRODUCT, constituent_count=count)
        assert rule.constituent_count == count


@pytest.mark.unit
def test_aggregation_is_frozen() -> None:
    rule = Aggregation()
    with pytest.raises(FrozenInstanceError):
        rule.constituent_count = 2  # type: ignore[misc]


@pytest.mark.unit
def test_aggregation_equality_is_structural() -> None:
    a = Aggregation(aggregator_kind=AggregatorKind.DIFFERENCE, constituent_count=2)
    b = Aggregation(aggregator_kind=AggregatorKind.DIFFERENCE, constituent_count=2)
    assert a == b
    assert hash(a) == hash(b)


# =============================================================================
# LOOKUP_TABLE SHAPE TESTS
# =============================================================================


@pytest.mark.unit
def test_lookup_table_constructs_happy_path_with_all_fields() -> None:
    cal_id = uuid4()
    rule = LookupTable(
        calibration_revision_id=cal_id,
        interpolation_kind=InterpolationKind.CUBIC,
        extrapolation_kind=ExtrapolationKind.ERROR,
        invertible=False,
        readback_aggregator_kind=ReadbackAggregatorKind.MEAN,
        unit_in="deg",
        unit_out="um",
    )
    assert rule.calibration_revision_id == cal_id
    assert rule.interpolation_kind == InterpolationKind.CUBIC
    assert rule.extrapolation_kind == ExtrapolationKind.ERROR
    assert rule.invertible is False
    assert rule.readback_aggregator_kind == ReadbackAggregatorKind.MEAN
    assert rule.unit_in == "deg"
    assert rule.unit_out == "um"
    assert rule.kind == PartitionRuleKind.LOOKUP_TABLE


@pytest.mark.unit
def test_lookup_table_default_field_values() -> None:
    cal_id = uuid4()
    rule = LookupTable(calibration_revision_id=cal_id)
    assert rule.interpolation_kind == InterpolationKind.LINEAR
    assert rule.extrapolation_kind == ExtrapolationKind.CLAMP
    assert rule.invertible is True
    assert rule.readback_aggregator_kind is None
    assert rule.unit_in == ""
    assert rule.unit_out == ""


@pytest.mark.unit
def test_lookup_table_rejects_missing_calibration_revision_id() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        LookupTable()  # default is UUID(int=0)
    assert info.value.sub_code == "calibration_revision_id_missing"
    assert "required" in info.value.reason


@pytest.mark.unit
def test_lookup_table_rejects_zero_uuid() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        LookupTable(calibration_revision_id=UUID(int=0))
    assert info.value.sub_code == "calibration_revision_id_missing"


@pytest.mark.unit
@pytest.mark.parametrize(
    "interpolation_kind",
    [InterpolationKind.LINEAR, InterpolationKind.CUBIC, InterpolationKind.NEAREST],
)
def test_lookup_table_accepts_all_interpolation_kinds(
    interpolation_kind: InterpolationKind,
) -> None:
    rule = LookupTable(calibration_revision_id=uuid4(), interpolation_kind=interpolation_kind)
    assert rule.interpolation_kind == interpolation_kind


@pytest.mark.unit
@pytest.mark.parametrize("extrapolation_kind", [ExtrapolationKind.CLAMP, ExtrapolationKind.ERROR])
def test_lookup_table_accepts_all_extrapolation_kinds(
    extrapolation_kind: ExtrapolationKind,
) -> None:
    rule = LookupTable(calibration_revision_id=uuid4(), extrapolation_kind=extrapolation_kind)
    assert rule.extrapolation_kind == extrapolation_kind


@pytest.mark.unit
def test_lookup_table_invertible_true_allows_no_readback_aggregator() -> None:
    rule = LookupTable(
        calibration_revision_id=uuid4(),
        invertible=True,
        readback_aggregator_kind=None,
    )
    assert rule.invertible is True
    assert rule.readback_aggregator_kind is None


@pytest.mark.unit
def test_lookup_table_invertible_false_requires_readback_aggregator() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        LookupTable(
            calibration_revision_id=uuid4(),
            invertible=False,
            readback_aggregator_kind=None,
        )
    assert info.value.sub_code == "readback_aggregator_required"
    assert "invertible=False" in info.value.reason


@pytest.mark.unit
def test_lookup_table_invertible_false_accepts_readback_aggregator() -> None:
    rule = LookupTable(
        calibration_revision_id=uuid4(),
        invertible=False,
        readback_aggregator_kind=ReadbackAggregatorKind.SUM,
    )
    assert rule.invertible is False
    assert rule.readback_aggregator_kind == ReadbackAggregatorKind.SUM


@pytest.mark.unit
def test_lookup_table_is_frozen() -> None:
    rule = LookupTable(calibration_revision_id=uuid4())
    with pytest.raises(FrozenInstanceError):
        rule.invertible = False  # type: ignore[misc]


@pytest.mark.unit
def test_lookup_table_equality_is_structural() -> None:
    cal_id = uuid4()
    a = LookupTable(
        calibration_revision_id=cal_id,
        interpolation_kind=InterpolationKind.LINEAR,
    )
    b = LookupTable(
        calibration_revision_id=cal_id,
        interpolation_kind=InterpolationKind.LINEAR,
    )
    assert a == b
    assert hash(a) == hash(b)


# =============================================================================
# COMPOSITE_PARTITION SHAPE TESTS
# =============================================================================


@pytest.mark.unit
def test_composite_partition_constructs_happy_path_with_all_fields() -> None:
    params = (("a", 1.0), ("b", 2.0))
    rule = CompositePartition(
        partition_kind=PartitionKind.FINE_CENTERED_KEEP,
        constituent_count=3,
        partition_parameters=params,
        readback_aggregator_kind=ReadbackAggregatorKind.MEAN,
    )
    assert rule.partition_kind == PartitionKind.FINE_CENTERED_KEEP
    assert rule.constituent_count == 3
    assert rule.partition_parameters == params
    assert rule.readback_aggregator_kind == ReadbackAggregatorKind.MEAN
    assert rule.kind == PartitionRuleKind.COMPOSITE_PARTITION


@pytest.mark.unit
def test_composite_partition_default_field_values() -> None:
    rule = CompositePartition()
    assert rule.partition_kind == PartitionKind.PROPORTIONAL_FILL
    assert rule.constituent_count == 2
    assert rule.partition_parameters == ()
    assert rule.readback_aggregator_kind == ReadbackAggregatorKind.SUM


@pytest.mark.unit
@pytest.mark.parametrize(
    "partition_kind",
    [
        PartitionKind.COARSE_FIRST_FILL,
        PartitionKind.FINE_CENTERED_KEEP,
        PartitionKind.PROPORTIONAL_FILL,
        PartitionKind.CONCENTRIC_SYMMETRIC,
    ],
)
def test_composite_partition_accepts_all_partition_kinds(
    partition_kind: PartitionKind,
) -> None:
    rule = CompositePartition(partition_kind=partition_kind, constituent_count=2)
    assert rule.partition_kind == partition_kind


@pytest.mark.unit
def test_composite_partition_rejects_constituent_count_below_minimum() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        CompositePartition(constituent_count=1)
    assert info.value.sub_code == "composite_constituent_count_below_minimum"
    assert "constituent_count must be >= 2" in info.value.reason


@pytest.mark.unit
def test_composite_partition_rejects_constituent_count_zero() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        CompositePartition(constituent_count=0)
    assert info.value.sub_code == "composite_constituent_count_below_minimum"


@pytest.mark.unit
def test_composite_partition_rejects_constituent_count_negative() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        CompositePartition(constituent_count=-1)
    assert info.value.sub_code == "composite_constituent_count_below_minimum"


@pytest.mark.unit
def test_composite_partition_accepts_constituent_count_2() -> None:
    rule = CompositePartition(constituent_count=2)
    assert rule.constituent_count == 2


@pytest.mark.unit
def test_composite_partition_accepts_large_constituent_count() -> None:
    rule = CompositePartition(constituent_count=100)
    assert rule.constituent_count == 100


@pytest.mark.unit
def test_composite_partition_accepts_empty_partition_parameters() -> None:
    rule = CompositePartition(partition_parameters=())
    assert rule.partition_parameters == ()


@pytest.mark.unit
def test_composite_partition_rejects_nan_in_partition_parameters() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        CompositePartition(
            partition_parameters=(("scale", float("nan")),),
            constituent_count=2,
        )
    assert info.value.sub_code == "numeric_not_finite"


@pytest.mark.unit
def test_composite_partition_rejects_inf_in_partition_parameters() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        CompositePartition(
            partition_parameters=(("weight", float("inf")),),
            constituent_count=2,
        )
    assert info.value.sub_code == "numeric_not_finite"


@pytest.mark.unit
def test_composite_partition_accepts_negative_partition_parameter_values() -> None:
    rule = CompositePartition(
        partition_parameters=(("offset", -5.5),),
        constituent_count=2,
    )
    assert rule.partition_parameters == (("offset", -5.5),)


@pytest.mark.unit
def test_composite_partition_accepts_zero_partition_parameter_values() -> None:
    rule = CompositePartition(
        partition_parameters=(("weight", 0.0),),
        constituent_count=2,
    )
    assert rule.partition_parameters == (("weight", 0.0),)


@pytest.mark.unit
def test_composite_partition_is_frozen() -> None:
    rule = CompositePartition()
    with pytest.raises(FrozenInstanceError):
        rule.constituent_count = 3  # type: ignore[misc]


@pytest.mark.unit
def test_composite_partition_equality_is_structural() -> None:
    params = (("a", 1.0), ("b", 2.0))
    a = CompositePartition(
        partition_kind=PartitionKind.COARSE_FIRST_FILL,
        constituent_count=2,
        partition_parameters=params,
    )
    b = CompositePartition(
        partition_kind=PartitionKind.COARSE_FIRST_FILL,
        constituent_count=2,
        partition_parameters=params,
    )
    assert a == b
    assert hash(a) == hash(b)


# =============================================================================
# SOLVER_REFERENCE SHAPE TESTS
# =============================================================================


@pytest.mark.unit
def test_solver_reference_constructs_happy_path_with_all_fields() -> None:
    rule = SolverReference(
        solver_id="hexapod-kinematics-v2",
        solver_version="1.2.3",
        solver_transport_kind=SolverTransportKind.PYTHON_CALLABLE,
        residual_tolerance_limit=0.01,
        singularity_threshold=0.05,
        invertible=True,
        readback_aggregator_kind=None,
    )
    assert rule.solver_id == "hexapod-kinematics-v2"
    assert rule.solver_version == "1.2.3"
    assert rule.solver_transport_kind == SolverTransportKind.PYTHON_CALLABLE
    assert rule.residual_tolerance_limit == 0.01
    assert rule.singularity_threshold == 0.05
    assert rule.invertible is True
    assert rule.readback_aggregator_kind is None
    assert rule.kind == PartitionRuleKind.SOLVER_REFERENCE


@pytest.mark.unit
def test_solver_reference_default_field_values() -> None:
    # Will fail due to missing solver_id, so we need to provide it
    rule = SolverReference(solver_id="test", solver_version="1.0")
    assert rule.solver_transport_kind == SolverTransportKind.SOFT_IOC_RECORD
    assert rule.residual_tolerance_limit == 0.0
    assert rule.singularity_threshold == 0.0
    assert rule.invertible is True
    assert rule.readback_aggregator_kind is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "transport_kind",
    [
        SolverTransportKind.SOFT_IOC_RECORD,
        SolverTransportKind.PYTHON_CALLABLE,
        SolverTransportKind.CONTROLLER_API,
        SolverTransportKind.EXTERNAL_HTTP_SERVICE,
    ],
)
def test_solver_reference_accepts_all_transport_kinds(
    transport_kind: SolverTransportKind,
) -> None:
    rule = SolverReference(
        solver_id="test",
        solver_version="1.0",
        solver_transport_kind=transport_kind,
    )
    assert rule.solver_transport_kind == transport_kind


@pytest.mark.unit
def test_solver_reference_rejects_empty_solver_id() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        SolverReference(solver_id="", solver_version="1.0")
    assert info.value.sub_code == "solver_id_missing"
    assert "required" in info.value.reason


@pytest.mark.unit
def test_solver_reference_rejects_empty_solver_version() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        SolverReference(solver_id="test", solver_version="")
    assert info.value.sub_code == "solver_version_missing"
    assert "required" in info.value.reason


@pytest.mark.unit
def test_solver_reference_rejects_oversized_solver_id() -> None:
    overlong_id = "x" * (PARTITION_RULE_SOLVER_ID_MAX_LENGTH + 1)
    with pytest.raises(InvalidPartitionRuleError) as info:
        SolverReference(solver_id=overlong_id, solver_version="1.0")
    assert info.value.sub_code == "solver_id_too_long"
    assert str(PARTITION_RULE_SOLVER_ID_MAX_LENGTH) in info.value.reason


@pytest.mark.unit
def test_solver_reference_accepts_max_length_solver_id() -> None:
    max_id = "x" * PARTITION_RULE_SOLVER_ID_MAX_LENGTH
    rule = SolverReference(solver_id=max_id, solver_version="1.0")
    assert len(rule.solver_id) == PARTITION_RULE_SOLVER_ID_MAX_LENGTH


@pytest.mark.unit
def test_solver_reference_rejects_oversized_solver_version() -> None:
    overlong_version = "x" * (PARTITION_RULE_SOLVER_VERSION_MAX_LENGTH + 1)
    with pytest.raises(InvalidPartitionRuleError) as info:
        SolverReference(solver_id="test", solver_version=overlong_version)
    assert info.value.sub_code == "solver_version_too_long"
    assert str(PARTITION_RULE_SOLVER_VERSION_MAX_LENGTH) in info.value.reason


@pytest.mark.unit
def test_solver_reference_accepts_max_length_solver_version() -> None:
    max_version = "x" * PARTITION_RULE_SOLVER_VERSION_MAX_LENGTH
    rule = SolverReference(solver_id="test", solver_version=max_version)
    assert len(rule.solver_version) == PARTITION_RULE_SOLVER_VERSION_MAX_LENGTH


@pytest.mark.unit
def test_solver_reference_rejects_residual_tolerance_limit_nan() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        SolverReference(
            solver_id="test",
            solver_version="1.0",
            residual_tolerance_limit=float("nan"),
        )
    assert info.value.sub_code == "numeric_not_finite"


@pytest.mark.unit
def test_solver_reference_rejects_residual_tolerance_limit_inf() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        SolverReference(
            solver_id="test",
            solver_version="1.0",
            residual_tolerance_limit=float("inf"),
        )
    assert info.value.sub_code == "numeric_not_finite"


@pytest.mark.unit
def test_solver_reference_rejects_singularity_threshold_nan() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        SolverReference(
            solver_id="test",
            solver_version="1.0",
            singularity_threshold=float("nan"),
        )
    assert info.value.sub_code == "numeric_not_finite"


@pytest.mark.unit
def test_solver_reference_rejects_singularity_threshold_inf() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        SolverReference(
            solver_id="test",
            solver_version="1.0",
            singularity_threshold=float("inf"),
        )
    assert info.value.sub_code == "numeric_not_finite"


@pytest.mark.unit
def test_solver_reference_rejects_negative_residual_tolerance_limit() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        SolverReference(
            solver_id="test",
            solver_version="1.0",
            residual_tolerance_limit=-0.01,
        )
    assert info.value.sub_code == "residual_tolerance_negative"
    assert "must be >= 0" in info.value.reason


@pytest.mark.unit
def test_solver_reference_accepts_zero_residual_tolerance_limit() -> None:
    rule = SolverReference(
        solver_id="test",
        solver_version="1.0",
        residual_tolerance_limit=0.0,
    )
    assert rule.residual_tolerance_limit == 0.0


@pytest.mark.unit
def test_solver_reference_rejects_singularity_threshold_below_residual() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        SolverReference(
            solver_id="test",
            solver_version="1.0",
            residual_tolerance_limit=0.05,
            singularity_threshold=0.01,
        )
    assert info.value.sub_code == "singularity_threshold_below_residual"
    assert "must be >=" in info.value.reason


@pytest.mark.unit
def test_solver_reference_accepts_singularity_threshold_equal_to_residual() -> None:
    rule = SolverReference(
        solver_id="test",
        solver_version="1.0",
        residual_tolerance_limit=0.05,
        singularity_threshold=0.05,
    )
    assert rule.singularity_threshold == rule.residual_tolerance_limit


@pytest.mark.unit
def test_solver_reference_accepts_singularity_threshold_above_residual() -> None:
    rule = SolverReference(
        solver_id="test",
        solver_version="1.0",
        residual_tolerance_limit=0.05,
        singularity_threshold=0.10,
    )
    assert rule.singularity_threshold > rule.residual_tolerance_limit


@pytest.mark.unit
def test_solver_reference_invertible_true_allows_no_readback_aggregator() -> None:
    rule = SolverReference(
        solver_id="test",
        solver_version="1.0",
        invertible=True,
        readback_aggregator_kind=None,
    )
    assert rule.invertible is True
    assert rule.readback_aggregator_kind is None


@pytest.mark.unit
def test_solver_reference_invertible_false_requires_readback_aggregator() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        SolverReference(
            solver_id="test",
            solver_version="1.0",
            invertible=False,
            readback_aggregator_kind=None,
        )
    assert info.value.sub_code == "readback_aggregator_required"
    assert "invertible=False" in info.value.reason


@pytest.mark.unit
def test_solver_reference_invertible_false_accepts_readback_aggregator() -> None:
    rule = SolverReference(
        solver_id="test",
        solver_version="1.0",
        invertible=False,
        readback_aggregator_kind=ReadbackAggregatorKind.SELECT_INDEX_0,
    )
    assert rule.invertible is False
    assert rule.readback_aggregator_kind == ReadbackAggregatorKind.SELECT_INDEX_0


@pytest.mark.unit
def test_solver_reference_is_frozen() -> None:
    rule = SolverReference(solver_id="test", solver_version="1.0")
    with pytest.raises(FrozenInstanceError):
        rule.invertible = False  # type: ignore[misc]


@pytest.mark.unit
def test_solver_reference_equality_is_structural() -> None:
    a = SolverReference(
        solver_id="hexapod-v2",
        solver_version="1.0.0",
        solver_transport_kind=SolverTransportKind.PYTHON_CALLABLE,
    )
    b = SolverReference(
        solver_id="hexapod-v2",
        solver_version="1.0.0",
        solver_transport_kind=SolverTransportKind.PYTHON_CALLABLE,
    )
    assert a == b
    assert hash(a) == hash(b)


# =============================================================================
# ROUND-TRIP CODEC TESTS
# =============================================================================


@pytest.mark.unit
def test_affine_round_trip_codec() -> None:
    original = Affine(gain=2.5, offset=10.0, unit_in="mm", unit_out="deg")
    payload = partition_rule_to_payload(original)
    assert payload["kind"] == PartitionRuleKind.AFFINE.value
    rebuilt = partition_rule_from_payload(payload)
    assert rebuilt == original


@pytest.mark.unit
def test_aggregation_round_trip_codec() -> None:
    original = Aggregation(aggregator_kind=AggregatorKind.DIFFERENCE, constituent_count=2)
    payload = partition_rule_to_payload(original)
    assert payload["kind"] == PartitionRuleKind.AGGREGATION.value
    rebuilt = partition_rule_from_payload(payload)
    assert rebuilt == original


@pytest.mark.unit
def test_lookup_table_round_trip_codec() -> None:
    cal_id = uuid4()
    original = LookupTable(
        calibration_revision_id=cal_id,
        interpolation_kind=InterpolationKind.CUBIC,
        extrapolation_kind=ExtrapolationKind.ERROR,
        invertible=False,
        readback_aggregator_kind=ReadbackAggregatorKind.MEAN,
        unit_in="deg",
        unit_out="um",
    )
    payload = partition_rule_to_payload(original)
    assert payload["kind"] == PartitionRuleKind.LOOKUP_TABLE.value
    # UUID serialized as string
    assert payload["calibration_revision_id"] == str(cal_id)
    rebuilt = partition_rule_from_payload(payload)
    assert rebuilt == original


@pytest.mark.unit
def test_composite_partition_round_trip_codec() -> None:
    params = (("a", 1.0), ("b", 2.0))
    original = CompositePartition(
        partition_kind=PartitionKind.FINE_CENTERED_KEEP,
        constituent_count=3,
        partition_parameters=params,
        readback_aggregator_kind=ReadbackAggregatorKind.MEAN,
    )
    payload = partition_rule_to_payload(original)
    assert payload["kind"] == PartitionRuleKind.COMPOSITE_PARTITION.value
    rebuilt = partition_rule_from_payload(payload)
    assert rebuilt == original


@pytest.mark.unit
def test_solver_reference_round_trip_codec() -> None:
    original = SolverReference(
        solver_id="hexapod-kinematics",
        solver_version="2.1.0",
        solver_transport_kind=SolverTransportKind.CONTROLLER_API,
        residual_tolerance_limit=0.01,
        singularity_threshold=0.05,
        invertible=False,
        readback_aggregator_kind=ReadbackAggregatorKind.SELECT_INDEX_0,
    )
    payload = partition_rule_to_payload(original)
    assert payload["kind"] == PartitionRuleKind.SOLVER_REFERENCE.value
    rebuilt = partition_rule_from_payload(payload)
    assert rebuilt == original


# =============================================================================
# PAYLOAD DETERMINISM TEST
# =============================================================================


@pytest.mark.unit
def test_composite_partition_payload_sorts_partition_parameters() -> None:
    """Payload determinism: parameters serialized in sorted order regardless
    of construction order. This pins the audit-determinism contract."""
    # Construct with unsorted parameters
    unsorted_params = (("z", 3.0), ("a", 1.0), ("m", 2.0))
    rule = CompositePartition(
        partition_parameters=unsorted_params,
        constituent_count=2,
    )
    payload = partition_rule_to_payload(rule)

    # Verify payload has sorted parameters
    serialized_params = payload["partition_parameters"]
    assert serialized_params == [["a", 1.0], ["m", 2.0], ["z", 3.0]]


# =============================================================================
# ENUM EXHAUSTIVENESS TESTS
# =============================================================================


@pytest.mark.unit
def test_partition_rule_kind_has_exactly_5_values() -> None:
    """Closed catalog: PartitionRuleKind has exactly 5 values. Adding
    a sixth requires deliberate test update."""
    kinds = list(PartitionRuleKind)
    assert len(kinds) == 5
    assert set(kinds) == {
        PartitionRuleKind.AFFINE,
        PartitionRuleKind.AGGREGATION,
        PartitionRuleKind.LOOKUP_TABLE,
        PartitionRuleKind.COMPOSITE_PARTITION,
        PartitionRuleKind.SOLVER_REFERENCE,
    }


@pytest.mark.unit
def test_aggregator_kind_has_exactly_4_values() -> None:
    """Closed catalog: AggregatorKind has exactly 4 values."""
    kinds = list(AggregatorKind)
    assert len(kinds) == 4
    assert set(kinds) == {
        AggregatorKind.SUM,
        AggregatorKind.DIFFERENCE,
        AggregatorKind.MID_RANGE,
        AggregatorKind.PRODUCT,
    }


@pytest.mark.unit
def test_partition_kind_has_exactly_4_values() -> None:
    """Closed catalog: PartitionKind has exactly 4 values."""
    kinds = list(PartitionKind)
    assert len(kinds) == 4
    assert set(kinds) == {
        PartitionKind.COARSE_FIRST_FILL,
        PartitionKind.FINE_CENTERED_KEEP,
        PartitionKind.PROPORTIONAL_FILL,
        PartitionKind.CONCENTRIC_SYMMETRIC,
    }


@pytest.mark.unit
def test_interpolation_kind_has_exactly_3_values() -> None:
    """Closed catalog: InterpolationKind has exactly 3 values."""
    kinds = list(InterpolationKind)
    assert len(kinds) == 3
    assert set(kinds) == {
        InterpolationKind.LINEAR,
        InterpolationKind.CUBIC,
        InterpolationKind.NEAREST,
    }


@pytest.mark.unit
def test_extrapolation_kind_has_exactly_2_values() -> None:
    """Closed catalog: ExtrapolationKind has exactly 2 values."""
    kinds = list(ExtrapolationKind)
    assert len(kinds) == 2
    assert set(kinds) == {
        ExtrapolationKind.CLAMP,
        ExtrapolationKind.ERROR,
    }


@pytest.mark.unit
def test_solver_transport_kind_has_exactly_4_values() -> None:
    """Closed catalog: SolverTransportKind has exactly 4 values."""
    kinds = list(SolverTransportKind)
    assert len(kinds) == 4
    assert set(kinds) == {
        SolverTransportKind.SOFT_IOC_RECORD,
        SolverTransportKind.PYTHON_CALLABLE,
        SolverTransportKind.CONTROLLER_API,
        SolverTransportKind.EXTERNAL_HTTP_SERVICE,
    }


@pytest.mark.unit
def test_readback_aggregator_kind_has_exactly_4_values() -> None:
    """Closed catalog: ReadbackAggregatorKind has exactly 4 values."""
    kinds = list(ReadbackAggregatorKind)
    assert len(kinds) == 4
    assert set(kinds) == {
        ReadbackAggregatorKind.IDENTITY,
        ReadbackAggregatorKind.SUM,
        ReadbackAggregatorKind.MEAN,
        ReadbackAggregatorKind.SELECT_INDEX_0,
    }


# =============================================================================
# PAYLOAD NEGATIVE CASES
# =============================================================================


@pytest.mark.unit
def test_partition_rule_from_payload_rejects_empty_dict() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        partition_rule_from_payload({})
    assert info.value.sub_code == "kind_missing"


@pytest.mark.unit
def test_partition_rule_from_payload_rejects_missing_kind() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        partition_rule_from_payload({"gain": 2.0})
    assert info.value.sub_code == "kind_missing"


@pytest.mark.unit
def test_partition_rule_from_payload_rejects_unknown_kind() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        partition_rule_from_payload({"kind": "UnknownKind"})
    assert info.value.sub_code == "kind_unknown"
    assert "UnknownKind" in info.value.reason


@pytest.mark.unit
def test_partition_rule_from_payload_rejects_affine_with_nan_gain() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        partition_rule_from_payload(
            {
                "kind": "Affine",
                "gain": float("nan"),
                "offset": 0.0,
            }
        )
    assert info.value.sub_code == "numeric_not_finite"


@pytest.mark.unit
def test_partition_rule_from_payload_rejects_lookup_table_missing_calibration_revision_id() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        partition_rule_from_payload(
            {
                "kind": "LookupTable",
                "interpolation_kind": "Linear",
            }
        )
    # Missing calibration_revision_id defaults to UUID(int=0), which is rejected
    assert info.value.sub_code == "calibration_revision_id_missing"


@pytest.mark.unit
def test_partition_rule_from_payload_rejects_lookup_table_with_zero_uuid() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        partition_rule_from_payload(
            {
                "kind": "LookupTable",
                "calibration_revision_id": str(UUID(int=0)),
            }
        )
    assert info.value.sub_code == "calibration_revision_id_missing"


@pytest.mark.unit
def test_partition_rule_from_payload_rejects_solver_reference_with_empty_solver_id() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        partition_rule_from_payload(
            {
                "kind": "SolverReference",
                "solver_id": "",
                "solver_version": "1.0",
            }
        )
    assert info.value.sub_code == "solver_id_missing"


@pytest.mark.unit
def test_partition_rule_from_payload_rejects_composite_partition_with_constituent_count_1() -> None:
    with pytest.raises(InvalidPartitionRuleError) as info:
        partition_rule_from_payload(
            {
                "kind": "CompositePartition",
                "constituent_count": 1,
                "partition_parameters": [],
            }
        )
    assert info.value.sub_code == "composite_constituent_count_below_minimum"


# =============================================================================
# ERROR HIERARCHY TESTS
# =============================================================================


@pytest.mark.unit
def test_invalid_partition_rule_error_is_value_error() -> None:
    """InvalidPartitionRuleError subclasses ValueError for easy catching
    at the route handler / BC boundary."""
    err = InvalidPartitionRuleError("test_code", "test reason")
    assert isinstance(err, ValueError)


@pytest.mark.unit
def test_invalid_partition_rule_error_carries_sub_code_and_reason() -> None:
    sub_code = "numeric_not_finite"
    reason = "test reason message"
    err = InvalidPartitionRuleError(sub_code, reason)
    assert err.sub_code == sub_code
    assert err.reason == reason
    assert sub_code in str(err)
    assert reason in str(err)


# =============================================================================
# EXPECTED_CONSTITUENT_COUNT HELPER TESTS
# =============================================================================


@pytest.mark.unit
def test_expected_constituent_count_affine_returns_1() -> None:
    rule = Affine(gain=2.0, offset=1.0)
    assert expected_constituent_count(rule) == 1


@pytest.mark.unit
def test_expected_constituent_count_affine_default_returns_1() -> None:
    rule = Affine()
    assert expected_constituent_count(rule) == 1


@pytest.mark.unit
def test_expected_constituent_count_aggregation_sum_returns_constituent_count() -> None:
    rule = Aggregation(aggregator_kind=AggregatorKind.SUM, constituent_count=4)
    assert expected_constituent_count(rule) == 4


@pytest.mark.unit
def test_expected_constituent_count_aggregation_difference_returns_2() -> None:
    rule = Aggregation(aggregator_kind=AggregatorKind.DIFFERENCE, constituent_count=2)
    assert expected_constituent_count(rule) == 2


@pytest.mark.unit
def test_expected_constituent_count_aggregation_mid_range_returns_2() -> None:
    rule = Aggregation(aggregator_kind=AggregatorKind.MID_RANGE, constituent_count=2)
    assert expected_constituent_count(rule) == 2


@pytest.mark.unit
def test_expected_constituent_count_aggregation_product_returns_constituent_count() -> None:
    rule = Aggregation(aggregator_kind=AggregatorKind.PRODUCT, constituent_count=5)
    assert expected_constituent_count(rule) == 5


@pytest.mark.unit
def test_expected_constituent_count_aggregation_default_returns_1() -> None:
    rule = Aggregation()
    assert expected_constituent_count(rule) == 1


@pytest.mark.unit
def test_expected_constituent_count_lookup_table_returns_1() -> None:
    rule = LookupTable(calibration_revision_id=uuid4())
    assert expected_constituent_count(rule) == 1


@pytest.mark.unit
def test_expected_constituent_count_lookup_table_non_invertible_returns_1() -> None:
    rule = LookupTable(
        calibration_revision_id=uuid4(),
        invertible=False,
        readback_aggregator_kind=ReadbackAggregatorKind.MEAN,
    )
    assert expected_constituent_count(rule) == 1


@pytest.mark.unit
def test_expected_constituent_count_composite_partition_returns_constituent_count() -> None:
    rule = CompositePartition(
        partition_kind=PartitionKind.PROPORTIONAL_FILL,
        constituent_count=3,
    )
    assert expected_constituent_count(rule) == 3


@pytest.mark.unit
def test_expected_constituent_count_composite_partition_minimum_returns_2() -> None:
    rule = CompositePartition(constituent_count=2)
    assert expected_constituent_count(rule) == 2


@pytest.mark.unit
def test_expected_constituent_count_composite_partition_large_returns_constituent_count() -> None:
    rule = CompositePartition(constituent_count=50)
    assert expected_constituent_count(rule) == 50


@pytest.mark.unit
def test_expected_constituent_count_solver_reference_returns_none() -> None:
    rule = SolverReference(solver_id="hexapod", solver_version="1.0")
    assert expected_constituent_count(rule) is None


@pytest.mark.unit
def test_expected_constituent_count_solver_reference_non_invertible_returns_none() -> None:
    rule = SolverReference(
        solver_id="hexapod",
        solver_version="1.0",
        invertible=False,
        readback_aggregator_kind=ReadbackAggregatorKind.SELECT_INDEX_0,
    )
    assert expected_constituent_count(rule) is None
