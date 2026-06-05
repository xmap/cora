"""Validate a `Wire` against the Plan's bound Assets and their ports.

This is a structural / relational validator, NOT an instance of the
schema-validated-values pattern (no JSON Schema involved). The
checks live here:

  - both endpoint asset_ids are in the Plan's `asset_ids` set
  - both endpoint port_names exist on their referenced Asset.ports
  - source port has `direction=OUTPUT`, target port has
    `direction=INPUT`
  - source and target ports have matching `signal_type` (exact)
  - the wire is not the trivial self-loop (same asset + same port)

The fan-in check (target port already wired by another Wire) is NOT
performed here because it requires the Plan's CURRENT `wires` set —
it lives in the `add_plan_wire` decider directly. Same for duplicate
detection (re-add of an already-present Wire). Those are
collection-membership checks; this module is point-validation of one
proposed Wire against the cross-aggregate context.

Per the locked design at [[project_plan_wiring_design]]:

  - Strict forward-reference: reject if either endpoint port doesn't
    exist on the bound Asset RIGHT NOW. Operators must add ports
    BEFORE wiring against them; remove wires BEFORE removing the
    referenced ports (PostgreSQL FK shape).

The validators read `Asset.ports` and `Plan.asset_ids` only — they
take no I/O dependencies. The handler pre-loads the bound Assets
into a `PlanWireContext` (slice-local, mirrors `PlanBindingContext`
+ `RunStartContext`) before calling the decider.
"""

from collections.abc import Mapping
from uuid import UUID

from cora.equipment.aggregates._partition_rule import (
    PartitionRule,
    expected_constituent_count,
)
from cora.equipment.aggregates.asset import Asset, AssetPort, PortDirection
from cora.recipe.aggregates.plan.state import (
    PlanPseudoAxisArityMismatchError,
    PlanPseudoAxisFanoutSignalTypeMismatchError,
    PlanPseudoAxisOutputCardinalityError,
    PlanWireAssetNotBoundError,
    PlanWireDirectionMismatchError,
    PlanWirePortNotFoundError,
    PlanWireSelfLoopError,
    PlanWireSignalTypeMismatchError,
    Wire,
)


def _find_port(asset: Asset, port_name: str) -> AssetPort | None:
    """Return the AssetPort with the given name, or None if absent."""
    for port in asset.ports:
        if port.name == port_name:
            return port
    return None


def validate_wire_endpoints(
    wire: Wire,
    *,
    bound_asset_ids: frozenset[UUID],
    assets_by_id: Mapping[UUID, Asset],
) -> None:
    """Validate a Wire's endpoint structure against bound Assets.

    Performs (in order, fail-fast):
      1. self-loop guard (same asset + same port name) → `PlanWireSelfLoopError`
      2. asset-binding check (both endpoint asset_ids in `bound_asset_ids`)
         → `PlanWireAssetNotBoundError`
      3. port-existence check (both port names found on respective
         Asset.ports) → `PlanWirePortNotFoundError`
      4. direction check (source=OUTPUT, target=INPUT)
         → `PlanWireDirectionMismatchError`
      5. signal_type compatibility (exact match)
         → `PlanWireSignalTypeMismatchError`

    `assets_by_id` must contain entries for every bound asset_id the
    wire references; the handler is responsible for providing this
    via `PlanWireContext`. Self-loops on different ports of the same
    Asset ARE allowed (PandABox LUT block self-feedback pattern); the
    self-loop guard rejects ONLY the degenerate case where source and
    target are the same port.
    """
    # 1. self-loop on same port (degenerate)
    if (
        wire.source_asset_id == wire.target_asset_id
        and wire.source_port_name == wire.target_port_name
    ):
        raise PlanWireSelfLoopError(wire)

    # 2. asset-binding check (both endpoints must be bound by the Plan)
    missing_assets = sorted(
        (
            asset_id
            for asset_id in (wire.source_asset_id, wire.target_asset_id)
            if asset_id not in bound_asset_ids
        ),
        key=str,
    )
    if missing_assets:
        # de-dup if both endpoints reference the same missing asset
        unique_missing: list[UUID] = []
        for asset_id in missing_assets:
            if asset_id not in unique_missing:
                unique_missing.append(asset_id)
        raise PlanWireAssetNotBoundError(wire, unique_missing)

    # 3. port-existence check (each endpoint port must exist on its Asset)
    source_asset = assets_by_id[wire.source_asset_id]
    target_asset = assets_by_id[wire.target_asset_id]
    source_port = _find_port(source_asset, wire.source_port_name)
    target_port = _find_port(target_asset, wire.target_port_name)
    missing_ports: list[tuple[UUID, str, str]] = []
    if source_port is None:
        missing_ports.append((wire.source_asset_id, wire.source_port_name, "source"))
    if target_port is None:
        missing_ports.append((wire.target_asset_id, wire.target_port_name, "target"))
    if missing_ports:
        raise PlanWirePortNotFoundError(wire, missing_ports)

    # type narrowing for the remaining checks (mypy/pyright)
    assert source_port is not None
    assert target_port is not None

    # 4. direction check (source must be OUTPUT, target must be INPUT)
    if (
        source_port.direction is not PortDirection.OUTPUT
        or target_port.direction is not PortDirection.INPUT
    ):
        raise PlanWireDirectionMismatchError(
            wire,
            actual_source_direction=source_port.direction.value,
            actual_target_direction=target_port.direction.value,
        )

    # 5. signal_type compatibility (exact match)
    if source_port.signal_type != target_port.signal_type:
        raise PlanWireSignalTypeMismatchError(
            wire,
            source_signal_type=source_port.signal_type,
            target_signal_type=target_port.signal_type,
        )


def validate_pseudoaxis_fanout(
    *,
    pseudoaxis_asset: Asset,
    partition_rule: PartitionRule | None,
    incoming_wires: frozenset[Wire],
    assets_by_id: Mapping[UUID, Asset],
) -> None:
    """Validate fan-out into a PseudoAxis Asset's INPUT ports.

    Adds three checks on TOP of `validate_wire_endpoints` (which is
    per-wire structural). This validator looks at the full set of
    wires that target a single PseudoAxis Asset's INPUT ports and
    asks whether the SET satisfies the partition rule's contract:

      (a) Rule presence: if `partition_rule is None`, the Asset is
          PseudoAxis-shaped but the rule has not been set yet. That
          is an Equipment-side concern (the partition-rule slice), not
          a Plan-bind concern; this validator no-ops and lets earlier
          Plan-bind checks own the empty case.
      (b) Output cardinality: PseudoAxis Assets MUST declare exactly
          one OUTPUT port. Zero or two-plus OUTPUT ports raise
          `PlanPseudoAxisOutputCardinalityError`.
      (c) Over-arity: incoming wire count must NOT exceed
          `expected_constituent_count(rule)`. Under-wiring is allowed
          here (operators wire incrementally; the first add_plan_wire
          to a multi-constituent PseudoAxis would otherwise always
          trip strict equality). Under-arity is a Plan-completeness
          check that belongs at version_plan time, not per-wire add.
          `SolverReference` rules declare no arity (the external solver
          owns kinematics signature) and skip this check.
      (d) Signal-type homogeneity: all incoming wires' source ports
          must share one `signal_type`; mixed types raise
          `PlanPseudoAxisFanoutSignalTypeMismatchError`.

    Pure (no I/O). The caller (the `add_plan_wire` handler) is
    responsible for pre-loading every Asset that appears as a SOURCE
    of an incoming wire into `assets_by_id` before invocation; missing
    source assets would surface as a KeyError, which the handler
    prevents by load-then-validate ordering.

    `incoming_wires` MUST be the FULL set targeting this PseudoAxis
    Asset (the existing wires plus the proposed wire if this is an
    add-time invocation). The caller assembles the set; the validator
    just counts and reads.
    """
    # (a) rule not set: Plan-bind validator does not own this case.
    if partition_rule is None:
        return

    # (b) output cardinality: PseudoAxis Asset must have exactly 1 OUTPUT port.
    output_ports = [p for p in pseudoaxis_asset.ports if p.direction is PortDirection.OUTPUT]
    if len(output_ports) != 1:
        raise PlanPseudoAxisOutputCardinalityError(
            pseudoaxis_asset_id=pseudoaxis_asset.id,
            output_port_count=len(output_ports),
        )

    rule_kind = partition_rule.kind.value

    # (c) over-arity check (skip for SolverReference where expected is None).
    # Under-wiring is a Plan-completeness concern caught at version_plan time;
    # incremental add_plan_wire must accept the intermediate "still wiring"
    # state, otherwise no operator could ever wire a multi-constituent
    # PseudoAxis (the first add would always trip strict equality).
    expected = expected_constituent_count(partition_rule)
    if expected is not None and len(incoming_wires) > expected:
        raise PlanPseudoAxisArityMismatchError(
            pseudoaxis_asset_id=pseudoaxis_asset.id,
            expected_constituent_count=expected,
            actual_input_wire_count=len(incoming_wires),
            rule_kind=rule_kind,
        )

    # (d) signal-type homogeneity across the incoming wires' source ports.
    source_signal_types: set[str] = set()
    for wire in incoming_wires:
        source_asset = assets_by_id[wire.source_asset_id]
        source_port = _find_port(source_asset, wire.source_port_name)
        if source_port is None:
            # Defensive: validate_wire_endpoints rejects this on the
            # proposed wire; existing wires were validated before they
            # were added. A None here would mean an Asset port was
            # removed out from under a previously-valid wire, which is
            # blocked by the strict forward-reference contract. Skip
            # this wire rather than crash; the structural validator
            # owns the real error surface.
            continue
        source_signal_types.add(source_port.signal_type)

    if len(source_signal_types) > 1:
        raise PlanPseudoAxisFanoutSignalTypeMismatchError(
            pseudoaxis_asset_id=pseudoaxis_asset.id,
            signal_types=frozenset(source_signal_types),
            rule_kind=rule_kind,
        )


__all__ = ["validate_pseudoaxis_fanout", "validate_wire_endpoints"]
