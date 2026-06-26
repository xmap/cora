"""Pure decider for the `TruncateRun` command.

Multi-source partial-data terminal: `Running | Held -> Truncated`.
Symmetric source set with stop_run / abort_run, every operator-
initiated terminal accepts any non-terminal state. Truncating any
terminal Run (Completed | Aborted | Stopped | Truncated) raises;
re-truncating a `Truncated` Run raises (strict-not-idempotent).

`reason` validation goes through the `RunTruncateReason` VO (which
calls the shared `validate_bounded_text` helper). The on-the-wire payload
in `RunTruncated.reason` carries the trimmed string.

`interrupted_at` is operator-supplied and optional. When provided,
must not be in the future relative to `now` (defensive guard, the
operator should be marking a past interruption); the decider does
NOT enforce a lower bound, on-the-wire serialization preserves
whatever timezone-aware datetime the caller supplied.

Today the decider emits a single `RunTruncated` event. When the
Run aggregate adds logbooks, the decider extends
to emit one `RunLogbookClosed` event per open logbook before the
`RunTruncated` event, per gate-review L4. The single-event shape
today is forward-compatible: the slim Run aggregate has no
`logbooks` field today, so the close-events list is naturally
empty.

Invariants:
  - State must not be None  -> RunNotFoundError
  - command.reason must be 1-500 chars after trimming
    -> InvalidRunTruncateReasonError
  - interrupted_at, when set, must not be in the future
    -> InvalidRunInterruptedAtError
  - State.status must be in {Running, Held}
    -> RunCannotTruncateError(current_status=...)
"""

from datetime import datetime

from cora.run.aggregates.run import (
    InvalidRunInterruptedAtError,
    Run,
    RunCannotTruncateError,
    RunNotFoundError,
    RunStatus,
    RunTruncated,
    RunTruncateReason,
)
from cora.run.features.truncate_run.command import TruncateRun

_TRUNCATABLE_STATUSES: tuple[RunStatus, ...] = (RunStatus.RUNNING, RunStatus.HELD)


def decide(
    state: Run | None,
    command: TruncateRun,
    *,
    now: datetime,
) -> list[RunTruncated]:
    """Decide the events produced by truncating a Run."""
    if state is None:
        raise RunNotFoundError(command.run_id)
    reason = RunTruncateReason(command.reason)
    if command.interrupted_at is not None and command.interrupted_at > now:
        raise InvalidRunInterruptedAtError(command.interrupted_at, now)
    if state.status not in _TRUNCATABLE_STATUSES:
        raise RunCannotTruncateError(state.id, current_status=state.status)
    return [
        RunTruncated(
            run_id=state.id,
            reason=reason.value,
            interrupted_at=command.interrupted_at,
            occurred_at=now,
            decided_by_decision_id=command.decided_by_decision_id,
        )
    ]
