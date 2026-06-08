"""Pure decider for the `RemoveSubject` command.

Multi-source-state transition (4f widening):
`Received | Mounted | Measured -> Removed`. Three valid source
states:

  - Received: sample arrived but was never mounted (legitimate
    "remove without use" workflow), OR sample was mounted then
    dismounted (4f re-mount cycle path) and the operator decided to
    remove rather than re-mount.
  - Mounted: sample physically present but no data collected yet
    (operator changed mind, removing without measuring).
  - Measured: data collected, ready to remove.

Source-state guard uses tuple-membership; the error message lists
all allowed source states for diagnostic clarity (carried by
`SubjectCannotRemoveError`).

`removed_by` is handler-injected from the request envelope's
`principal_id` (not on the command). The command surface omits the
field so callers cannot spoof a different removing actor; the
fold-symmetry attribution half then lands on the event payload per
[[project_fold_symmetry_design]].

Invariants:
  - State must not be None -> SubjectNotFoundError
  - State.status must be in {Received, Mounted, Measured}
    -> SubjectCannotRemoveError(current_status=...)
"""

from datetime import datetime

from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotRemoveError,
    SubjectNotFoundError,
    SubjectRemoved,
    SubjectStatus,
)
from cora.subject.features.remove_subject.command import RemoveSubject

_REMOVABLE_STATES: tuple[SubjectStatus, ...] = (
    SubjectStatus.RECEIVED,
    SubjectStatus.MOUNTED,
    SubjectStatus.MEASURED,
)


def decide(
    state: Subject | None,
    command: RemoveSubject,
    *,
    now: datetime,
    removed_by: ActorId,
) -> list[SubjectRemoved]:
    """Decide the events produced by removing an existing subject."""
    if state is None:
        raise SubjectNotFoundError(command.subject_id)
    if state.status not in _REMOVABLE_STATES:
        raise SubjectCannotRemoveError(state.id, current_status=state.status)
    return [SubjectRemoved(subject_id=state.id, occurred_at=now, removed_by=removed_by)]
