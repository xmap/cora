"""Unit tests for the pure per-kind partition-rule evaluators.

Covers the 5 functions exposed by `cora.operation._partition_rule_eval`:
`eval_affine`, `eval_affine_inverse`, `eval_aggregation`,
`eval_lookup_table`, `eval_composite_partition`, `eval_solver_reference`,
plus the `check_solver_residual` guard hoisted for the deferred solver
transport bridge.

Each per-kind function gets a happy-path example (forward and, where
defined, inverse) plus a representative edge case (NaN / Inf rejection
at the boundary, arity guards on the aggregator, divide-by-zero on the
Affine inverse, non-negative requirement on the Product nth-root, and,
for LookupTable, LINEAR interpolation, NEAREST snap, clamp vs error
extrapolation, and malformed-curve guards). Hypothesis round-trip
properties pin forward-then-inverse symmetry for Affine, the equal-split
/ pairwise shapes of Aggregation, and within-bounds monotonicity for the
LookupTable LINEAR kernel.
"""

from __future__ import annotations

import math
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.equipment.aggregates._partition_rule import (
    Affine,
    Aggregation,
    AggregatorKind,
    CompositePartition,
    ExtrapolationKind,
    InterpolationKind,
    LookupTable,
    PartitionKind,
    PartitionRuleKind,
    SolverReference,
    SolverTransportKind,
)
from cora.operation._partition_rule_eval import (
    check_solver_residual,
    eval_affine,
    eval_affine_inverse,
    eval_aggregation,
    eval_composite_partition,
    eval_lookup_table,
    eval_solver_reference,
)
from cora.operation.errors import (
    PseudoAxisCommandOutsideRangeError,
    PseudoAxisEvaluationFailedError,
    PseudoAxisSingularityExceededError,
)

_ASSET_ID = UUID("01900000-0000-7000-8000-0000000000a1")
_CALIBRATION_ID = UUID("01900000-0000-7000-8000-0000000000b0")
_CALIBRATION_REVISION_ID = UUID("01900000-0000-7000-8000-0000000000b1")

_FINITE_FLOAT = st.floats(allow_nan=False, allow_infinity=False, min_value=-1.0e6, max_value=1.0e6)
_NONZERO_FINITE_FLOAT = _FINITE_FLOAT.filter(lambda x: abs(x) > 1.0e-3)


# -- eval_affine ------------------------------------------------------------


@pytest.mark.unit
def test_eval_affine_happy_path_returns_gain_times_commanded_plus_offset() -> None:
    rule = Affine(gain=2.0, offset=1.0)
    assert math.isclose(eval_affine(rule, 3.0, asset_id=_ASSET_ID), 7.0)


@pytest.mark.unit
def test_eval_affine_inverse_happy_path_returns_virtual_minus_offset_over_gain() -> None:
    rule = Affine(gain=2.0, offset=1.0)
    assert math.isclose(eval_affine_inverse(rule, 7.0, asset_id=_ASSET_ID), 3.0)


@pytest.mark.unit
def test_eval_affine_rejects_nan_commanded() -> None:
    rule = Affine(gain=2.0, offset=1.0)
    with pytest.raises(PseudoAxisEvaluationFailedError) as excinfo:
        eval_affine(rule, float("nan"), asset_id=_ASSET_ID)
    assert excinfo.value.asset_id == _ASSET_ID
    assert excinfo.value.kind == PartitionRuleKind.AFFINE
    assert "finite" in excinfo.value.reason


@pytest.mark.unit
def test_eval_affine_rejects_inf_commanded() -> None:
    rule = Affine(gain=2.0, offset=1.0)
    with pytest.raises(PseudoAxisEvaluationFailedError):
        eval_affine(rule, float("inf"), asset_id=_ASSET_ID)


@pytest.mark.unit
def test_eval_affine_inverse_with_zero_gain_raises_singularity() -> None:
    rule = Affine(gain=0.0, offset=1.0)
    with pytest.raises(PseudoAxisEvaluationFailedError) as excinfo:
        eval_affine_inverse(rule, 5.0, asset_id=_ASSET_ID)
    assert "gain == 0" in excinfo.value.reason


# -- eval_aggregation -------------------------------------------------------


@pytest.mark.unit
def test_eval_aggregation_sum_happy_path_returns_equal_split() -> None:
    rule = Aggregation(aggregator_kind=AggregatorKind.SUM, constituent_count=4)
    result = eval_aggregation(rule, 8.0, asset_id=_ASSET_ID)
    assert result == (2.0, 2.0, 2.0, 2.0)


@pytest.mark.unit
def test_eval_aggregation_difference_happy_path_returns_signed_halves() -> None:
    rule = Aggregation(aggregator_kind=AggregatorKind.DIFFERENCE, constituent_count=2)
    minus, plus = eval_aggregation(rule, 6.0, asset_id=_ASSET_ID)
    assert math.isclose(minus, -3.0)
    assert math.isclose(plus, 3.0)
    assert math.isclose(plus - minus, 6.0)


@pytest.mark.unit
def test_eval_aggregation_mid_range_happy_path_returns_pair_equal_to_commanded() -> None:
    rule = Aggregation(aggregator_kind=AggregatorKind.MID_RANGE, constituent_count=2)
    assert eval_aggregation(rule, 4.5, asset_id=_ASSET_ID) == (4.5, 4.5)


@pytest.mark.unit
def test_eval_aggregation_product_happy_path_returns_nth_root() -> None:
    rule = Aggregation(aggregator_kind=AggregatorKind.PRODUCT, constituent_count=3)
    result = eval_aggregation(rule, 8.0, asset_id=_ASSET_ID)
    assert len(result) == 3
    assert all(math.isclose(c, 2.0) for c in result)


@pytest.mark.unit
def test_eval_aggregation_product_rejects_negative_commanded() -> None:
    rule = Aggregation(aggregator_kind=AggregatorKind.PRODUCT, constituent_count=3)
    with pytest.raises(PseudoAxisEvaluationFailedError) as excinfo:
        eval_aggregation(rule, -1.0, asset_id=_ASSET_ID)
    assert "Product" in excinfo.value.reason


@pytest.mark.unit
def test_eval_aggregation_rejects_nan_commanded() -> None:
    rule = Aggregation(aggregator_kind=AggregatorKind.SUM, constituent_count=2)
    with pytest.raises(PseudoAxisEvaluationFailedError):
        eval_aggregation(rule, float("nan"), asset_id=_ASSET_ID)


# -- eval_lookup_table ------------------------------------------------------

# A two-segment energy -> position curve. Energy (keV) is the independent
# variable; position the dependent. Linear between (18, 0.6) and (25, 0.9).
_CURVE: tuple[tuple[float, float], ...] = ((18.0, 0.6), (25.0, 0.9))


def _lookup_rule(
    *,
    interpolation_kind: InterpolationKind = InterpolationKind.LINEAR,
    extrapolation_kind: ExtrapolationKind = ExtrapolationKind.CLAMP,
) -> LookupTable:
    return LookupTable(
        calibration_id=_CALIBRATION_ID,
        calibration_revision_id=_CALIBRATION_REVISION_ID,
        interpolation_kind=interpolation_kind,
        extrapolation_kind=extrapolation_kind,
    )


@pytest.mark.unit
def test_eval_lookup_table_linear_interpolates_between_points() -> None:
    rule = _lookup_rule(interpolation_kind=InterpolationKind.LINEAR)
    # 22 keV sits 4/7 of the way from 18 to 25: 0.6 + (4/7)*(0.9-0.6).
    result = eval_lookup_table(rule, 22.0, asset_id=_ASSET_ID, curve=_CURVE)
    assert math.isclose(result, 0.6 + (4.0 / 7.0) * 0.3, rel_tol=1e-12)


@pytest.mark.unit
def test_eval_lookup_table_linear_returns_exact_value_at_a_tabulated_point() -> None:
    rule = _lookup_rule(interpolation_kind=InterpolationKind.LINEAR)
    assert math.isclose(eval_lookup_table(rule, 18.0, asset_id=_ASSET_ID, curve=_CURVE), 0.6)
    assert math.isclose(eval_lookup_table(rule, 25.0, asset_id=_ASSET_ID, curve=_CURVE), 0.9)


@pytest.mark.unit
def test_eval_lookup_table_sorts_unordered_curve_before_interpolating() -> None:
    rule = _lookup_rule(interpolation_kind=InterpolationKind.LINEAR)
    reversed_curve = ((25.0, 0.9), (18.0, 0.6))
    result = eval_lookup_table(rule, 22.0, asset_id=_ASSET_ID, curve=reversed_curve)
    assert math.isclose(result, 0.6 + (4.0 / 7.0) * 0.3, rel_tol=1e-12)


@pytest.mark.unit
def test_eval_lookup_table_nearest_snaps_to_closest_point() -> None:
    rule = _lookup_rule(interpolation_kind=InterpolationKind.NEAREST)
    assert eval_lookup_table(rule, 19.0, asset_id=_ASSET_ID, curve=_CURVE) == 0.6
    assert eval_lookup_table(rule, 24.0, asset_id=_ASSET_ID, curve=_CURVE) == 0.9


@pytest.mark.unit
def test_eval_lookup_table_clamp_below_range_returns_low_endpoint() -> None:
    rule = _lookup_rule(extrapolation_kind=ExtrapolationKind.CLAMP)
    assert eval_lookup_table(rule, 10.0, asset_id=_ASSET_ID, curve=_CURVE) == 0.6


@pytest.mark.unit
def test_eval_lookup_table_clamp_above_range_returns_high_endpoint() -> None:
    rule = _lookup_rule(extrapolation_kind=ExtrapolationKind.CLAMP)
    assert eval_lookup_table(rule, 40.0, asset_id=_ASSET_ID, curve=_CURVE) == 0.9


@pytest.mark.unit
def test_eval_lookup_table_error_below_range_raises_outside_range() -> None:
    rule = _lookup_rule(extrapolation_kind=ExtrapolationKind.ERROR)
    with pytest.raises(PseudoAxisCommandOutsideRangeError) as excinfo:
        eval_lookup_table(rule, 10.0, asset_id=_ASSET_ID, curve=_CURVE)
    assert excinfo.value.asset_id == _ASSET_ID
    assert excinfo.value.commanded == 10.0


@pytest.mark.unit
def test_eval_lookup_table_error_above_range_raises_outside_range() -> None:
    rule = _lookup_rule(extrapolation_kind=ExtrapolationKind.ERROR)
    with pytest.raises(PseudoAxisCommandOutsideRangeError):
        eval_lookup_table(rule, 99.0, asset_id=_ASSET_ID, curve=_CURVE)


@pytest.mark.unit
def test_eval_lookup_table_cubic_not_implemented_raises() -> None:
    rule = _lookup_rule(interpolation_kind=InterpolationKind.CUBIC)
    with pytest.raises(PseudoAxisEvaluationFailedError) as excinfo:
        eval_lookup_table(rule, 22.0, asset_id=_ASSET_ID, curve=_CURVE)
    assert excinfo.value.kind == PartitionRuleKind.LOOKUP_TABLE
    assert "not implemented" in excinfo.value.reason


@pytest.mark.unit
def test_eval_lookup_table_rejects_nan_commanded() -> None:
    rule = _lookup_rule()
    with pytest.raises(PseudoAxisEvaluationFailedError):
        eval_lookup_table(rule, float("nan"), asset_id=_ASSET_ID, curve=_CURVE)


@pytest.mark.unit
def test_eval_lookup_table_rejects_curve_with_fewer_than_two_points() -> None:
    rule = _lookup_rule()
    with pytest.raises(PseudoAxisEvaluationFailedError) as excinfo:
        eval_lookup_table(rule, 22.0, asset_id=_ASSET_ID, curve=((18.0, 0.6),))
    assert "at least 2 points" in excinfo.value.reason


@pytest.mark.unit
def test_eval_lookup_table_rejects_duplicate_independent_value() -> None:
    rule = _lookup_rule()
    with pytest.raises(PseudoAxisEvaluationFailedError) as excinfo:
        eval_lookup_table(rule, 18.0, asset_id=_ASSET_ID, curve=((18.0, 0.6), (18.0, 0.9)))
    assert "duplicate" in excinfo.value.reason


@pytest.mark.unit
@given(commanded=st.floats(min_value=18.0, max_value=25.0))
def test_eval_lookup_table_linear_stays_within_endpoint_bounds(commanded: float) -> None:
    rule = _lookup_rule(interpolation_kind=InterpolationKind.LINEAR)
    result = eval_lookup_table(rule, commanded, asset_id=_ASSET_ID, curve=_CURVE)
    assert 0.6 <= result <= 0.9


@pytest.mark.unit
@given(
    a=st.floats(min_value=18.0, max_value=25.0),
    b=st.floats(min_value=18.0, max_value=25.0),
)
def test_eval_lookup_table_linear_is_monotonic_for_increasing_curve(a: float, b: float) -> None:
    assume(a < b)
    rule = _lookup_rule(interpolation_kind=InterpolationKind.LINEAR)
    ya = eval_lookup_table(rule, a, asset_id=_ASSET_ID, curve=_CURVE)
    yb = eval_lookup_table(rule, b, asset_id=_ASSET_ID, curve=_CURVE)
    assert ya <= yb


# -- eval_composite_partition ----------------------------------------------


@pytest.mark.unit
def test_eval_composite_partition_proportional_fill_returns_equal_split() -> None:
    rule = CompositePartition(partition_kind=PartitionKind.PROPORTIONAL_FILL, constituent_count=4)
    result = eval_composite_partition(rule, 8.0, asset_id=_ASSET_ID, constituent_count=4)
    assert result == (2.0, 2.0, 2.0, 2.0)


@pytest.mark.unit
def test_eval_composite_partition_fine_centered_keep_loads_last_constituent() -> None:
    rule = CompositePartition(partition_kind=PartitionKind.FINE_CENTERED_KEEP, constituent_count=3)
    result = eval_composite_partition(rule, 5.0, asset_id=_ASSET_ID, constituent_count=3)
    assert result == (0.0, 0.0, 5.0)


@pytest.mark.unit
def test_eval_composite_partition_coarse_first_fill_loads_first_constituent() -> None:
    rule = CompositePartition(partition_kind=PartitionKind.COARSE_FIRST_FILL, constituent_count=3)
    result = eval_composite_partition(rule, 5.0, asset_id=_ASSET_ID, constituent_count=3)
    assert result == (5.0, 0.0, 0.0)


@pytest.mark.unit
def test_eval_composite_partition_concentric_symmetric_returns_equal_split() -> None:
    rule = CompositePartition(
        partition_kind=PartitionKind.CONCENTRIC_SYMMETRIC, constituent_count=2
    )
    result = eval_composite_partition(rule, 4.0, asset_id=_ASSET_ID, constituent_count=2)
    assert result == (2.0, 2.0)


@pytest.mark.unit
def test_eval_composite_partition_rejects_constituent_count_below_two() -> None:
    rule = CompositePartition(partition_kind=PartitionKind.PROPORTIONAL_FILL, constituent_count=2)
    with pytest.raises(PseudoAxisEvaluationFailedError) as excinfo:
        eval_composite_partition(rule, 4.0, asset_id=_ASSET_ID, constituent_count=1)
    assert "constituent_count >= 2" in excinfo.value.reason


@pytest.mark.unit
def test_eval_composite_partition_rejects_rule_count_mismatch_with_asset() -> None:
    rule = CompositePartition(partition_kind=PartitionKind.PROPORTIONAL_FILL, constituent_count=2)
    with pytest.raises(PseudoAxisEvaluationFailedError) as excinfo:
        eval_composite_partition(rule, 4.0, asset_id=_ASSET_ID, constituent_count=3)
    assert "does not match" in excinfo.value.reason


@pytest.mark.unit
def test_eval_composite_partition_rejects_nan_commanded() -> None:
    rule = CompositePartition(partition_kind=PartitionKind.PROPORTIONAL_FILL, constituent_count=2)
    with pytest.raises(PseudoAxisEvaluationFailedError):
        eval_composite_partition(rule, float("nan"), asset_id=_ASSET_ID, constituent_count=2)


# -- eval_solver_reference + check_solver_residual --------------------------


@pytest.mark.unit
def test_eval_solver_reference_raises_not_implemented_until_bridge_lands() -> None:
    rule = SolverReference(
        solver_id="hexapod-6dof",
        solver_version="1.0.0",
        solver_transport_kind=SolverTransportKind.SOFT_IOC_RECORD,
        residual_tolerance_limit=1.0e-6,
        singularity_threshold=1.0e-3,
    )
    with pytest.raises(NotImplementedError):
        eval_solver_reference(rule, 0.0, asset_id=_ASSET_ID)


@pytest.mark.unit
def test_check_solver_residual_under_threshold_passes_silently() -> None:
    rule = SolverReference(
        solver_id="solver",
        solver_version="1",
        residual_tolerance_limit=1.0e-6,
        singularity_threshold=1.0e-3,
    )
    check_solver_residual(rule, asset_id=_ASSET_ID, residual=1.0e-4)


@pytest.mark.unit
def test_check_solver_residual_over_threshold_raises_singularity() -> None:
    rule = SolverReference(
        solver_id="solver",
        solver_version="1",
        residual_tolerance_limit=1.0e-6,
        singularity_threshold=1.0e-3,
    )
    with pytest.raises(PseudoAxisSingularityExceededError) as excinfo:
        check_solver_residual(rule, asset_id=_ASSET_ID, residual=1.0)
    assert math.isclose(excinfo.value.threshold, 1.0e-3)
    assert math.isclose(excinfo.value.residual, 1.0)


@pytest.mark.unit
def test_check_solver_residual_treats_negative_residual_as_magnitude() -> None:
    rule = SolverReference(
        solver_id="solver",
        solver_version="1",
        residual_tolerance_limit=1.0e-6,
        singularity_threshold=1.0e-3,
    )
    with pytest.raises(PseudoAxisSingularityExceededError):
        check_solver_residual(rule, asset_id=_ASSET_ID, residual=-1.0)


# -- Hypothesis round-trip properties --------------------------------------


@pytest.mark.unit
@given(
    gain=_NONZERO_FINITE_FLOAT,
    offset=_FINITE_FLOAT,
    commanded=_FINITE_FLOAT,
)
def test_eval_affine_forward_then_inverse_round_trips(
    gain: float, offset: float, commanded: float
) -> None:
    rule = Affine(gain=gain, offset=offset)
    forward = eval_affine(rule, commanded, asset_id=_ASSET_ID)
    assume(math.isfinite(forward))
    recovered = eval_affine_inverse(rule, forward, asset_id=_ASSET_ID)
    assert math.isclose(recovered, commanded, rel_tol=1.0e-6, abs_tol=1.0e-6)


@pytest.mark.unit
@given(
    constituent_count=st.integers(min_value=1, max_value=6),
    commanded=_FINITE_FLOAT,
)
def test_eval_aggregation_sum_split_reaggregates_to_commanded(
    constituent_count: int, commanded: float
) -> None:
    rule = Aggregation(aggregator_kind=AggregatorKind.SUM, constituent_count=constituent_count)
    split = eval_aggregation(rule, commanded, asset_id=_ASSET_ID)
    assert len(split) == constituent_count
    assert math.isclose(sum(split), commanded, rel_tol=1.0e-9, abs_tol=1.0e-9)


@pytest.mark.unit
@given(commanded=_FINITE_FLOAT)
def test_eval_aggregation_difference_split_reaggregates_to_commanded(
    commanded: float,
) -> None:
    rule = Aggregation(aggregator_kind=AggregatorKind.DIFFERENCE, constituent_count=2)
    minus, plus = eval_aggregation(rule, commanded, asset_id=_ASSET_ID)
    assert math.isclose(plus - minus, commanded, rel_tol=1.0e-9, abs_tol=1.0e-9)


@pytest.mark.unit
@given(
    constituent_count=st.integers(min_value=1, max_value=6),
    commanded=st.floats(min_value=0.0, max_value=1.0e6, allow_nan=False, allow_infinity=False),
)
def test_eval_aggregation_product_split_reaggregates_to_commanded(
    constituent_count: int, commanded: float
) -> None:
    rule = Aggregation(aggregator_kind=AggregatorKind.PRODUCT, constituent_count=constituent_count)
    split = eval_aggregation(rule, commanded, asset_id=_ASSET_ID)
    product = 1.0
    for value in split:
        product *= value
    assert math.isclose(product, commanded, rel_tol=1.0e-6, abs_tol=1.0e-6)
