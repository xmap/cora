"""PartitionRule value object: a typed rule that decomposes a virtual-axis
command into setpoints on N constituent motor axes.

A `PartitionRule` is the math attached to a `PseudoAxis` Asset. Operators
command the virtual output port; the runtime evaluator (in the Operation
module) reads this rule and writes the resolved setpoints to the
constituent motors via ControlPort.

`expected_constituent_count` exposes the declared arity per rule shape;
it is the single source of truth shared by the runtime evaluator (Operation
BC) and the Plan-bind fan-out validator (Recipe BC).

Closed discriminated union of 5 frozen-dataclass shapes, all carrying a
`kind: PartitionRuleKind` discriminator:

- `Affine`: `dependent = gain * independent + offset`. Single-input,
  single-output. The general affine map covers pure offset (gain=1) and
  pure scale (offset=0). Used for laminography pitch tracking in the
  linear approximation, mirror lever-arm couplings, calibration-derived
  linear corrections.
- `Aggregation`: `virtual = aggregator(constituent_1, ..., constituent_N)`
  where `aggregator` is a closed StrEnum of deterministic aggregators
  (Sum, Difference, MidRange, Product). One-way and total: virtual is
  computed from constituents with a unique inverse. Used for slit
  center/gap arithmetic, KB mirror lever-arm sync.
- `LookupTable`: `dependent = interpolate(independent, calibration_revision_id)`
  with closed interpolation + extrapolation policy. Used for undulator
  gap, lens turret to focus_Z, attenuator transmission, scintillator
  efficiency, thermal drift tables. Calibration revision is pinned by
  id for reproducibility; retraction aborts evaluation.
- `CompositePartition`: `virtual = sum(constituents)` with a partition rule
  that decides how the operator-commanded virtual value is split among
  N constituents. Used for sample-stack Y compensation (hexapod_Y +
  table_Y with "hexapod stays near 0" rule).
- `SolverReference`: `dependent = vendor_solver(independent)` where the
  solver is identified by id and transport. The escape valve for
  irreducibly nonlinear cases (hexapod 6-DoF, six-circle HKL) where the
  controller already implements the math.

The catalog grows by PR (the Affordance / CalibrationQuantity precedent).
This module is the single source of truth for the shape; deciders read
it, routes parse JSON into it (via Pydantic at the route layer), events
serialize it via `partition_rule_to_payload` / `partition_rule_from_payload`.

`PartitionRule` is a frozen-dataclass union per the existing CORA
typed-VO pattern (Drawing precedent at `_drawing.py`). Pydantic exists
only at the route boundary. See [[project-pseudoaxis-design]] v3 for the
design lock and rationale.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal
from uuid import UUID

PARTITION_RULE_SOLVER_ID_MAX_LENGTH = 200
PARTITION_RULE_SOLVER_VERSION_MAX_LENGTH = 100
PARTITION_RULE_UNIT_MAX_LENGTH = 50
PARTITION_RULE_VIRTUAL_PORT_NAME_MAX_LENGTH = 200


class InvalidPartitionRuleError(ValueError):
    """Base class for PartitionRule shape-validation failures.

    Subclasses carry the specific sub-code so the route layer can
    surface a structured error body. The base catches everything at
    the BC's exception-handler layer.
    """

    def __init__(self, sub_code: str, reason: str) -> None:
        super().__init__(f"Invalid PartitionRule [{sub_code}]: {reason}")
        self.sub_code = sub_code
        self.reason = reason


class PartitionRuleKind(StrEnum):
    """Discriminator for the 5 partition-rule shapes.

    Closed catalog: extending requires a paired PR that ships the new
    dataclass shape, the dict-to-VO and VO-to-dict dispatch arms, the
    runtime evaluator (in Operation), and the projection CHECK
    constraint update.
    """

    AFFINE = "Affine"
    AGGREGATION = "Aggregation"
    LOOKUP_TABLE = "LookupTable"
    COMPOSITE_PARTITION = "CompositePartition"
    SOLVER_REFERENCE = "SolverReference"


class AggregatorKind(StrEnum):
    """How an Aggregation shape combines N constituent values into one.

    Sum: `v = sum(c_i)`. Difference (2-constituent only): `v = c_1 - c_0`.
    MidRange (2-constituent only): `v = (c_0 + c_1) / 2`. Product:
    `v = prod(c_i)`.
    """

    SUM = "Sum"
    DIFFERENCE = "Difference"
    MID_RANGE = "MidRange"
    PRODUCT = "Product"


class PartitionKind(StrEnum):
    """How a CompositePartition shape splits an operator-commanded
    virtual value across N constituents.

    CoarseFirstFill: fill from the coarsest constituent first; remaining
    constituents stay near their default. FineCenteredKeep: keep the
    finest constituent near its center of travel; let the other
    constituents pick up coarse offset (the 2-BM sample-stack rule).
    ProportionalFill: split proportionally to each constituent's travel
    range. ConcentricSymmetric: symmetric expansion around a center
    (used for concentric pinhole + iris compositions).
    """

    COARSE_FIRST_FILL = "CoarseFirstFill"
    FINE_CENTERED_KEEP = "FineCenteredKeep"
    PROPORTIONAL_FILL = "ProportionalFill"
    CONCENTRIC_SYMMETRIC = "ConcentricSymmetric"


class InterpolationKind(StrEnum):
    """How a LookupTable interpolates between tabulated points."""

    LINEAR = "Linear"
    CUBIC = "Cubic"
    NEAREST = "Nearest"


class ExtrapolationKind(StrEnum):
    """How a LookupTable handles inputs outside its tabulated range.

    Clamp: returns the value at the nearest endpoint. Error: raises
    PseudoAxisEvaluationFailedError at runtime.
    """

    CLAMP = "Clamp"
    ERROR = "Error"


class SolverTransportKind(StrEnum):
    """How a SolverReference reaches its external solver.

    SoftIOCRecord: the solver is an EPICS soft-IOC record; the
    invocation writes setpoints to a calc record and reads results.
    PythonCallable: the solver is a registered Python callable in the
    facility's solver registry. ControllerAPI: the solver lives in a
    hardware controller exposed via a vendor API. ExternalHTTPService:
    the solver is a long-running HTTP service registered at facility
    setup.
    """

    SOFT_IOC_RECORD = "SoftIOCRecord"
    PYTHON_CALLABLE = "PythonCallable"
    CONTROLLER_API = "ControllerAPI"
    EXTERNAL_HTTP_SERVICE = "ExternalHTTPService"


class ReadbackAggregatorKind(StrEnum):
    """How a PartitionRule reconstructs the virtual-axis readback value
    from constituent readbacks when forward-inverse symmetry is not
    available (LookupTable non-monotonic, SolverReference declared
    non-invertible).

    Identity: returns the single constituent's readback (only valid
    when there is exactly one constituent). Sum: returns the sum of
    constituent readbacks. Mean: returns the arithmetic mean. SelectIndex0:
    returns the first constituent's readback (operator decides the
    canonical choice when the math admits no clean inverse).
    """

    IDENTITY = "Identity"
    SUM = "Sum"
    MEAN = "Mean"
    SELECT_INDEX_0 = "SelectIndex0"


def _check_finite(value: float, field_name: str, kind: PartitionRuleKind) -> None:
    """Reject NaN and infinite values in numeric fields.

    NaN propagates silently through arithmetic, which is the opposite
    of what an audited evaluator needs. Infinite values usually mean
    a divide-by-zero upstream that we want to surface, not propagate.
    """
    if not math.isfinite(value):
        raise InvalidPartitionRuleError(
            sub_code="numeric_not_finite",
            reason=(
                f"{kind.value}.{field_name} must be a finite number "
                f"(got {value!r}); NaN and Inf are rejected"
            ),
        )


@dataclass(frozen=True)
class Affine:
    """Affine partition: `dependent = gain * independent + offset`.

    Single-input, single-output. The general affine map covers pure
    offset (gain=1) and pure scale (offset=0). Always invertible.

    `unit_in` / `unit_out` are operator-supplied short strings that
    document the dimensional contract (for example "mm" / "deg").
    They are NOT semantic units in the measurement-units sense; that
    typing lives on the AssetPort signal_type. These strings carry
    operator intent and surface in audit logs.
    """

    kind: Literal[PartitionRuleKind.AFFINE] = field(default=PartitionRuleKind.AFFINE, init=False)
    gain: float = 1.0
    offset: float = 0.0
    unit_in: str = ""
    unit_out: str = ""

    def __post_init__(self) -> None:
        _check_finite(self.gain, "gain", PartitionRuleKind.AFFINE)
        _check_finite(self.offset, "offset", PartitionRuleKind.AFFINE)


@dataclass(frozen=True)
class Aggregation:
    """Aggregation partition: `virtual = aggregator(constituents)`.

    `aggregator_kind` selects a closed deterministic aggregation. The
    `constituent_count` field documents how many constituents the
    aggregator expects; the runtime evaluator cross-checks against the
    Asset's declared constituent_asset_ids count at evaluate time and
    raises if there is a mismatch.

    Difference and MidRange require constituent_count == 2; Sum and
    Product require constituent_count >= 1. Validated at construction.
    """

    kind: Literal[PartitionRuleKind.AGGREGATION] = field(
        default=PartitionRuleKind.AGGREGATION, init=False
    )
    aggregator_kind: AggregatorKind = AggregatorKind.SUM
    constituent_count: int = 1

    def __post_init__(self) -> None:
        if self.constituent_count < 1:
            raise InvalidPartitionRuleError(
                sub_code="constituent_count_below_minimum",
                reason=(
                    f"Aggregation.constituent_count must be >= 1, got {self.constituent_count}"
                ),
            )
        if (
            self.aggregator_kind in (AggregatorKind.DIFFERENCE, AggregatorKind.MID_RANGE)
            and self.constituent_count != 2
        ):
            raise InvalidPartitionRuleError(
                sub_code="aggregator_constituent_count_mismatch",
                reason=(
                    f"Aggregation.aggregator_kind={self.aggregator_kind.value} requires "
                    f"constituent_count == 2 (got {self.constituent_count})"
                ),
            )


@dataclass(frozen=True)
class LookupTable:
    """LookupTable partition: `dependent = interpolate(independent, table)`.

    The table itself is referenced by Calibration revision id (not
    inlined) so the calibration history audit remains the source of
    truth and the partition rule survives recalibration via explicit
    revision update. Pinning is intentional: a Method that fixed its
    pixel scale at revision R reproduces against revision R even if a
    later revision changed the calibration.

    `invertible=True` requires the underlying table to be monotonic
    along its independent axis (validated at the slice decider when
    the rule is set, by loading the calibration revision). If
    monotonic-check at decide time fails, the slice rejects.

    If `invertible=False`, `readback_aggregator_kind` must be supplied
    so the virtual-axis readback can be reconstructed from constituent
    readbacks.
    """

    kind: Literal[PartitionRuleKind.LOOKUP_TABLE] = field(
        default=PartitionRuleKind.LOOKUP_TABLE, init=False
    )
    calibration_revision_id: UUID = field(default_factory=lambda: UUID(int=0))
    interpolation_kind: InterpolationKind = InterpolationKind.LINEAR
    extrapolation_kind: ExtrapolationKind = ExtrapolationKind.CLAMP
    invertible: bool = True
    readback_aggregator_kind: ReadbackAggregatorKind | None = None
    unit_in: str = ""
    unit_out: str = ""

    def __post_init__(self) -> None:
        if self.calibration_revision_id == UUID(int=0):
            raise InvalidPartitionRuleError(
                sub_code="calibration_revision_id_missing",
                reason="LookupTable.calibration_revision_id is required",
            )
        if not self.invertible and self.readback_aggregator_kind is None:
            raise InvalidPartitionRuleError(
                sub_code="readback_aggregator_required",
                reason=("LookupTable.readback_aggregator_kind is required when invertible=False"),
            )


@dataclass(frozen=True)
class CompositePartition:
    """CompositePartition: virtual axis = sum of N constituents with a
    partition rule that decides how the operator-commanded value is
    split among them.

    `partition_kind` is the operating-discipline closed enum. The
    runtime evaluator looks up each partition-kind's resolver function
    and applies it to the (commanded_value, constituent_count,
    partition_parameters) triple to produce N setpoints.

    `partition_parameters` is a closed-schema dict whose keys depend on
    partition_kind. The runtime evaluator validates the keys against
    the partition_kind's expected schema and raises
    PseudoAxisEvaluationFailedError on mismatch. Future versions may
    promote this to a per-partition-kind typed VO; for v1 the dict
    shape is sufficient because the parameter sets are small (typically
    1-3 keys per partition kind) and operator-facing.

    Always invertible: the virtual readback aggregates constituent
    readbacks per `readback_aggregator_kind` (default `Sum` since the
    composition is a sum).
    """

    kind: Literal[PartitionRuleKind.COMPOSITE_PARTITION] = field(
        default=PartitionRuleKind.COMPOSITE_PARTITION, init=False
    )
    partition_kind: PartitionKind = PartitionKind.PROPORTIONAL_FILL
    constituent_count: int = 2
    partition_parameters: tuple[tuple[str, float], ...] = ()
    readback_aggregator_kind: ReadbackAggregatorKind = ReadbackAggregatorKind.SUM

    def __post_init__(self) -> None:
        if self.constituent_count < 2:
            raise InvalidPartitionRuleError(
                sub_code="composite_constituent_count_below_minimum",
                reason=(
                    "CompositePartition.constituent_count must be >= 2 "
                    f"(got {self.constituent_count}); use Affine for the 1-to-1 case"
                ),
            )
        for key, value in self.partition_parameters:
            _check_finite(
                value, f"partition_parameters[{key!r}]", PartitionRuleKind.COMPOSITE_PARTITION
            )


@dataclass(frozen=True)
class SolverReference:
    """SolverReference partition: an external solver owns the math.

    Used for irreducibly nonlinear cases (hexapod 6-DoF parallel
    kinematics, six-circle HKL inverse kinematics, DCM Bragg gap
    tracking) where the vendor controller already implements the
    forward and inverse. CORA names the solver by id, captures the
    invocation in the audit trail via observability, and verifies the
    returned residual against `singularity_threshold`.

    `solver_id` is the canonical id within the facility's solver
    registry. `solver_version` is the version of the solver
    implementation that the rule was authored against (changes in
    the solver itself should bump this and trigger a rule update).
    `solver_transport_kind` declares how the evaluator reaches the
    solver. `residual_tolerance_limit` is the maximum acceptable
    post-solve residual; below this, the result is accepted.
    `singularity_threshold` is a multiplier on residual_tolerance_limit
    above which the solver's result is treated as singular and rejected
    with PseudoAxisSingularityExceededError.

    `invertible` is declared explicitly because some solvers are
    forward-only (vendor APIs that compute leg lengths from a Cartesian
    pose but provide no inverse). When `invertible=False`,
    `readback_aggregator_kind` is required.
    """

    kind: Literal[PartitionRuleKind.SOLVER_REFERENCE] = field(
        default=PartitionRuleKind.SOLVER_REFERENCE, init=False
    )
    solver_id: str = ""
    solver_version: str = ""
    solver_transport_kind: SolverTransportKind = SolverTransportKind.SOFT_IOC_RECORD
    residual_tolerance_limit: float = 0.0
    singularity_threshold: float = 0.0
    invertible: bool = True
    readback_aggregator_kind: ReadbackAggregatorKind | None = None

    def __post_init__(self) -> None:
        if not self.solver_id:
            raise InvalidPartitionRuleError(
                sub_code="solver_id_missing",
                reason="SolverReference.solver_id is required",
            )
        if len(self.solver_id) > PARTITION_RULE_SOLVER_ID_MAX_LENGTH:
            raise InvalidPartitionRuleError(
                sub_code="solver_id_too_long",
                reason=(
                    f"SolverReference.solver_id length {len(self.solver_id)} exceeds "
                    f"{PARTITION_RULE_SOLVER_ID_MAX_LENGTH}"
                ),
            )
        if not self.solver_version:
            raise InvalidPartitionRuleError(
                sub_code="solver_version_missing",
                reason="SolverReference.solver_version is required",
            )
        if len(self.solver_version) > PARTITION_RULE_SOLVER_VERSION_MAX_LENGTH:
            raise InvalidPartitionRuleError(
                sub_code="solver_version_too_long",
                reason=(
                    f"SolverReference.solver_version length {len(self.solver_version)} "
                    f"exceeds {PARTITION_RULE_SOLVER_VERSION_MAX_LENGTH}"
                ),
            )
        _check_finite(
            self.residual_tolerance_limit,
            "residual_tolerance_limit",
            PartitionRuleKind.SOLVER_REFERENCE,
        )
        _check_finite(
            self.singularity_threshold, "singularity_threshold", PartitionRuleKind.SOLVER_REFERENCE
        )
        if self.residual_tolerance_limit < 0:
            raise InvalidPartitionRuleError(
                sub_code="residual_tolerance_negative",
                reason=(
                    f"SolverReference.residual_tolerance_limit must be >= 0 "
                    f"(got {self.residual_tolerance_limit})"
                ),
            )
        if self.singularity_threshold < self.residual_tolerance_limit:
            raise InvalidPartitionRuleError(
                sub_code="singularity_threshold_below_residual",
                reason=(
                    f"SolverReference.singularity_threshold ({self.singularity_threshold}) "
                    f"must be >= residual_tolerance_limit ({self.residual_tolerance_limit})"
                ),
            )
        if not self.invertible and self.readback_aggregator_kind is None:
            raise InvalidPartitionRuleError(
                sub_code="readback_aggregator_required",
                reason=(
                    "SolverReference.readback_aggregator_kind is required when invertible=False"
                ),
            )


type PartitionRule = Affine | Aggregation | LookupTable | CompositePartition | SolverReference


def partition_rule_to_payload(rule: PartitionRule) -> dict[str, object]:
    """Serialize a PartitionRule VO to a JSON-friendly dict for jsonb
    storage on the AssetPartitionRuleUpdated event payload.

    Output shape always carries the `kind` discriminator at the top
    level; the remaining keys are the kind-specific fields. Round-trips
    with `partition_rule_from_payload` (re-runs `__post_init__`
    validators on rebuild).

    The match-arm dispatch keeps the dispatcher visible at the call
    site so reviewers see when a new kind is added. This is deliberate
    per the closed-catalog discipline.
    """
    match rule:
        case Affine(gain=gain, offset=offset, unit_in=unit_in, unit_out=unit_out):
            return {
                "kind": PartitionRuleKind.AFFINE.value,
                "gain": gain,
                "offset": offset,
                "unit_in": unit_in,
                "unit_out": unit_out,
            }
        case Aggregation(aggregator_kind=aggregator_kind, constituent_count=constituent_count):
            return {
                "kind": PartitionRuleKind.AGGREGATION.value,
                "aggregator_kind": aggregator_kind.value,
                "constituent_count": constituent_count,
            }
        case LookupTable(
            calibration_revision_id=calibration_revision_id,
            interpolation_kind=interpolation_kind,
            extrapolation_kind=extrapolation_kind,
            invertible=invertible,
            readback_aggregator_kind=readback_aggregator_kind,
            unit_in=unit_in,
            unit_out=unit_out,
        ):
            return {
                "kind": PartitionRuleKind.LOOKUP_TABLE.value,
                "calibration_revision_id": str(calibration_revision_id),
                "interpolation_kind": interpolation_kind.value,
                "extrapolation_kind": extrapolation_kind.value,
                "invertible": invertible,
                "readback_aggregator_kind": (
                    readback_aggregator_kind.value if readback_aggregator_kind is not None else None
                ),
                "unit_in": unit_in,
                "unit_out": unit_out,
            }
        case CompositePartition(
            partition_kind=partition_kind,
            constituent_count=constituent_count,
            partition_parameters=partition_parameters,
            readback_aggregator_kind=readback_aggregator_kind,
        ):
            return {
                "kind": PartitionRuleKind.COMPOSITE_PARTITION.value,
                "partition_kind": partition_kind.value,
                "constituent_count": constituent_count,
                "partition_parameters": sorted(
                    [list(pair) for pair in partition_parameters], key=lambda kv: str(kv[0])
                ),
                "readback_aggregator_kind": readback_aggregator_kind.value,
            }
        case SolverReference(
            solver_id=solver_id,
            solver_version=solver_version,
            solver_transport_kind=solver_transport_kind,
            residual_tolerance_limit=residual_tolerance_limit,
            singularity_threshold=singularity_threshold,
            invertible=invertible,
            readback_aggregator_kind=readback_aggregator_kind,
        ):
            return {
                "kind": PartitionRuleKind.SOLVER_REFERENCE.value,
                "solver_id": solver_id,
                "solver_version": solver_version,
                "solver_transport_kind": solver_transport_kind.value,
                "residual_tolerance_limit": residual_tolerance_limit,
                "singularity_threshold": singularity_threshold,
                "invertible": invertible,
                "readback_aggregator_kind": (
                    readback_aggregator_kind.value if readback_aggregator_kind is not None else None
                ),
            }


def partition_rule_from_payload(payload: dict[str, object]) -> PartitionRule:
    """Reconstruct a PartitionRule VO from its JSON payload.

    Dispatches on payload['kind']. Re-runs each shape's `__post_init__`
    validators so a malformed event payload fails loud rather than
    folding into invalid state. Round-trips losslessly with
    `partition_rule_to_payload`.

    Raises `InvalidPartitionRuleError(sub_code='kind_unknown')` if the
    discriminator is missing or not a known PartitionRuleKind value.
    """
    raw_kind = payload.get("kind")
    if raw_kind is None:
        raise InvalidPartitionRuleError(
            sub_code="kind_missing",
            reason="PartitionRule payload is missing the 'kind' discriminator",
        )
    try:
        kind = PartitionRuleKind(str(raw_kind))
    except ValueError as exc:
        raise InvalidPartitionRuleError(
            sub_code="kind_unknown",
            reason=f"PartitionRule kind {raw_kind!r} is not a known PartitionRuleKind value",
        ) from exc
    match kind:
        case PartitionRuleKind.AFFINE:
            return Affine(
                gain=float(payload.get("gain", 1.0)),  # type: ignore[arg-type]
                offset=float(payload.get("offset", 0.0)),  # type: ignore[arg-type]
                unit_in=str(payload.get("unit_in", "")),
                unit_out=str(payload.get("unit_out", "")),
            )
        case PartitionRuleKind.AGGREGATION:
            return Aggregation(
                aggregator_kind=AggregatorKind(str(payload.get("aggregator_kind", "Sum"))),
                constituent_count=int(payload.get("constituent_count", 1)),  # type: ignore[arg-type]
            )
        case PartitionRuleKind.LOOKUP_TABLE:
            readback_raw = payload.get("readback_aggregator_kind")
            # Tolerate missing calibration_revision_id by defaulting to
            # the sentinel UUID(int=0); __post_init__ then raises
            # InvalidPartitionRuleError(sub_code="calibration_revision_id_missing"),
            # which is the same error the operator sees if they explicitly
            # pass the sentinel. Consistent error surface for both cases.
            raw_cal_id = payload.get("calibration_revision_id")
            return LookupTable(
                calibration_revision_id=(
                    UUID(str(raw_cal_id)) if raw_cal_id is not None else UUID(int=0)
                ),
                interpolation_kind=InterpolationKind(
                    str(payload.get("interpolation_kind", "Linear"))
                ),
                extrapolation_kind=ExtrapolationKind(
                    str(payload.get("extrapolation_kind", "Clamp"))
                ),
                invertible=bool(payload.get("invertible", True)),
                readback_aggregator_kind=(
                    ReadbackAggregatorKind(str(readback_raw)) if readback_raw is not None else None
                ),
                unit_in=str(payload.get("unit_in", "")),
                unit_out=str(payload.get("unit_out", "")),
            )
        case PartitionRuleKind.COMPOSITE_PARTITION:
            raw_params: list[list[str | float]] = (
                payload.get("partition_parameters") or []  # type: ignore[assignment]
            )
            params: tuple[tuple[str, float], ...] = tuple(
                (str(pair[0]), float(pair[1])) for pair in raw_params
            )
            return CompositePartition(
                partition_kind=PartitionKind(
                    str(payload.get("partition_kind", "ProportionalFill"))
                ),
                constituent_count=int(payload.get("constituent_count", 2)),  # type: ignore[arg-type]
                partition_parameters=params,
                readback_aggregator_kind=ReadbackAggregatorKind(
                    str(payload.get("readback_aggregator_kind", "Sum"))
                ),
            )
        case PartitionRuleKind.SOLVER_REFERENCE:
            readback_raw = payload.get("readback_aggregator_kind")
            return SolverReference(
                solver_id=str(payload.get("solver_id", "")),
                solver_version=str(payload.get("solver_version", "")),
                solver_transport_kind=SolverTransportKind(
                    str(payload.get("solver_transport_kind", "SoftIOCRecord"))
                ),
                residual_tolerance_limit=float(payload.get("residual_tolerance_limit", 0.0)),  # type: ignore[arg-type]
                singularity_threshold=float(payload.get("singularity_threshold", 0.0)),  # type: ignore[arg-type]
                invertible=bool(payload.get("invertible", True)),
                readback_aggregator_kind=(
                    ReadbackAggregatorKind(str(readback_raw)) if readback_raw is not None else None
                ),
            )


def expected_constituent_count(rule: PartitionRule) -> int | None:
    """Return the constituent-input arity declared by `rule`, or None.

    Centralizes the per-shape arity rule so the Operation-tier runtime
    evaluator and the Recipe-tier Plan-bind fan-out validator agree on
    the contract:

      - `Affine`: 1 (single-input, single-output).
      - `Aggregation`: `rule.constituent_count` (operator-declared on
        the rule; `__post_init__` already guards aggregator-specific
        minima such as Difference / MidRange = 2).
      - `LookupTable`: 1 (single independent variable per table).
      - `CompositePartition`: `rule.constituent_count`.
      - `SolverReference`: None. The arity is not declared on the rule
        (the external solver owns its own kinematics signature);
        callers MUST treat None as "skip the arity check" rather than
        substituting a default.

    Pure helper. No I/O, no side effects.
    """
    match rule:
        case Affine():
            return 1
        case Aggregation(constituent_count=count):
            return count
        case LookupTable():
            return 1
        case CompositePartition(constituent_count=count):
            return count
        case SolverReference():
            return None


__all__ = [
    "PARTITION_RULE_SOLVER_ID_MAX_LENGTH",
    "PARTITION_RULE_SOLVER_VERSION_MAX_LENGTH",
    "PARTITION_RULE_UNIT_MAX_LENGTH",
    "PARTITION_RULE_VIRTUAL_PORT_NAME_MAX_LENGTH",
    "Affine",
    "Aggregation",
    "AggregatorKind",
    "CompositePartition",
    "ExtrapolationKind",
    "InterpolationKind",
    "InvalidPartitionRuleError",
    "LookupTable",
    "PartitionKind",
    "PartitionRule",
    "PartitionRuleKind",
    "ReadbackAggregatorKind",
    "SolverReference",
    "SolverTransportKind",
    "expected_constituent_count",
    "partition_rule_from_payload",
    "partition_rule_to_payload",
]
