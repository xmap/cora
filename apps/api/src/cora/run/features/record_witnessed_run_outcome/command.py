"""The `RecordWitnessedRunOutcome` command -- intent dataclass for this slice.

A witnessed terminal: CORA records that an external tool reported a
capture's lifecycle ended, closing a Run the witnessed-genesis slice
opened. Carries only the substrate-observed facts:

  - `run_id` -- the Run to terminate. Resolved by the RunWitness runtime
    from its own dedup map (capture_code -> open Run id), never
    operator-supplied.
  - `capture_code` -- carried for logging/error-message attribution only;
    not used to look up the Run (the runtime already resolved `run_id`).
  - `observed_phase` -- which terminal the substrate reported, `Ended` or
    `Aborted`. The decider refuses every other `CapturePhase` value: the
    runtime never calls this command for `Begun` / `Progressing` /
    `Unrecognized`, so reaching here with one of those is a caller
    mistake, not a fact about the world.
  - `observed_at` -- the substrate's own time for the terminal reading,
    carried straight onto `RunCompleted.observed_at` /
    `RunAborted.observed_at`. `None` when the substrate reported no time
    at all (same shape as `CaptureLifecycleObservation.observed_at`).
  - `monitor_source_id` -- the stable `MonitorSourceId` of the in-process
    RunWitness runtime, mirroring `RecordWitnessedRun.monitor_source_id`.
  - `trigger` -- command-tier guard string. The decider rejects any value
    other than the literal `"Monitor"` with
    `RunMonitorTriggerNotPermittedError`, the same anti-lock
    `RecordWitnessedRun` carries: there is no operator path to a
    witnessed terminal.
  - `capture_progress_snapshot` -- the last per-role progress counts
    RunWitness retained before this terminal, or `None` if nothing was
    retained. Carried straight onto `RunCompleted
    .capture_progress_snapshot` / `RunAborted.capture_progress_snapshot`
    with no validation (see the decider's docstring for why an
    out-of-order or future-dated reading inside it does not refuse the
    terminal).

No `reason` field: for an `Aborted` outcome the decider composes the
`RunAborted.reason` text itself from `capture_code`, so no
operator-injectable string reaches the event through this command. No
`decided_by_decision_id`: RunWitness has no Decision-BC input to link.
`capture_progress_snapshot` does not change that: it carries substrate-
observed numbers and timestamps, never operator-authored text.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from cora.run.aggregates.run.state import CaptureProgressSnapshot
from cora.shared.capture_phase import CapturePhase
from cora.shared.identity import MonitorSourceId


@dataclass(frozen=True)
class RecordWitnessedRunOutcome:
    """Record that an external tool reported a witnessed capture's terminal."""

    run_id: UUID
    capture_code: str
    observed_phase: CapturePhase
    observed_at: datetime | None
    monitor_source_id: MonitorSourceId
    trigger: str
    capture_progress_snapshot: CaptureProgressSnapshot | None
