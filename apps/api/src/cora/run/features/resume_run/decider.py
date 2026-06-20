"""Pure decider for the `ResumeRun` command.

Single-source resume transition: `Held -> Running`. The inverse
of hold (which requires `Running`). Resuming an already-`Running`
Run raises (strict-not-idempotent); resuming a terminal Run raises.

Invariants:
  - State must not be None  -> RunNotFoundError
  - State.status must be in {Held}
    -> RunCannotResumeError(current_status=...)
"""

from datetime import datetime

from cora.run.aggregates.run import (
    Run,
    RunCannotResumeError,
    RunNotFoundError,
    RunResumed,
    RunStatus,
)
from cora.run.features.resume_run.command import ResumeRun

_RESUMABLE_STATUSES: tuple[RunStatus, ...] = (RunStatus.HELD,)


def decide(
    state: Run | None,
    command: ResumeRun,
    *,
    now: datetime,
) -> list[RunResumed]:
    """Decide the events produced by resuming a held Run."""
    if state is None:
        raise RunNotFoundError(command.run_id)
    if state.status not in _RESUMABLE_STATUSES:
        raise RunCannotResumeError(state.id, current_status=state.status)
    return [
        RunResumed(
            run_id=state.id,
            decided_by_decision_id=command.decided_by_decision_id,
            occurred_at=now,
        )
    ]
