"""Pure decider for the `RestoreSupply` command.

`{Recovering, Degraded} -> Available`: an operator declaring a resource
back to nominal. Distinct from `SupplyMarkedAvailable`, which is the
first-observation declaration out of `Unknown`. Strict-not-idempotent.

## Why two sources

`Degraded` was added because it was the one transition the
`SupplyStatus` FSM documented and nothing implemented. Before this, a
degraded Supply could only go deeper: the exit was
`mark_supply_unavailable` then `mark_supply_recovering` then here, three
gestures whose first step appends "this resource was unavailable" to an
append-only log about a resource that was never down. Recording a
falsehood to satisfy a state machine is the wrong trade, so the source
set widened instead.

One event covers both because `SupplyRestored.from_status` already
distinguishes them: "restored after an outage" and "restored after a
shortfall" are separate facts on the wire without a separate class. See
[[project_supply_degraded_restore_design]].

## What widening does NOT do

Restore stays operator-only. `observe_supply_status` fences `Available`
out of the monitor path entirely (`_MONITOR_FORBIDDEN_TARGETS`), so no
sensor reaches it from either source. The Phoebus latched-alarm
precedent this slice cites is about requiring a human rather than an
auto-timer, not about which state the resource came from, so it is
untouched.
"""

from datetime import datetime

from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    Supply,
    SupplyCannotRestoreError,
    SupplyNotFoundError,
    SupplyReason,
    SupplyRestored,
    SupplyStatus,
    TriggerSource,
)
from cora.supply.features.restore_supply.command import RestoreSupply

# The constant was written as a frozenset for exactly this edit: its
# original comment said "day-2 widening is a one-line edit, not a
# predicate-shape rewrite", and so it was.
_RESTORABLE_FROM: frozenset[SupplyStatus] = frozenset(
    {SupplyStatus.RECOVERING, SupplyStatus.DEGRADED}
)


def decide(
    state: Supply | None,
    command: RestoreSupply,
    *,
    now: datetime,
    triggered_by: ActorId,
) -> list[SupplyRestored]:
    """Decide the events produced by restoring a Supply to Available.

    Invariants:
      - State must not be None -> SupplyNotFoundError
      - Current status must be Recovering or Degraded ->
        SupplyCannotRestoreError
      - Reason must be valid -> InvalidSupplyReasonError
        (via SupplyReason VO)

    `triggered_by` is the operator's `ActorId`. Restore is operator-
    only per the latched-alarm Anti-hook in [[project_supply_design]];
    no Monitor or Auto counterpart.
    """
    if state is None:
        raise SupplyNotFoundError(command.supply_id)
    if state.status not in _RESTORABLE_FROM:
        raise SupplyCannotRestoreError(state.id, state.status)

    reason = SupplyReason(command.reason)

    return [
        SupplyRestored(
            supply_id=state.id,
            from_status=state.status.value,
            reason=reason.value,
            trigger=TriggerSource.OPERATOR.value,
            triggered_by=triggered_by,
            occurred_at=now,
        )
    ]
