"""Runtime evaluator that resolves a PseudoAxis virtual-axis command.

Loads the target Asset, verifies it is of Family PseudoAxis and carries
a partition rule, dispatches on the rule's kind, returns the resolved
constituent setpoints with timing + correlation evidence. The caller
(pre-Conductor expansion) is responsible for the constituent Surface
authz sweep and the sequential ControlPort dispatch loop; this module
is the math + load step only.

Pure function from `(event_store, asset_id, commanded_value,
constituent_asset_ids, correlation_id, calibration_revision,
pseudoaxis_family_ids)` to a `ResolvedSetpoints` record, modulo the
event-store I/O for the Asset load and the one structlog emission at
the end. No business-logic state survives across commands per the
non-determinism principle: the evaluator reloads the Asset on every
invocation.

`pseudoaxis_family_ids` is supplied by the caller so this module does
not have to spin up a Family-by-name lookup; the wiring layer
resolves the canonical PseudoAxis Family at startup and threads the
id set through. `calibration_revision` is supplied by the caller for
the LookupTable arm and may be None for every other rule kind;
LookupTable + None raises `InvalidPartitionRuleError(sub_code=
"calibration_revision_retracted")` per the memo lock.

See [[project-pseudoaxis-design]] v3 step 1 + step 2 + step 4.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cora.equipment.aggregates._partition_rule import (
    Affine,
    Aggregation,
    CompositePartition,
    LookupTable,
    PartitionRuleKind,
    SolverReference,
)
from cora.equipment.aggregates.asset.read import load_asset
from cora.equipment.aggregates.asset.state import AssetNotFoundError
from cora.infrastructure.logging import get_logger
from cora.operation._partition_rule_eval import (
    check_solver_residual,
    eval_affine,
    eval_aggregation,
    eval_composite_partition,
    eval_lookup_table,
    eval_solver_reference,
)
from cora.operation.errors import (
    AssetNotPseudoAxisError,
    PartitionRuleNotFoundError,
    PseudoAxisEvaluationFailedError,
)

if TYPE_CHECKING:
    from uuid import UUID

    from cora.infrastructure.ports import EventStore

_log = get_logger(__name__)
_RESOLVED_LOG_EVENT = "pseudoaxis.resolved"


@dataclass(frozen=True)
class ResolvedSetpoints:
    """Output of `resolve_pseudoaxis_command`.

    Captures the resolved constituent setpoints in the same order as
    `constituent_asset_ids` so the caller can zip the two tuples for
    sequential ControlPort dispatch. `evaluator_kind` is the rule
    kind that produced the result; surfaces in the structured log so
    operators can filter on rule kind. `evaluator_latency_ms` is the
    wall-clock time the evaluator spent inside the math (load +
    dispatch + result-construction); the soft SLA targets live in
    [[project-pseudoaxis-design]] v3 watch items. `residual` is
    populated only for `SolverReference`; the other rule kinds leave
    it at 0.0 (the residual is mathematically zero for closed-form
    rules). `correlation_id` is threaded into the downstream
    `controlport.dispatch` events via contextvars at the caller.
    """

    constituent_asset_ids: tuple[UUID, ...]
    constituent_values: tuple[float, ...]
    evaluator_kind: PartitionRuleKind
    evaluator_latency_ms: float
    residual: float
    correlation_id: UUID


async def resolve_pseudoaxis_command(
    *,
    event_store: EventStore,
    asset_id: UUID,
    commanded_value: float,
    constituent_asset_ids: tuple[UUID, ...],
    correlation_id: UUID,
    pseudoaxis_family_ids: frozenset[UUID],
    calibration_revision: object | None = None,
) -> ResolvedSetpoints:
    """Resolve a PseudoAxis virtual-axis command into constituent setpoints.

    Steps:

      1. Load the target Asset; raise `AssetNotFoundError` if the
         stream is empty.
      2. Verify the Asset's `family_ids` intersects the caller-supplied
         `pseudoaxis_family_ids`; raise `AssetNotPseudoAxisError`
         otherwise (routing bug from the caller's side).
      3. Verify `state.partition_rule is not None`; raise
         `PartitionRuleNotFoundError` otherwise (PseudoAxis Asset
         exists but the operating math has not been set).
      4. Dispatch on `type(state.partition_rule)` into the matching
         pure evaluator in `_partition_rule_eval`. For `LookupTable`,
         pass `calibration_revision` through; for `SolverReference`,
         apply the singularity-threshold guard via
         `check_solver_residual`.
      5. Emit one `pseudoaxis.resolved` structured-log event with the
         rule kind, the resolved setpoints, the latency, the
         correlation id, and the residual.
      6. Return a `ResolvedSetpoints` record.

    `constituent_asset_ids` is supplied by the caller (loaded from
    the rule + Asset wiring at command-acceptance time) so this
    evaluator does not have to reach into the wiring substrate. The
    caller is also responsible for the cross-Surface authz pre-check
    and the ControlPort dispatch loop.
    """
    started = time.perf_counter()

    asset = await load_asset(event_store, asset_id)
    if asset is None:
        raise AssetNotFoundError(asset_id)

    if asset.family_ids.isdisjoint(pseudoaxis_family_ids):
        raise AssetNotPseudoAxisError(asset_id)

    rule = asset.partition_rule
    if rule is None:
        raise PartitionRuleNotFoundError(asset_id)

    kind: PartitionRuleKind
    constituent_values: tuple[float, ...]
    residual: float = 0.0

    match rule:
        case Affine():
            kind = PartitionRuleKind.AFFINE
            if len(constituent_asset_ids) != 1:
                raise PseudoAxisEvaluationFailedError(
                    asset_id=asset_id,
                    kind=kind,
                    reason=(
                        f"Affine partition rule expects exactly 1 constituent "
                        f"(got {len(constituent_asset_ids)})"
                    ),
                )
            forward = eval_affine(rule, commanded_value, asset_id=asset_id)
            constituent_values = (forward,)
        case Aggregation():
            kind = PartitionRuleKind.AGGREGATION
            if len(constituent_asset_ids) != rule.constituent_count:
                raise PseudoAxisEvaluationFailedError(
                    asset_id=asset_id,
                    kind=kind,
                    reason=(
                        f"Aggregation partition rule expects "
                        f"{rule.constituent_count} constituents "
                        f"(got {len(constituent_asset_ids)})"
                    ),
                )
            constituent_values = eval_aggregation(rule, commanded_value, asset_id=asset_id)
        case LookupTable():
            kind = PartitionRuleKind.LOOKUP_TABLE
            if len(constituent_asset_ids) != 1:
                raise PseudoAxisEvaluationFailedError(
                    asset_id=asset_id,
                    kind=kind,
                    reason=(
                        f"LookupTable partition rule expects exactly 1 constituent "
                        f"(got {len(constituent_asset_ids)})"
                    ),
                )
            forward = eval_lookup_table(
                rule,
                commanded_value,
                asset_id=asset_id,
                calibration_revision=calibration_revision,
            )
            constituent_values = (forward,)
        case CompositePartition():
            kind = PartitionRuleKind.COMPOSITE_PARTITION
            constituent_values = eval_composite_partition(
                rule,
                commanded_value,
                asset_id=asset_id,
                constituent_count=len(constituent_asset_ids),
            )
        case SolverReference():
            kind = PartitionRuleKind.SOLVER_REFERENCE
            constituent_values, residual = eval_solver_reference(
                rule, commanded_value, asset_id=asset_id
            )
            check_solver_residual(rule, asset_id=asset_id, residual=residual)

    elapsed_ms = (time.perf_counter() - started) * 1000.0

    _log.info(
        _RESOLVED_LOG_EVENT,
        asset_id=str(asset_id),
        commanded_value=commanded_value,
        partition_rule_kind=kind.value,
        resolved_setpoints=list(constituent_values),
        evaluator_latency_ms=elapsed_ms,
        status="ok",
        correlation_id=str(correlation_id),
        residual=residual,
    )

    return ResolvedSetpoints(
        constituent_asset_ids=constituent_asset_ids,
        constituent_values=constituent_values,
        evaluator_kind=kind,
        evaluator_latency_ms=elapsed_ms,
        residual=residual,
        correlation_id=correlation_id,
    )


__all__ = [
    "ResolvedSetpoints",
    "resolve_pseudoaxis_command",
]
