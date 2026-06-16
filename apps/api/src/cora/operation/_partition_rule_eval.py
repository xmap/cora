"""Pure per-kind partition-rule evaluators.

The PseudoAxis runtime evaluator dispatches a `PartitionRule` (closed
union of 5 shapes at `cora.equipment.aggregates._partition_rule`) into
the matching pure function here. Each function takes a frozen rule VO
plus the operator-commanded scalar plus any side data the rule needs,
returns the resolved setpoint(s), and raises a typed exception on
mathematical failure.

Discipline: pure, side-effect-free, deterministic. No I/O, no clock,
no global state, no logging. The caller is responsible for observability;
these functions only do the math. NaN / Inf inputs and aggregator-shape
mismatches (e.g. `Difference` with constituent_count != 2) raise
`PseudoAxisEvaluationFailedError`.

`eval_lookup_table` takes the calibration points as already-extracted
`(independent, dependent)` pairs (the caller loads the pinned revision and
extracts them) so the kernel stays pure and decoupled from the Calibration
payload shape. It interpolates LINEAR or snaps NEAREST; CUBIC is not yet
implemented. Out-of-range with `extrapolation_kind=Error` raises
`PseudoAxisCommandOutsideRangeError`; with `Clamp` it returns the nearest
endpoint.

The `SolverReference` evaluator is a placeholder: it raises
`NotImplementedError` so the foundation layer can ship; the solver
transport bridge lands in a follow-up. The signature is stable.

See [[project-pseudoaxis-design]] v3 for the design lock.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

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
)
from cora.operation.errors import (
    PseudoAxisCommandOutsideRangeError,
    PseudoAxisEvaluationFailedError,
    PseudoAxisSingularityExceededError,
)

if TYPE_CHECKING:
    from uuid import UUID


def _ensure_commanded_finite(asset_id: UUID, kind: PartitionRuleKind, commanded: float) -> None:
    """Reject NaN / Inf operator commands at the evaluator boundary."""
    if not math.isfinite(commanded):
        raise PseudoAxisEvaluationFailedError(
            asset_id=asset_id,
            kind=kind,
            reason=f"commanded value must be finite (got {commanded!r})",
        )


def _ensure_result_finite(
    asset_id: UUID, kind: PartitionRuleKind, value: float, label: str
) -> None:
    """Reject NaN / Inf result coming out of the math kernel."""
    if not math.isfinite(value):
        raise PseudoAxisEvaluationFailedError(
            asset_id=asset_id,
            kind=kind,
            reason=f"{label} produced non-finite result {value!r}",
        )


def eval_affine(rule: Affine, commanded: float, *, asset_id: UUID) -> float:
    """Evaluate an Affine rule: forward `commanded -> gain*commanded + offset`.

    Always invertible. Inverse is implicit at the call site: the
    inverse direction reads `(commanded - offset) / gain`, which is
    well-defined iff `gain != 0`. Both directions are exercised by
    callers; this function returns the forward result. Inverse is
    delegated to `eval_affine_inverse`.
    """
    kind = PartitionRuleKind.AFFINE
    _ensure_commanded_finite(asset_id, kind, commanded)
    result = rule.gain * commanded + rule.offset
    _ensure_result_finite(asset_id, kind, result, "Affine forward")
    return result


def eval_affine_inverse(rule: Affine, virtual: float, *, asset_id: UUID) -> float:
    """Evaluate Affine inverse: `virtual -> (virtual - offset) / gain`.

    Raises `PseudoAxisEvaluationFailedError` when `gain == 0` (the
    forward map collapses to a constant and no inverse exists).
    """
    kind = PartitionRuleKind.AFFINE
    _ensure_commanded_finite(asset_id, kind, virtual)
    if rule.gain == 0.0:
        raise PseudoAxisEvaluationFailedError(
            asset_id=asset_id,
            kind=kind,
            reason="Affine inverse undefined when gain == 0",
        )
    result = (virtual - rule.offset) / rule.gain
    _ensure_result_finite(asset_id, kind, result, "Affine inverse")
    return result


def eval_aggregation(
    rule: Aggregation,
    commanded: float,
    *,
    asset_id: UUID,
) -> tuple[float, ...]:
    """Split an aggregator's virtual value into N constituent setpoints.

    Inverse direction of `virtual = aggregator(c_1, ..., c_N)`:

      - `Sum`:        equal-split: every constituent gets `commanded / N`.
      - `Difference`: 2-constituent only; returns `(+commanded/2, -commanded/2)`
        so that `c_1 - c_0 == commanded`.
      - `MidRange`:   2-constituent only; returns `(commanded, commanded)`
        (the trivial mid-range realization with both endpoints equal).
      - `Product`:    every constituent gets `commanded ** (1/N)` (the
        positive nth root); requires `commanded >= 0` so the root is real.

    Constituent-count guards reject the wrong arity per
    `AggregatorKind`.
    """
    kind = PartitionRuleKind.AGGREGATION
    _ensure_commanded_finite(asset_id, kind, commanded)
    n = rule.constituent_count
    if n < 1:
        raise PseudoAxisEvaluationFailedError(
            asset_id=asset_id,
            kind=kind,
            reason=f"Aggregation requires constituent_count >= 1 (got {n})",
        )

    aggregator = rule.aggregator_kind

    if aggregator in (AggregatorKind.DIFFERENCE, AggregatorKind.MID_RANGE) and n != 2:
        raise PseudoAxisEvaluationFailedError(
            asset_id=asset_id,
            kind=kind,
            reason=(
                f"Aggregation aggregator_kind={aggregator.value} requires "
                f"constituent_count == 2 (got {n})"
            ),
        )

    if aggregator is AggregatorKind.SUM:
        per_constituent = commanded / n
        _ensure_result_finite(asset_id, kind, per_constituent, "Aggregation Sum split")
        return tuple(per_constituent for _ in range(n))

    if aggregator is AggregatorKind.DIFFERENCE:
        half = commanded / 2.0
        _ensure_result_finite(asset_id, kind, half, "Aggregation Difference split")
        return (-half, half)

    if aggregator is AggregatorKind.MID_RANGE:
        _ensure_result_finite(asset_id, kind, commanded, "Aggregation MidRange split")
        return (commanded, commanded)

    if aggregator is AggregatorKind.PRODUCT:
        if commanded < 0.0:
            raise PseudoAxisEvaluationFailedError(
                asset_id=asset_id,
                kind=kind,
                reason=(
                    f"Aggregation Product nth-root requires commanded >= 0 (got {commanded!r})"
                ),
            )
        root = commanded ** (1.0 / n)
        _ensure_result_finite(asset_id, kind, root, "Aggregation Product split")
        return tuple(root for _ in range(n))

    raise PseudoAxisEvaluationFailedError(
        asset_id=asset_id,
        kind=kind,
        reason=f"unsupported AggregatorKind {aggregator!r}",
    )


def _ordered_points(
    asset_id: UUID, points: tuple[tuple[float, float], ...]
) -> tuple[list[float], list[float]]:
    """Validate and order lookup points into parallel x / y lists.

    Requires at least two points, all finite, with strictly increasing
    independent values once sorted (duplicate independents make forward
    interpolation ambiguous). A malformed lookup is a data-substrate
    failure, not an operator error, so it raises
    `PseudoAxisEvaluationFailedError` (mapped to 500), matching the
    other math-kernel failures.
    """
    kind = PartitionRuleKind.LOOKUP_TABLE
    if len(points) < 2:
        raise PseudoAxisEvaluationFailedError(
            asset_id=asset_id,
            kind=kind,
            reason=f"LookupTable needs at least 2 points (got {len(points)})",
        )
    ordered = sorted(points, key=lambda point: point[0])
    xs = [point[0] for point in ordered]
    ys = [point[1] for point in ordered]
    for x, y in ordered:
        if not math.isfinite(x) or not math.isfinite(y):
            raise PseudoAxisEvaluationFailedError(
                asset_id=asset_id,
                kind=kind,
                reason=f"LookupTable has a non-finite point ({x!r}, {y!r})",
            )
    for i in range(1, len(xs)):
        if xs[i] == xs[i - 1]:
            raise PseudoAxisEvaluationFailedError(
                asset_id=asset_id,
                kind=kind,
                reason=(
                    f"LookupTable has a duplicate independent value {xs[i]!r}; "
                    "forward interpolation is ambiguous"
                ),
            )
    return xs, ys


def _linear_interpolate(xs: list[float], ys: list[float], commanded: float) -> float:
    """Straight-line interpolation of `commanded` within [xs[0], xs[-1]].

    Caller guarantees `xs[0] <= commanded <= xs[-1]` and strictly
    increasing xs. Exact-point hits return the tabulated dependent value.
    """
    for i in range(1, len(xs)):
        if commanded <= xs[i]:
            x0, x1 = xs[i - 1], xs[i]
            y0, y1 = ys[i - 1], ys[i]
            fraction = (commanded - x0) / (x1 - x0)
            return y0 + fraction * (y1 - y0)
    return ys[-1]


def _nearest_value(xs: list[float], ys: list[float], commanded: float) -> float:
    """Return the dependent value of the point whose independent is nearest.

    Ties resolve to the lower independent value (first match), which is
    deterministic.
    """
    best_index = 0
    best_distance = abs(xs[0] - commanded)
    for i in range(1, len(xs)):
        distance = abs(xs[i] - commanded)
        if distance < best_distance:
            best_distance = distance
            best_index = i
    return ys[best_index]


def eval_lookup_table(
    rule: LookupTable,
    commanded: float,
    *,
    asset_id: UUID,
    points: tuple[tuple[float, float], ...],
) -> float:
    """Evaluate a LookupTable rule by interpolating the calibration points.

    `points` is the resolved, already-extracted sequence of `(independent,
    dependent)` pairs the caller pulled from the pinned Calibration
    revision (a continuous energy curve or a discrete index table); the
    kernel stays pure and decoupled from the Calibration payload shape.
    `interpolation_kind` selects `LINEAR` (straight line between the
    bracketing points) or `NEAREST` (snap to the closest independent
    point); `CUBIC` is not yet implemented. Outside the tabulated range,
    `extrapolation_kind=Clamp` returns the nearest endpoint's dependent
    value and `Error` raises `PseudoAxisCommandOutsideRangeError`.
    """
    kind = PartitionRuleKind.LOOKUP_TABLE
    _ensure_commanded_finite(asset_id, kind, commanded)
    xs, ys = _ordered_points(asset_id, points)
    low, high = xs[0], xs[-1]

    if commanded < low or commanded > high:
        if rule.extrapolation_kind is ExtrapolationKind.ERROR:
            raise PseudoAxisCommandOutsideRangeError(
                asset_id=asset_id, commanded=commanded, low=low, high=high
            )
        result = ys[0] if commanded < low else ys[-1]
        _ensure_result_finite(asset_id, kind, result, "LookupTable clamp")
        return result

    if rule.interpolation_kind is InterpolationKind.NEAREST:
        result = _nearest_value(xs, ys, commanded)
    elif rule.interpolation_kind is InterpolationKind.LINEAR:
        result = _linear_interpolate(xs, ys, commanded)
    else:
        raise PseudoAxisEvaluationFailedError(
            asset_id=asset_id,
            kind=kind,
            reason=(
                f"LookupTable interpolation_kind={rule.interpolation_kind.value} "
                "is not implemented (LINEAR and NEAREST are supported)"
            ),
        )
    _ensure_result_finite(asset_id, kind, result, "LookupTable interpolation")
    return result


def eval_composite_partition(
    rule: CompositePartition,
    commanded: float,
    *,
    asset_id: UUID,
    constituent_count: int,
) -> tuple[float, ...]:
    """Split a CompositePartition virtual value across N constituents.

    The post-condition is `sum(returned) == commanded` to within
    floating-point round-off; the partition rule chooses HOW the
    commanded value is distributed.

      - `ProportionalFill`:     every constituent gets `commanded / N`.
      - `FineCenteredKeep`:     constituent[0] is the fine axis and is
        kept at 0; constituent[-1] absorbs the full commanded value;
        intermediate constituents stay at 0. The 2-BM sample-stack rule.
      - `CoarseFirstFill`:      constituent[0] is the coarse axis and
        absorbs the full commanded value; the rest stay at 0.
      - `ConcentricSymmetric`:  symmetric expansion: every constituent
        gets `commanded / N` (the symmetric realization with all
        constituents moving in lockstep).

    The runtime evaluator passes `constituent_count` from the Asset's
    `constituent_asset_ids`; the rule's declared `constituent_count`
    is cross-checked and a mismatch raises.
    """
    kind = PartitionRuleKind.COMPOSITE_PARTITION
    _ensure_commanded_finite(asset_id, kind, commanded)
    if constituent_count < 2:
        raise PseudoAxisEvaluationFailedError(
            asset_id=asset_id,
            kind=kind,
            reason=(
                f"CompositePartition requires constituent_count >= 2 (got {constituent_count})"
            ),
        )
    if rule.constituent_count != constituent_count:
        raise PseudoAxisEvaluationFailedError(
            asset_id=asset_id,
            kind=kind,
            reason=(
                f"CompositePartition rule.constituent_count={rule.constituent_count} "
                f"does not match Asset constituent_count={constituent_count}"
            ),
        )

    partition = rule.partition_kind

    if partition in (PartitionKind.PROPORTIONAL_FILL, PartitionKind.CONCENTRIC_SYMMETRIC):
        per = commanded / constituent_count
        _ensure_result_finite(asset_id, kind, per, f"CompositePartition {partition.value}")
        return tuple(per for _ in range(constituent_count))

    if partition is PartitionKind.FINE_CENTERED_KEEP:
        _ensure_result_finite(asset_id, kind, commanded, "CompositePartition FineCenteredKeep")
        values: list[float] = [0.0] * constituent_count
        values[-1] = commanded
        return tuple(values)

    if partition is PartitionKind.COARSE_FIRST_FILL:
        _ensure_result_finite(asset_id, kind, commanded, "CompositePartition CoarseFirstFill")
        values = [0.0] * constituent_count
        values[0] = commanded
        return tuple(values)

    raise PseudoAxisEvaluationFailedError(
        asset_id=asset_id,
        kind=kind,
        reason=f"unsupported PartitionKind {partition!r}",
    )


def eval_solver_reference(
    rule: SolverReference,
    commanded: float,
    *,
    asset_id: UUID,
) -> tuple[tuple[float, ...], float]:
    """Invoke a SolverReference rule's external solver.

    Returns `(constituent_setpoints, residual)`. The caller compares
    `residual` against `rule.singularity_threshold` and raises
    `PseudoAxisSingularityExceededError` on exceedance.

    The solver-transport bridge ships later. The signature is stable
    so callers can rely on the shape today; this implementation raises
    `NotImplementedError` until the bridge lands.
    """
    _ = _ensure_commanded_finite, asset_id, rule, commanded
    raise NotImplementedError(
        "SolverReference partition-rule evaluation is deferred; "
        "the solver transport bridge ships in a follow-up slice "
        f"(asset {asset_id!r}, transport {rule.solver_transport_kind.value!r}, "
        f"solver_id {rule.solver_id!r})"
    )


def check_solver_residual(
    rule: SolverReference,
    *,
    asset_id: UUID,
    residual: float,
) -> None:
    """Compare a solver-returned residual against the singularity threshold.

    Hoisted here so the solver-bridge follow-up can reuse the same
    guard the foundation layer already exposes. Raises
    `PseudoAxisSingularityExceededError` when `residual` exceeds the
    rule's `singularity_threshold`. Negative residuals are treated as
    their absolute value, mirroring the convention that residuals are
    magnitudes.
    """
    magnitude = abs(residual)
    if magnitude > rule.singularity_threshold:
        raise PseudoAxisSingularityExceededError(
            asset_id=asset_id,
            residual=magnitude,
            threshold=rule.singularity_threshold,
        )


__all__ = [
    "check_solver_residual",
    "eval_affine",
    "eval_affine_inverse",
    "eval_aggregation",
    "eval_composite_partition",
    "eval_lookup_table",
    "eval_solver_reference",
]
