"""Pure decider for the `HoldRun` command.

Single-source pause transition: `Running -> Held`. Re-holding an
already-`Held` Run raises (strict-not-idempotent); holding a
terminal Run raises.

Hold ⇄ Resume is bidirectional and unlimited-cycle (PackML +
Bluesky precedent), so an operator can hold → resume → hold
repeatedly during a single Run; each hold requires an intervening
resume.

Invariants:
  - State must not be None  -> RunNotFoundError
  - State.status must be in {Running}
    -> RunCannotHoldError(current_status=...)
"""

from datetime import datetime

from cora.run.aggregates.run import (
    Run,
    RunCannotHoldError,
    RunHeld,
    RunNotFoundError,
    RunStatus,
)
from cora.run.features.hold_run.command import HoldRun

_HOLDABLE_STATUSES: tuple[RunStatus, ...] = (RunStatus.RUNNING,)


def decide(
    state: Run | None,
    command: HoldRun,
    *,
    now: datetime,
) -> list[RunHeld]:
    """Decide the events produced by holding an existing Run."""
    if state is None:
        raise RunNotFoundError(command.run_id)
    if state.status not in _HOLDABLE_STATUSES:
        raise RunCannotHoldError(state.id, current_status=state.status)
    return [
        RunHeld(
            run_id=state.id,
            decided_by_decision_id=command.decided_by_decision_id,
            occurred_at=now,
        )
    ]
