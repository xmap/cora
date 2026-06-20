"""Pure decider for the `StopRun` command.

Multi-source controlled-exit terminal: `Running | Held -> Stopped`.
Symmetric source set with abort_run — operator-initiated controlled
exits don't require an active state, only any non-terminal state.
Stopping any terminal Run (Completed | Aborted | Stopped) raises;
re-stopping a `Stopped` Run raises (strict-not-idempotent).

`reason` validation goes through the `RunStopReason` VO (which
calls the shared `validate_bounded_text` helper). The on-the-wire payload
in `RunStopped.reason` carries the trimmed string.

Invariants:
  - State must not be None  -> RunNotFoundError
  - command.reason must be 1-500 chars after trimming
    -> InvalidRunStopReasonError
  - State.status must be in {Running, Held}
    -> RunCannotStopError(current_status=...)
"""

from datetime import datetime

from cora.run.aggregates.run import (
    Run,
    RunCannotStopError,
    RunNotFoundError,
    RunStatus,
    RunStopped,
    RunStopReason,
)
from cora.run.features.stop_run.command import StopRun

_STOPPABLE_STATUSES: tuple[RunStatus, ...] = (RunStatus.RUNNING, RunStatus.HELD)


def decide(
    state: Run | None,
    command: StopRun,
    *,
    now: datetime,
) -> list[RunStopped]:
    """Decide the events produced by stopping a Run."""
    if state is None:
        raise RunNotFoundError(command.run_id)
    reason = RunStopReason(command.reason)
    if state.status not in _STOPPABLE_STATUSES:
        raise RunCannotStopError(state.id, current_status=state.status)
    return [
        RunStopped(
            run_id=state.id,
            reason=reason.value,
            decided_by_decision_id=command.decided_by_decision_id,
            occurred_at=now,
        )
    ]
