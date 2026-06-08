"""Pure decider for the `StoreSubject` command.

Terminal disposition: `Removed -> Stored`. Single-source guard
(only `Removed` is a valid prior state). Mirrors `return_subject` /
`discard_subject` — three-sibling terminal disposition pattern.

Strict semantics, not idempotent: re-storing an already-`Stored`
subject raises rather than no-op.

`stored_by` is handler-injected from the request envelope's
`principal_id` (not on the command). The command surface omits the
field so callers cannot spoof a different storing actor; the
fold-symmetry attribution half then lands on the event payload per
[[project_fold_symmetry_design]].

Invariants:
  - State must not be None -> SubjectNotFoundError
  - State.status must be `Removed` -> SubjectCannotStoreError(current_status=...)
"""

from datetime import datetime

from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotStoreError,
    SubjectNotFoundError,
    SubjectStatus,
    SubjectStored,
)
from cora.subject.features.store_subject.command import StoreSubject


def decide(
    state: Subject | None,
    command: StoreSubject,
    *,
    now: datetime,
    stored_by: ActorId,
) -> list[SubjectStored]:
    """Decide the events produced by storing an existing subject."""
    if state is None:
        raise SubjectNotFoundError(command.subject_id)
    if state.status is not SubjectStatus.REMOVED:
        raise SubjectCannotStoreError(state.id, current_status=state.status)
    return [SubjectStored(subject_id=state.id, occurred_at=now, stored_by=stored_by)]
