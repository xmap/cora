"""Pure decider for the `CompleteSealRepublishing` command.

Single-source transition: `Republishing -> Live`. Strict-not-idempotent
(matches the Calibration / Clearance / Supply / Permit / Credential
precedent): completing a republish on a Seal that is not in
`Republishing` status raises `SealCannotCompleteRepublishingError`.

`completed_by` is handler-injected from the request envelope's
`principal_id` per the non-determinism principle (capture, don't
recompute). The decider is pure: state + command + injected
non-determinism in, events out.

## Validation

  - State must not be None (Seal must exist)
    -> SealNotFoundError
  - Current status must be `Republishing`
    -> SealCannotCompleteRepublishingError
  - `new_head_hash` and `new_sequence_number` MUST be supplied together
    or omitted together (pairing invariant; the back-edge carries both
    or neither) -> InvalidSealHeadHashError
  - When omitted, the prior `state.current_head_hash` MUST already be
    set (a republish-without-fresh-head only makes sense after at least
    one signing) -> InvalidSealHeadHashError
  - When supplied, `new_sequence_number` MUST be strictly greater than
    `state.current_sequence_number`
    -> SealSequenceNumberRegressionError

Cross-aggregate purpose binding is not in this slice's scope: the
back-edge does not mutate either key ref, so `_key_separation` is not
invoked here.
"""

from datetime import datetime

from cora.federation.aggregates.seal import (
    InvalidSealHeadHashError,
    Seal,
    SealCannotCompleteRepublishingError,
    SealNotFoundError,
    SealRepublishingCompleted,
    SealSequenceNumberRegressionError,
    SealStatus,
)
from cora.federation.features.complete_seal_republishing.command import (
    CompleteSealRepublishing,
)
from cora.shared.identity import ActorId


def decide(
    state: Seal | None,
    command: CompleteSealRepublishing,
    *,
    now: datetime,
    completed_by: ActorId,
) -> list[SealRepublishingCompleted]:
    """Decide the events produced by completing a Seal republish.

    Invariants:
      - State must not be None -> SealNotFoundError
      - Status must be Republishing
        -> SealCannotCompleteRepublishingError
      - head_hash / sequence_number pair supplied together or omitted
        together -> InvalidSealHeadHashError
      - When omitted, prior head_hash must already exist
        -> InvalidSealHeadHashError
      - When supplied, sequence_number strictly greater than prior
        -> SealSequenceNumberRegressionError
    """
    if state is None:
        raise SealNotFoundError(command.facility_id)
    if state.status is not SealStatus.REPUBLISHING:
        raise SealCannotCompleteRepublishingError(
            facility_id=state.facility_id,
            current_status=state.status,
        )

    head_supplied = command.new_head_hash is not None
    seq_supplied = command.new_sequence_number is not None
    if head_supplied != seq_supplied:
        raise InvalidSealHeadHashError(
            "new_head_hash and new_sequence_number must be supplied "
            "together or omitted together "
            f"(new_head_hash={command.new_head_hash!r}, "
            f"new_sequence_number={command.new_sequence_number!r})"
        )

    if head_supplied:
        assert command.new_head_hash is not None
        assert command.new_sequence_number is not None
        if command.new_sequence_number <= state.current_sequence_number:
            raise SealSequenceNumberRegressionError(
                facility_id=state.facility_id,
                prior_sequence_number=state.current_sequence_number,
                proposed_sequence_number=command.new_sequence_number,
            )
        new_head_hash = command.new_head_hash
        new_sequence_number = command.new_sequence_number
    else:
        if state.current_head_hash is None:
            raise InvalidSealHeadHashError(
                f"Seal for facility {state.facility_id!r}: "
                f"complete_seal_republishing without new_head_hash requires "
                f"a prior signing (current_head_hash is None)"
            )
        new_head_hash = state.current_head_hash
        new_sequence_number = state.current_sequence_number

    return [
        SealRepublishingCompleted(
            facility_id=state.facility_id,
            new_head_hash=new_head_hash,
            new_sequence_number=new_sequence_number,
            completed_by=completed_by,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
