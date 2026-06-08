"""Pure decider for the `MeasureSubject` command.

Update-style decider: receives the rebuilt `Subject` state (folded
from the loaded event stream) and returns the events to append. No
I/O.

Invariants:
  - State must not be None (subject must exist) -> SubjectNotFoundError
  - State must be in `Mounted` (the only state from which measurement
    is valid) -> SubjectCannotMeasureError(current_status=...)

Strict semantics, not idempotent: re-measuring an already-`Measured`
subject raises rather than no-op or always-emit. Per-measurement
detail (which scan, params, results) is out of scope at the
aggregate level — that lives in `Run` observation channels later. The
aggregate-level `Measured` status just means "has been measured at
least once". Same precedent as `mount_subject` and
`deactivate_actor`.

`measured_by` is handler-injected from the request envelope's
`principal_id` (not on the command). The command surface omits the
field so callers cannot spoof a different measuring actor; the
fold-symmetry attribution half then lands on the event payload per
[[project_fold_symmetry_design]].
"""

from datetime import datetime

from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotMeasureError,
    SubjectMeasured,
    SubjectNotFoundError,
    SubjectStatus,
)
from cora.subject.features.measure_subject.command import MeasureSubject


def decide(
    state: Subject | None,
    command: MeasureSubject,
    *,
    now: datetime,
    measured_by: ActorId,
) -> list[SubjectMeasured]:
    """Decide the events produced by measuring an existing subject."""
    if state is None:
        raise SubjectNotFoundError(command.subject_id)
    if state.status is not SubjectStatus.MOUNTED:
        raise SubjectCannotMeasureError(state.id, current_status=state.status)
    return [SubjectMeasured(subject_id=state.id, occurred_at=now, measured_by=measured_by)]
