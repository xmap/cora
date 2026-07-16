"""Pure decider for the `StopRun` command.

Multi-source controlled-exit terminal: `Running | Held -> Stopped`.
Symmetric source set with abort_run — operator-initiated controlled
exits don't require an active state, only any non-terminal state.
Stopping any terminal Run (Completed | Aborted | Stopped) raises;
re-stopping a `Stopped` Run raises (strict-not-idempotent).

## Consequence gate (Gate IV)

`StopRun` is in the declared consequence class
(`cora.shared.consequence.COMMANDS_REQUIRING_RATIFICATION`): a deliberate,
irreversible early termination requires a second, independent principal's
co-signature. The handler pre-loads coverage via the `ConsequenceLookup` port and
passes `ratification_covered` here (the pure decider stays I/O-free). When the
command is in-scope AND coverage is absent, the gate refuses with
`RunRequiresRatificationError` BEFORE the status/transition checks: admission is
the outer precondition. Kind-blind (the decider never reads actor kind). On that
refusal the operator requests a ratification, which parks the run in the shared
hold pending the co-sign (see the RatificationHoldSubscriber).

`reason` validation goes through the `RunStopReason` VO (which
calls the shared `validate_bounded_text` helper). The on-the-wire payload
in `RunStopped.reason` carries the trimmed string.

Invariants:
  - Consequence-classed command without Granted coverage
    -> RunRequiresRatificationError
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
    RunRequiresRatificationError,
    RunStatus,
    RunStopped,
    RunStopReason,
)
from cora.run.features.stop_run.command import StopRun
from cora.shared.consequence import requires_ratification

_STOPPABLE_STATUSES: tuple[RunStatus, ...] = (RunStatus.RUNNING, RunStatus.HELD)

_COMMAND_NAME = "StopRun"


def decide(
    state: Run | None,
    command: StopRun,
    *,
    now: datetime,
    ratification_covered: bool,
) -> list[RunStopped]:
    """Decide the events produced by stopping a Run.

    `ratification_covered` is the consequence-gate coverage fact pre-loaded by the
    handler from the `ConsequenceLookup` port: True iff a Granted Ratification
    covers `(run_id, StopRun)`. The gate is checked first (admission precondition)
    so an un-co-signed stop is refused before any transition logic runs.
    """
    if requires_ratification(_COMMAND_NAME) and not ratification_covered:
        raise RunRequiresRatificationError(command.run_id, _COMMAND_NAME)
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
