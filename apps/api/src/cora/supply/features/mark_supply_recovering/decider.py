"""Pure decider for the `MarkSupplyRecovering` command.

Single-source transition: `{Unavailable} -> Recovering`.
Strict-not-idempotent: re-marking an already-Recovering supply
raises.
"""

from datetime import datetime

from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    Supply,
    SupplyCannotMarkRecoveringError,
    SupplyMarkedRecovering,
    SupplyNotFoundError,
    SupplyReason,
    SupplyStatus,
    TriggerSource,
)
from cora.supply.features.mark_supply_recovering.command import MarkSupplyRecovering

# Single-source today, but kept as a frozenset constant for symmetry with
# the multi-source guards (`degrade_supply`, `mark_supply_unavailable`)
# so day-2 widening is a one-line edit, not a predicate-shape rewrite.
_RECOVERABLE_FROM: frozenset[SupplyStatus] = frozenset({SupplyStatus.UNAVAILABLE})


def decide(
    state: Supply | None,
    command: MarkSupplyRecovering,
    *,
    now: datetime,
    triggered_by: ActorId,
) -> list[SupplyMarkedRecovering]:
    """Decide the events produced by marking a Supply Recovering.

    Invariants:
      - State must not be None -> SupplyNotFoundError
      - Current status must be Unavailable
        -> SupplyCannotMarkRecoveringError
      - Reason must be valid -> InvalidSupplyReasonError
        (via SupplyReason VO)

    `triggered_by` is the operator's `ActorId`. Monitor-driven
    recovering transitions flow through `observe_supply_status`.
    """
    if state is None:
        raise SupplyNotFoundError(command.supply_id)
    if state.status not in _RECOVERABLE_FROM:
        raise SupplyCannotMarkRecoveringError(state.id, state.status)

    reason = SupplyReason(command.reason)

    return [
        SupplyMarkedRecovering(
            supply_id=state.id,
            from_status=state.status.value,
            reason=reason.value,
            trigger=TriggerSource.OPERATOR.value,
            triggered_by=triggered_by,
            occurred_at=now,
        )
    ]
