"""Pure decider for the `DiscardDistribution` command.

Guarded primitive: a Distribution copy may be marked Discarded only
when a SIBLING copy of the same Dataset is Verified on a DIFFERENT
storage tier (a different `supply_id`), AND the parent Dataset is not
itself Discarded. Strict semantics, not idempotent: re-discarding an
already-`Discarded` copy raises rather than no-op (matches every other
terminal-transition pattern in the codebase).

Metadata-only: the discard records the reclaim decision + reason; the
bytes for this copy are reclaimed out-of-band, the same posture as
`DatasetDiscarded`. No storage deletion is issued here.

## Firing order

  1. State must not be None -> DistributionNotFoundError.
  2. command.reason validated via DistributionDiscardReason VO
     (1-500 chars after trim) -> InvalidDistributionDiscardReasonError.
     Validated BEFORE the state guards, mirroring discard_dataset: a bad
     reason on an already-Discarded copy raises the reason error, not the
     cannot-discard error.
  3. state.status is DISCARDED -> DistributionCannotDiscardError
     (strict-not-idempotent).
  4. parent Dataset is Discarded ->
     DistributionCannotDiscardUnderDiscardedDatasetError.
  5. last-Verified redundancy guard: require any sibling copy of the same
     Dataset that is Verified on a different supply_id ->
     DistributionCannotDiscardLastVerifiedError otherwise.
  6. Emit DistributionDiscarded.

## The sibling-Verified read is projection-derived (eventual)

`context.sibling_distributions` comes from the projection-backed
`DatasetDistributionLookup`, NOT from folding sibling Distribution
aggregates. This is deliberate: a Distribution's `Verified` status is
projection-only (the flip lands on `proj_data_distribution_summary` via
the AttestationRecorded subscription; a folded Distribution aggregate is
always `status=Registered` because the Verified/Stale transitions emit no
stream event). Reading siblings from the aggregate would never see a
Verified copy. The redundancy gate therefore reads the same eventual
signal the start_run input gate reads, with the same eventual-consistency
stance.

## Accepted two-concurrent-discards race (deferred strong fix)

Two operators discarding two different copies of the same Dataset at the
same moment can each see the OTHER as the safe Verified-on-a-different-
tier sibling and both succeed, leaving the Dataset with zero non-Discarded
Verified copies. The race is accepted here because the discard is
metadata-only and recoverable (the bytes are reclaimed out-of-band, after
the metadata decision, so a quick double-discard does not by itself
destroy data), and because a zero-Verified-copies auditor (a separate
follow-up slice) is the backstop that detects the lost-redundancy state.
The strong fix, a compare-and-swap on the parent Dataset stream that
serializes concurrent discards under the same Dataset, is DESIGNED-IN but
deferred. This mirrors the way start_run documents its eventual-Verified
input gate rather than taking a distributed lock.

## Verified/Stale stay projection-only

This slice does NOT retro-convert the Verified/Stale projection flip into
Distribution-stream events. The only Distribution-stream transition this
slice adds is `DistributionDiscarded`.
"""

from datetime import datetime

from cora.data.aggregates.dataset import DatasetStatus
from cora.data.aggregates.distribution import (
    Distribution,
    DistributionCannotDiscardError,
    DistributionCannotDiscardLastVerifiedError,
    DistributionCannotDiscardUnderDiscardedDatasetError,
    DistributionDiscarded,
    DistributionDiscardReason,
    DistributionNotFoundError,
    DistributionStatus,
)
from cora.data.features.discard_distribution.command import DiscardDistribution
from cora.data.features.discard_distribution.context import DiscardDistributionContext
from cora.shared.identity import ActorId

#: Wire value of `DistributionStatus.VERIFIED` read off the
#: projection-backed sibling lookup result. The lookup carries
#: `status` as a plain string (the projection's TEXT column), so the
#: redundancy check compares against the literal, the same posture as
#: the start_run input gate.
_VERIFIED_STATUS = DistributionStatus.VERIFIED.value


def decide(
    state: Distribution | None,
    command: DiscardDistribution,
    *,
    context: DiscardDistributionContext,
    now: datetime,
    discarded_by: ActorId,
) -> list[DistributionDiscarded]:
    """Decide the events produced by discarding a Distribution copy.

    Invariants:
      (Firing order per the module docstring above.)
      - State must not be None -> DistributionNotFoundError
      - command.reason must be 1-500 chars after trimming
        -> InvalidDistributionDiscardReasonError
      - State.status must not be Discarded
        -> DistributionCannotDiscardError
      - Parent Dataset must not be Discarded
        -> DistributionCannotDiscardUnderDiscardedDatasetError
      - A sibling copy must be Verified on a different supply_id
        -> DistributionCannotDiscardLastVerifiedError
    """
    if state is None:
        raise DistributionNotFoundError(command.distribution_id)
    reason = DistributionDiscardReason(command.reason)
    if state.status is DistributionStatus.DISCARDED:
        raise DistributionCannotDiscardError(state.id, current_status=state.status)
    if context.dataset.status is DatasetStatus.DISCARDED:
        raise DistributionCannotDiscardUnderDiscardedDatasetError(
            distribution_id=state.id, dataset_id=state.dataset_id
        )
    has_verified_sibling_on_other_tier = any(
        sibling.distribution_id != state.id
        and sibling.supply_id != state.supply_id
        and sibling.status == _VERIFIED_STATUS
        for sibling in context.sibling_distributions
    )
    if not has_verified_sibling_on_other_tier:
        raise DistributionCannotDiscardLastVerifiedError(
            distribution_id=state.id, dataset_id=state.dataset_id
        )
    return [
        DistributionDiscarded(
            distribution_id=state.id,
            reason=reason.value,
            occurred_at=now,
            discarded_by=discarded_by,
        )
    ]
