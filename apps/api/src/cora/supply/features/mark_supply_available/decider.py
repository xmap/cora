"""Pure decider for the `MarkSupplyAvailable` command.

Single-source transition: `Unknown -> Available`. Strict-not-
idempotent: re-marking an already-Available supply raises (per
[[project_supply_design]] §Locks; matches the 5g-c strict-by-default
cross-BC anchor).

Distinct from `restore_supply` (10a-b) which exits `Recovering ->
Available`: the two transitions target the same status but carry
different audit semantics (first-observation declaration vs
recovery-confirmation acknowledgement) per the Phoebus latched-
alarm precedent.

## Validation

  - State must not be None (supply must exist) -> SupplyNotFoundError
  - Current status must be `Unknown` -> SupplyCannotMarkAvailableError
  - `reason` validated 1-500 chars via `SupplyReason` VO
    -> InvalidSupplyReasonError

## Trigger source: hardcoded Operator

The TriggerSource enum is locked 3-value day one (Operator | Monitor
| Auto) for forward-compat. In 10a-a only Operator slices exist;
this decider hardcodes `trigger=TriggerSource.OPERATOR.value` on the
emitted event payload. When the Monitor slice family ships (Watch
item 2 in [[project_supply_design]]), it gets its own slice with
trigger=Monitor; the same applies to Auto-restore (Watch item 1).
"""

from datetime import datetime

from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    Supply,
    SupplyCannotMarkAvailableError,
    SupplyMarkedAvailable,
    SupplyNotFoundError,
    SupplyReason,
    SupplyStatus,
    TriggerSource,
)
from cora.supply.features.mark_supply_available.command import MarkSupplyAvailable


def decide(
    state: Supply | None,
    command: MarkSupplyAvailable,
    *,
    now: datetime,
    triggered_by: ActorId,
) -> list[SupplyMarkedAvailable]:
    """Decide the events produced by marking a registered Supply Available.

    Invariants:
      - State must not be None -> SupplyNotFoundError
      - Current status must be Unknown
        -> SupplyCannotMarkAvailableError
      - Reason must be valid -> InvalidSupplyReasonError
        (via SupplyReason VO)

    `triggered_by` is the operator's `ActorId` (operator-only slice;
    Monitor first-observation is fenced per Anti-hook 2 in
    [[project_supply_design]]). Folded onto the event payload alongside
    trigger="Operator" per [[project_fold_symmetry_design]].
    """
    if state is None:
        raise SupplyNotFoundError(command.supply_id)
    if state.status is not SupplyStatus.UNKNOWN:
        raise SupplyCannotMarkAvailableError(state.id, state.status)

    # Validate + trim reason via VO; raises InvalidSupplyReasonError.
    reason = SupplyReason(command.reason)

    return [
        SupplyMarkedAvailable(
            supply_id=state.id,
            from_status=state.status.value,
            reason=reason.value,
            trigger=TriggerSource.OPERATOR.value,
            triggered_by=triggered_by,
            occurred_at=now,
        )
    ]
