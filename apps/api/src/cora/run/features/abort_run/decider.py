"""Pure decider for the `AbortRun` command.

Multi-source emergency-exit terminal: `Running | Held -> Aborted`.
Source set was widened to include `Held` (gate-review L2 lock):
emergencies during a hold are real and should not require an
intervening Resume. Aborting from any terminal (Completed |
Aborted | Stopped) raises `RunCannotAbortError`; re-aborting an
`Aborted` Run raises (strict-not-idempotent).

`reason` validation goes through the `RunAbortReason` VO (which
calls the shared `validate_bounded_text` helper). The on-the-wire payload
in `RunAborted.reason` carries the trimmed string.

Invariants:
  - State must not be None  -> RunNotFoundError
  - command.reason must be 1-500 chars after trimming
    -> InvalidRunAbortReasonError
  - State.status must be in {Running, Held}
    -> RunCannotAbortError(current_status=...)
"""

from datetime import datetime

from cora.run.aggregates.run import (
    Run,
    RunAborted,
    RunAbortReason,
    RunCannotAbortError,
    RunNotFoundError,
    RunStatus,
)
from cora.run.features.abort_run.command import AbortRun

_ABORTABLE_STATUSES: tuple[RunStatus, ...] = (RunStatus.RUNNING, RunStatus.HELD)


def decide(
    state: Run | None,
    command: AbortRun,
    *,
    now: datetime,
) -> list[RunAborted]:
    """Decide the events produced by aborting an existing Run."""
    if state is None:
        raise RunNotFoundError(command.run_id)
    reason = RunAbortReason(command.reason)
    if state.status not in _ABORTABLE_STATUSES:
        raise RunCannotAbortError(state.id, current_status=state.status)
    return [
        RunAborted(
            run_id=state.id,
            reason=reason.value,
            decided_by_decision_id=command.decided_by_decision_id,
            actuation_kind=command.actuation_kind,
            producing_job_id=command.producing_job_id,
            occurred_at=now,
        )
    ]
