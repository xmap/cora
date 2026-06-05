"""Pure decider for the `AddPlanWire` command.

Validation cascade (fail-fast, in order):

  1. Plan stream must have prior events -> `PlanNotFoundError` if state is None
  2. Construct the proposed `Wire` (raises `InvalidWireError` on bad
     port name lengths)
  3. Strict-not-idempotent: if the proposed wire is already in
     `state.wires`, raise `PlanWireAlreadyExistsError`. Mirrors 5h
     `add_asset_port`.
  4. Fan-in check: if any existing wire in `state.wires` already
     targets the same `(target_asset_id, target_port_name)` pair,
     raise `PlanWireTargetAlreadyConnectedError`. Done here (not in
     the structural validator) because it requires the current wire
     SET, which the handler doesn't have to load separately.
  5. Structural validation via `validate_wire_endpoints`:
     self-loop guard, asset-binding check, port-existence check,
     direction check, signal_type compatibility.
  6. PseudoAxis fan-out validation (only when the target Asset is a
     PseudoAxis Family member): output cardinality, partition-rule
     arity, signal-type homogeneity across the FULL set of incoming
     wires (existing wires targeting the same Asset + the proposed
     wire). See `validate_pseudoaxis_fanout` for the contract.

Lifecycle independence: wiring is allowed in any Plan lifecycle
state (Defined, Versioned, Deprecated), same precedent as
`update_plan_default_parameters` (6g-b). Operators can adjust
wiring on a Versioned Plan without re-versioning. Deprecated Plans
also accept wire mutations (advisory deprecation; the lifecycle
gate is at Run-start, not Plan-mutation).

PseudoAxis-membership detection: the handler resolves PseudoAxis
Family membership by loading each Family in the target Asset's
`family_ids` and matching on `name == "PseudoAxis"` (mirrors the
`update_asset_partition_rule` slice handler). The resolved family
ids are passed to the decider via the `pseudoaxis_family_ids`
keyword so the decider can stay pure (no I/O, no Family loading)
and tests can bypass the by-name lookup by supplying the set
directly (mirrors the Slice 2 `InMemoryRecipeExpansionPort` shape).

See [[project_plan_wiring_design]] and [[project_pseudoaxis_design]]
for the locked design memos.
"""

from datetime import datetime
from uuid import UUID

from cora.recipe.aggregates.plan import (
    Plan,
    PlanNotFoundError,
    PlanWireAdded,
    PlanWireAlreadyExistsError,
    PlanWireTargetAlreadyConnectedError,
    Wire,
    validate_pseudoaxis_fanout,
    validate_wire_endpoints,
)
from cora.recipe.features.add_plan_wire.command import AddPlanWire
from cora.recipe.features.add_plan_wire.context import PlanWireContext


def decide(
    state: Plan | None,
    command: AddPlanWire,
    *,
    context: PlanWireContext,
    now: datetime,
    pseudoaxis_family_ids: frozenset[UUID] = frozenset(),
) -> list[PlanWireAdded]:
    """Decide the events produced by adding a Wire to an existing Plan.

    Invariants:
      - State must not be None -> PlanNotFoundError
      - Wire structural shape must be valid -> InvalidWireError
        (via Wire VO)
      - Wire must not already be in state.wires
        (strict-not-idempotent) -> PlanWireAlreadyExistsError
      - (target_asset_id, target_port_name) must not already be
        connected (fan-in forbidden)
        -> PlanWireTargetAlreadyConnectedError
      - Endpoints must satisfy asset-binding, port existence,
        direction, and signal_type compatibility (no self-loop)
        -> InvalidWireError / wire-endpoint errors
        (via validate_wire_endpoints)
      - When the target Asset is in `pseudoaxis_family_ids` the fan-out
        invariants hold for the SET of wires that will target the Asset
        after the add:
          - exactly one OUTPUT port declared on the Asset
            -> PlanPseudoAxisOutputCardinalityError
          - wire count matches the partition rule's declared arity
            (SolverReference exempt)
            -> PlanPseudoAxisArityMismatchError
          - all source-side signal_types match
            -> PlanPseudoAxisFanoutSignalTypeMismatchError

    `pseudoaxis_family_ids` defaults to the empty set so callers that
    have no PseudoAxis Assets in play skip the fan-out check entirely.
    The handler computes the set via Family name lookup; tests supply
    it directly to keep the decider testable without I/O.
    """
    if state is None:
        raise PlanNotFoundError(command.plan_id)

    # Construct the Wire VO (validates structural shape: port name
    # lengths, raises InvalidWireError to 400 at the route layer).
    proposed = Wire(
        source_asset_id=command.source_asset_id,
        source_port_name=command.source_port_name,
        target_asset_id=command.target_asset_id,
        target_port_name=command.target_port_name,
    )

    # Strict-not-idempotent: re-add raises (mirrors 5h add_asset_port).
    if proposed in state.wires:
        raise PlanWireAlreadyExistsError(proposed)

    # Fan-in check: at most one Wire per (target_asset_id, target_port_name).
    for existing in state.wires:
        if (
            existing.target_asset_id == proposed.target_asset_id
            and existing.target_port_name == proposed.target_port_name
        ):
            raise PlanWireTargetAlreadyConnectedError(proposed, existing)

    # Cross-aggregate structural validation (asset-binding + port-existence
    # + direction + signal_type + self-loop guard).
    validate_wire_endpoints(
        proposed,
        bound_asset_ids=state.asset_ids,
        assets_by_id=context.assets,
    )

    # PseudoAxis fan-out validation. The target Asset is in
    # context.assets after validate_wire_endpoints passes (the
    # port-existence branch keys against assets_by_id). Family
    # membership is supplied by the handler; if the target Asset is
    # not a PseudoAxis member this branch no-ops.
    target_asset = context.assets[proposed.target_asset_id]
    if pseudoaxis_family_ids and (target_asset.family_ids & pseudoaxis_family_ids):
        incoming_wires = frozenset(
            {w for w in state.wires if w.target_asset_id == proposed.target_asset_id} | {proposed}
        )
        validate_pseudoaxis_fanout(
            pseudoaxis_asset=target_asset,
            partition_rule=target_asset.partition_rule,
            incoming_wires=incoming_wires,
            assets_by_id=context.assets,
        )

    return [
        PlanWireAdded(
            plan_id=state.id,
            source_asset_id=proposed.source_asset_id,
            source_port_name=proposed.source_port_name,
            target_asset_id=proposed.target_asset_id,
            target_port_name=proposed.target_port_name,
            occurred_at=now,
        )
    ]
