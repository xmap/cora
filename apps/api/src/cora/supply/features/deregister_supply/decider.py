"""Pure decider for the `DeregisterSupply` command.

Widest-source transition: any non-Decommissioned status transitions
to Decommissioned (the lifecycle terminal). Strict-not-idempotent:
re-deregistering an already-Decommissioned supply raises.
"""

from datetime import datetime

from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    Supply,
    SupplyCannotDeregisterError,
    SupplyDeregistered,
    SupplyNotFoundError,
    SupplyReason,
    SupplyStatus,
    TriggerSource,
)
from cora.supply.features.deregister_supply.command import DeregisterSupply


def decide(
    state: Supply | None,
    command: DeregisterSupply,
    *,
    now: datetime,
    triggered_by: ActorId,
) -> list[SupplyDeregistered]:
    """Decide the events produced by deregistering a Supply.

    Invariants:
      - State must not be None -> SupplyNotFoundError
      - Current status must not be Decommissioned ->
        SupplyCannotDeregisterError
      - Reason must be valid -> InvalidSupplyReasonError
        (via SupplyReason VO)

    `triggered_by` is the operator's `ActorId`. Deregistration is
    operator-only per [[project_deregister_supply_design]]; no
    Monitor or Auto counterpart (no substream or timer should ever
    auto-decommission a Supply).
    """
    if state is None:
        raise SupplyNotFoundError(command.supply_id)
    if state.status is SupplyStatus.DECOMMISSIONED:
        raise SupplyCannotDeregisterError(state.id, state.status)

    reason = SupplyReason(command.reason)

    return [
        SupplyDeregistered(
            supply_id=state.id,
            from_status=state.status.value,
            reason=reason.value,
            trigger=TriggerSource.OPERATOR.value,
            triggered_by=triggered_by,
            occurred_at=now,
        )
    ]
