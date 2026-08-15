"""Pure decider for the `RecordWitnessedRunOutcome` command.

Closes the witnessed genesis: `Running -> Completed` for an observed
`Ended`, `Running -> Aborted` for an observed `Aborted`. Emits the
EXISTING `RunCompleted` / `RunAborted` events (no new event type, no new
evolver arm, no new projection or export surface); only the command,
this decider, and the handler are new.

The two request-shape guards (`trigger`, `observed_phase`) run first,
mirroring `record_witnessed_run.decider`'s own ordering rationale: they
reject a malformed call before touching any state. `RunNotWitnessedError`
runs before the timestamp and status checks because it is the more
fundamental refusal -- an operator-driven Run's terminal never belongs to
this command regardless of what `observed_at` says or what status the
Run is in.

For an `Aborted` outcome, the `RunAborted.reason` text is composed here
from `capture_code`, never taken from the command: RunWitness has no
operator-injectable reason field to launder through this path.

Invariants:
  - command.trigger must be "Monitor"
    -> RunMonitorTriggerNotPermittedError
  - command.observed_phase must be Ended or Aborted
    -> RunCapturePhaseNotTerminalError
  - State must not be None  -> RunNotFoundError
  - State.conduct_mode must be Witnessed  -> RunNotWitnessedError
  - command.observed_at, when set, must not be in the future
    -> InvalidRunObservedAtError
  - State.status must be in {Running} for an Ended outcome
    -> RunCannotCompleteError(current_status=...)
  - State.status must be in {Running} for an Aborted outcome
    -> RunCannotAbortError(current_status=...)
"""

from datetime import datetime

from cora.run.aggregates.run import (
    InvalidRunObservedAtError,
    Run,
    RunAborted,
    RunAbortReason,
    RunCannotAbortError,
    RunCannotCompleteError,
    RunCapturePhaseNotTerminalError,
    RunCompleted,
    RunMonitorTriggerNotPermittedError,
    RunNotFoundError,
    RunNotWitnessedError,
    RunStatus,
)
from cora.run.features.record_witnessed_run_outcome.command import RecordWitnessedRunOutcome
from cora.shared.capture_phase import CapturePhase

_TERMINABLE_STATUSES: tuple[RunStatus, ...] = (RunStatus.RUNNING,)
_TERMINAL_PHASES: tuple[CapturePhase, ...] = (CapturePhase.ENDED, CapturePhase.ABORTED)
_REQUIRED_TRIGGER = "Monitor"


def decide(
    state: Run | None,
    command: RecordWitnessedRunOutcome,
    *,
    now: datetime,
) -> list[RunCompleted] | list[RunAborted]:
    """Decide the events produced by closing a witnessed Run."""
    if command.trigger != _REQUIRED_TRIGGER:
        raise RunMonitorTriggerNotPermittedError(command.run_id, command.trigger)
    if command.observed_phase not in _TERMINAL_PHASES:
        raise RunCapturePhaseNotTerminalError(command.run_id, command.observed_phase)
    if state is None:
        raise RunNotFoundError(command.run_id)
    if state.conduct_mode != "Witnessed":
        raise RunNotWitnessedError(state.id, state.conduct_mode)
    if command.observed_at is not None and command.observed_at > now:
        raise InvalidRunObservedAtError(command.observed_at, now)

    if command.observed_phase is CapturePhase.ENDED:
        if state.status not in _TERMINABLE_STATUSES:
            raise RunCannotCompleteError(state.id, current_status=state.status)
        return [
            RunCompleted(
                run_id=state.id,
                occurred_at=now,
                observed_at=command.observed_at,
            )
        ]

    if state.status not in _TERMINABLE_STATUSES:
        raise RunCannotAbortError(state.id, current_status=state.status)
    reason = RunAbortReason(f"RunWitness observed capture {command.capture_code} as Aborted")
    return [
        RunAborted(
            run_id=state.id,
            reason=reason.value,
            occurred_at=now,
            observed_at=command.observed_at,
        )
    ]
