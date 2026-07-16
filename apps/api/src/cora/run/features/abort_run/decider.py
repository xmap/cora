"""Pure decider for the `AbortRun` command.

Multi-source emergency-exit terminal: `Running | Held -> Aborted`.
Source set was widened to include `Held` (gate-review L2 lock):
emergencies during a hold are real and should not require an
intervening Resume. Aborting from any terminal (Completed |
Aborted | Stopped) raises `RunCannotAbortError`; re-aborting an
`Aborted` Run raises (strict-not-idempotent).

## Obligation gate (Gate III)

AbortRun is in `COMMANDS_REQUIRING_JUSTIFICATION`, so `require_justification` is
called FIRST (admission is the outer precondition): an abort without a non-empty,
bounded justification is refused with `JustificationRequiredError` (HTTP 422)
before any state/status check. Fail-closed and kind-blind (the helper reads only
the command name + text, never actor kind). The justification is the admission
account for taking this consequential action; it is distinct from the post-hoc
`reason` that lands on the RunAborted event and stays a pure decider input (no
I/O, so no handler pre-load needed, unlike the consequence gate's coverage lookup).

`reason` validation goes through the `RunAbortReason` VO (which
calls the shared `validate_bounded_text` helper). The on-the-wire payload
in `RunAborted.reason` carries the trimmed string.

Invariants:
  - Declared-class command without a valid justification
    -> JustificationRequiredError
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
from cora.shared.justification import require_justification

_ABORTABLE_STATUSES: tuple[RunStatus, ...] = (RunStatus.RUNNING, RunStatus.HELD)

_COMMAND_NAME = "AbortRun"


def decide(
    state: Run | None,
    command: AbortRun,
    *,
    now: datetime,
) -> list[RunAborted]:
    """Decide the events produced by aborting an existing Run."""
    require_justification(_COMMAND_NAME, command.justification)
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
