"""Pure decider for the `MarkSupplyUnavailable` command.

Multi-source transition (widest source set): `{Unknown, Available,
Degraded, Recovering} -> Unavailable`. Strict-not-idempotent: re-
marking an already-Unavailable supply raises.
"""

from datetime import datetime

from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    Supply,
    SupplyCannotMarkUnavailableError,
    SupplyMarkedUnavailable,
    SupplyNotFoundError,
    SupplyReason,
    SupplyStatus,
    TriggerSource,
)
from cora.supply.features.mark_supply_unavailable.command import MarkSupplyUnavailable

_MARKABLE_UNAVAILABLE_STATUSES: frozenset[SupplyStatus] = frozenset(
    {
        SupplyStatus.UNKNOWN,
        SupplyStatus.AVAILABLE,
        SupplyStatus.DEGRADED,
        SupplyStatus.RECOVERING,
    }
)


def decide(
    state: Supply | None,
    command: MarkSupplyUnavailable,
    *,
    now: datetime,
    triggered_by: ActorId,
) -> list[SupplyMarkedUnavailable]:
    """Decide the events produced by marking a Supply Unavailable.

    Invariants:
      - State must not be None -> SupplyNotFoundError
      - Current status must be Unknown, Available, Degraded, or
        Recovering -> SupplyCannotMarkUnavailableError
      - Reason must be valid -> InvalidSupplyReasonError
        (via SupplyReason VO)

    `triggered_by` is the operator's `ActorId`. Monitor-driven
    unavailable transitions flow through `observe_supply_status`.
    """
    if state is None:
        raise SupplyNotFoundError(command.supply_id)
    if state.status not in _MARKABLE_UNAVAILABLE_STATUSES:
        raise SupplyCannotMarkUnavailableError(state.id, state.status)

    reason = SupplyReason(command.reason)

    return [
        SupplyMarkedUnavailable(
            supply_id=state.id,
            from_status=state.status.value,
            reason=reason.value,
            trigger=TriggerSource.OPERATOR.value,
            triggered_by=triggered_by,
            occurred_at=now,
        )
    ]
