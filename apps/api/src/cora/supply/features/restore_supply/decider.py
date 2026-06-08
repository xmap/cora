"""Pure decider for the `RestoreSupply` command.

Single-source transition: `{Recovering} -> Available`. This is the
recovery-acknowledgement event, distinct from
`SupplyMarkedAvailable` (first-observation declaration) per the
Phoebus latched-alarm precedent. Strict-not-idempotent.
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

# Single-source today, but kept as a frozenset constant for symmetry with
# the multi-source guards (`degrade_supply`, `mark_supply_unavailable`)
# so day-2 widening is a one-line edit, not a predicate-shape rewrite.
_RESTORABLE_FROM: frozenset[SupplyStatus] = frozenset({SupplyStatus.RECOVERING})


def decide(
    state: Supply | None,
    command: RestoreSupply,
    *,
    now: datetime,
    triggered_by: ActorId,
) -> list[SupplyRestored]:
    """Decide the events produced by restoring a Recovering Supply.

    Invariants:
      - State must not be None -> SupplyNotFoundError
      - Current status must be Recovering -> SupplyCannotRestoreError
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
