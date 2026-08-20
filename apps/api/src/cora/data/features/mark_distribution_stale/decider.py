"""Pure decider for the `MarkDistributionStale` command.

Marking stale records a fact about the world that already happened (the
bytes at this location are gone or no longer trusted); it is not a
deliberate act CORA is entitled to refuse, unlike `discard_distribution`.
The decider therefore does NOT mirror discard's guards: no redundancy
check against sibling copies, no parent-Dataset-Discarded check, and no
cross-aggregate context. The only guards are structural.

## Firing order

  1. State must not be None -> DistributionNotFoundError.
  2. command.reason validated via DistributionMarkStaleReason VO
     (1-500 chars after trim) -> InvalidDistributionMarkStaleReasonError.
     Validated BEFORE the state guard, mirroring discard_distribution: a
     bad reason on an already-Discarded copy raises the reason error, not
     the cannot-mark-stale error.
  3. state.status is DISCARDED -> DistributionCannotMarkStaleError
     (Discarded is terminal; a Discarded copy cannot be marked Stale).
  4. Emit DistributionMarkedStale with trigger hardcoded to
     TriggerSource.OPERATOR.

## Trigger source: hardcoded Operator

Mirrors every operator-facing Supply decider. The value is NOT taken
from the command: this slice's only surfaces are the REST route and the
MCP tool, both operator-driven, and letting a caller supply the field
would let a principal assert its own claim came from a monitor. When a
reconciliation sweep lands, it emits the same event with
TriggerSource.MONITOR from its own slice, exactly as Supply's
observe_supply_status does.

## Marking an already-Stale (or Verified, or Registered) copy succeeds

Re-marking a copy that is already Stale is NOT strict-not-idempotent
like discard: a second storage-failure report, or a report that arrives
after an independent checksum-mismatch flip already moved the read
model to Stale, is still a true fact and is recorded again (a fresh
`marked_stale_at` / `marked_stale_by`). The only status this decider
refuses to transition out of is Discarded.

## Deliberately no last-Verified-copy guard

Discarding the last Verified copy of a Dataset is refused
(`DistributionCannotDiscardLastVerifiedError`) because CORA is entitled
to refuse a deliberate destructive act. Marking stale has no equivalent
guard: if the array holding the last Verified copy died, the array
died, and refusing to record that would make CORA assert something
false. This is the one design decision this slice is built around; do
not add a redundancy guard here.
"""

from datetime import datetime

from cora.data.aggregates.distribution import (
    Distribution,
    DistributionCannotMarkStaleError,
    DistributionMarkedStale,
    DistributionMarkStaleReason,
    DistributionNotFoundError,
    DistributionStatus,
    TriggerSource,
)
from cora.data.features.mark_distribution_stale.command import MarkDistributionStale
from cora.shared.identity import ActorId


def decide(
    state: Distribution | None,
    command: MarkDistributionStale,
    *,
    now: datetime,
    marked_stale_by: ActorId,
) -> list[DistributionMarkedStale]:
    """Decide the events produced by marking a Distribution copy Stale.

    Invariants:
      (Firing order per the module docstring above.)
      - State must not be None -> DistributionNotFoundError
      - command.reason must be 1-500 chars after trimming
        -> InvalidDistributionMarkStaleReasonError
      - State.status must not be Discarded (terminal)
        -> DistributionCannotMarkStaleError
    """
    if state is None:
        raise DistributionNotFoundError(command.distribution_id)
    reason = DistributionMarkStaleReason(command.reason)
    if state.status is DistributionStatus.DISCARDED:
        raise DistributionCannotMarkStaleError(state.id, current_status=state.status)
    return [
        DistributionMarkedStale(
            distribution_id=state.id,
            reason=reason.value,
            trigger=TriggerSource.OPERATOR.value,
            occurred_at=now,
            marked_stale_by=marked_stale_by,
        )
    ]
