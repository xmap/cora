"""Read-side helper: resolve a PseudoAxis's constituents from Plan wires.

A PseudoAxis virtual axis decomposes into one or more physical constituent
Assets. Those constituents are NOT stored on the partition rule; they are
the `source` endpoints of the `Plan.wires` that feed the pseudoaxis's INPUT
ports (a constituent motor's OUTPUT port wired to the pseudoaxis's
`constituent_in`, validated at Plan-bind by `wires_validation`). At conduct
time the pre-Conductor expander needs that constituent list to rewrite a
virtual-axis setpoint into per-constituent setpoints; this helper extracts
it from a loaded Plan.

Pure function: no I/O. The caller loads the Plan (via the Run that the
Procedure is a phase of) and passes it in.
"""

from uuid import UUID

from cora.recipe.aggregates.plan.state import Plan


def constituents_from_wires(plan: Plan, pseudoaxis_asset_id: UUID) -> tuple[UUID, ...]:
    """Return the constituent Asset ids wired into a pseudoaxis, in order.

    The constituents of pseudoaxis P are the `source_asset_id`s of the
    `Plan.wires` whose `target_asset_id == P` (the source is the physical
    Asset whose OUTPUT port feeds P's INPUT port). The result is ordered by
    `(target_port_name, source_asset_id)`: deterministic, and for the
    single-constituent pseudoaxes in use today (hexapod DoFs, energy facets,
    the foil selector) trivially the one wired Asset. For a future
    multi-constituent pseudoaxis the target input-port name carries the
    position; the consuming partition rule's `expected_constituent_count`
    cross-checks the count at evaluate time.

    Returns an empty tuple when no wire targets the pseudoaxis (the caller
    surfaces the resulting arity mismatch through the evaluator).
    """
    incoming = sorted(
        (wire for wire in plan.wires if wire.target_asset_id == pseudoaxis_asset_id),
        key=lambda wire: (wire.target_port_name, str(wire.source_asset_id)),
    )
    return tuple(wire.source_asset_id for wire in incoming)


__all__ = ["constituents_from_wires"]
