"""Pure decider for the `DegradeSupply` command.

Multi-source transition: `{Unknown, Available, Recovering} ->
Degraded`. Strict-not-idempotent: re-degrading an already-Degraded
supply raises. Same audit-triple payload as
`SupplyMarkedAvailable`.

## Validation

  - State must not be None (supply must exist) -> SupplyNotFoundError
  - Current status must be in `{Unknown, Available, Recovering}`
    -> SupplyCannotDegradeError
  - `reason` validated 1-500 chars via `SupplyReason` VO
    -> InvalidSupplyReasonError

## Trigger source: hardcoded Operator

10a-b only emits Operator-triggered transitions. Same convention as
`mark_supply_available`.
"""

from datetime import datetime

from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    Supply,
    SupplyCannotDegradeError,
    SupplyDegraded,
    SupplyNotFoundError,
    SupplyReason,
    SupplyStatus,
    TriggerSource,
)
from cora.supply.features.degrade_supply.command import DegradeSupply

_DEGRADABLE_STATUSES: frozenset[SupplyStatus] = frozenset(
    {SupplyStatus.UNKNOWN, SupplyStatus.AVAILABLE, SupplyStatus.RECOVERING}
)


def decide(
    state: Supply | None,
    command: DegradeSupply,
    *,
    now: datetime,
    triggered_by: ActorId,
) -> list[SupplyDegraded]:
    """Decide the events produced by degrading a Supply.

    Invariants:
      - State must not be None -> SupplyNotFoundError
      - Current status must be Unknown, Available, or Recovering
        -> SupplyCannotDegradeError
      - Reason must be valid -> InvalidSupplyReasonError
        (via SupplyReason VO)

    `triggered_by` is the operator's `ActorId`. Monitor-driven
    degrade flows through `observe_supply_status` (separate slice).
    """
    if state is None:
        raise SupplyNotFoundError(command.supply_id)
    if state.status not in _DEGRADABLE_STATUSES:
        raise SupplyCannotDegradeError(state.id, state.status)

    reason = SupplyReason(command.reason)

    return [
        SupplyDegraded(
            supply_id=state.id,
            from_status=state.status.value,
            reason=reason.value,
            trigger=TriggerSource.OPERATOR.value,
            triggered_by=triggered_by,
            occurred_at=now,
        )
    ]
