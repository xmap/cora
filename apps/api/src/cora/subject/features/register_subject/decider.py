"""Pure decider for the `RegisterSubject` command.

Pure function: given the current Subject state (None for a fresh
stream) and a `RegisterSubject` command, returns the events to
append. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports.

`registered_by` is handler-injected from the request envelope's
`principal_id` (not on the command). The command surface omits the
field so callers cannot spoof a different registering actor; the
fold-symmetry attribution half then lands on the event payload per
[[project_fold_symmetry_design]]. Subject state itself stays
fold-NEITHER (no actor folded onto the aggregate).
"""

from datetime import datetime
from uuid import UUID

from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import (
    Subject,
    SubjectAlreadyExistsError,
    SubjectName,
    SubjectRegistered,
)
from cora.subject.features.register_subject.command import RegisterSubject


def decide(
    state: Subject | None,
    command: RegisterSubject,
    *,
    now: datetime,
    new_id: UUID,
    registered_by: ActorId,
) -> list[SubjectRegistered]:
    """Decide the events produced by registering a new subject.

    Invariants:
      - State must be None (genesis-only)
        -> SubjectAlreadyExistsError
      - Name must be valid -> InvalidSubjectNameError
        (via SubjectName VO)
    """
    if state is not None:
        raise SubjectAlreadyExistsError(state.id)
    name = SubjectName(command.name)  # validates + trims; raises InvalidSubjectNameError
    return [
        SubjectRegistered(
            subject_id=new_id,
            name=name.value,
            occurred_at=now,
            registered_by=registered_by,
        )
    ]
