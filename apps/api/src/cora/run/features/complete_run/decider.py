"""Pure decider for the `CompleteRun` command.

Single-source happy-path terminal: `Running -> Completed`.
Re-completing an already-`Completed` Run raises (strict-not-
idempotent); completing an `Aborted` Run raises.

Source-state guard uses tuple-membership for forward-compat with
6f-3+ adding `Held` as an additional source if hold-then-complete
proves to be a real beamline workflow (today: just `Running`).

Invariants:
  - State must not be None  -> RunNotFoundError
  - State.status must be in {Running}
    -> RunCannotCompleteError(current_status=...)
"""

from datetime import datetime

from cora.run.aggregates.run import (
    Run,
    RunCannotCompleteError,
    RunCompleted,
    RunNotFoundError,
    RunStatus,
)
from cora.run.features.complete_run.command import CompleteRun

_COMPLETABLE_STATUSES: tuple[RunStatus, ...] = (RunStatus.RUNNING,)


def decide(
    state: Run | None,
    command: CompleteRun,
    *,
    now: datetime,
) -> list[RunCompleted]:
    """Decide the events produced by completing an existing Run."""
    if state is None:
        raise RunNotFoundError(command.run_id)
    if state.status not in _COMPLETABLE_STATUSES:
        raise RunCannotCompleteError(state.id, current_status=state.status)
    return [
        RunCompleted(
            run_id=state.id,
            actuation_kind=command.actuation_kind,
            producing_job_id=command.producing_job_id,
            artifact_uri=command.artifact_uri,
            occurred_at=now,
        )
    ]
