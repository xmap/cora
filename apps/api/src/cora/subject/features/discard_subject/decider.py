"""Pure decider for the `DiscardSubject` command.

Terminal disposition: `Removed -> Discarded`. Single-source guard
(only `Removed` is a valid prior state). Mirrors `return_subject` /
`store_subject` -- three-sibling terminal disposition pattern.

Strict semantics, not idempotent: re-discarding an already-`Discarded`
subject raises rather than no-op.

`reason` validation goes through the `SubjectDiscardReason` VO
(which calls the shared `validate_bounded_text` helper). The on-the-wire
payload in `SubjectDiscarded.reason` carries the trimmed string.

`discarded_by` is handler-injected from the request envelope's
`principal_id` (not on the command). The command surface omits the
field so callers cannot spoof a different discarding actor; the
fold-symmetry attribution half then lands on the event payload per
[[project_fold_symmetry_design]].

Invariants:
  - State must not be None -> SubjectNotFoundError
  - command.reason must be 1-500 chars after trimming
    -> InvalidSubjectDiscardReasonError
  - State.status must be `Removed`
    -> SubjectCannotDiscardError(current_status=...)
"""

from datetime import datetime

from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotDiscardError,
    SubjectDiscarded,
    SubjectDiscardReason,
    SubjectNotFoundError,
    SubjectStatus,
)
from cora.subject.features.discard_subject.command import DiscardSubject


def decide(
    state: Subject | None,
    command: DiscardSubject,
    *,
    now: datetime,
    discarded_by: ActorId,
) -> list[SubjectDiscarded]:
    """Decide the events produced by discarding an existing subject."""
    if state is None:
        raise SubjectNotFoundError(command.subject_id)
    reason = SubjectDiscardReason(command.reason)
    if state.status is not SubjectStatus.REMOVED:
        raise SubjectCannotDiscardError(state.id, current_status=state.status)
    return [
        SubjectDiscarded(
            subject_id=state.id,
            reason=reason.value,
            occurred_at=now,
            discarded_by=discarded_by,
        )
    ]
