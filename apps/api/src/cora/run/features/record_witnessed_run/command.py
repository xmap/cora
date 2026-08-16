"""The `RecordWitnessedRun` command -- intent dataclass for this slice.

A witnessed genesis: CORA records that an external tool began a capture,
rather than driving the act itself. Carries the caller-controlled inputs:

  - `name` -- display name for the new Run, same free-text shape as
    `StartRun.name`.
  - `plan_id` -- the Plan being executed. Deployment-declared (the
    RunWitness runtime resolves it from settings, not from the substrate);
    existence verified at handler-load time exactly as at a driven start.
  - `subject_id` -- always None in practice today (2-BM's dark-field /
    flat-field / fly-scan captures carry no Subject binding), but kept
    `UUID | None` rather than dropped: a future deployment watching a
    sample-bound capture is the same shape, not a different command.
  - `capture_code` -- the deployment-declared identity surface for the
    acquisition path being watched (`CaptureObserverScope`'s own
    vocabulary), carried onto the emitted `RunStarted.external_refs` as
    an `Identifier(scheme="capture-code", value=capture_code)` so a
    restart can rediscover which Run belongs to which open capture.
  - `monitor_source_id` -- the stable `MonitorSourceId` of the in-process
    RunWitness runtime that produced this genesis, mirroring
    `ObserveEnclosureStatus.monitor_source_id`.
  - `trigger` -- command-tier guard string. The decider rejects any value
    other than the literal `"Monitor"` with
    `RunMonitorTriggerNotPermittedError`, closing the operator-assert-
    Witnessed backdoor (mirrors `ObserveEnclosureStatus.trigger`'s D6.L2
    anti-lock): there is no operator path to a witnessed genesis.
  - `capture_precondition_bypass_snapshot` -- the latest `testing`-role
    reading `RunWitness` retained before this genesis, or `None` if the
    capture code declares no `testing` role, or none has ever arrived.
    Carried straight onto
    `RunStarted.capture_precondition_bypass_snapshot` with no
    validation, same posture as `RecordWitnessedRunOutcome
    .capture_progress_snapshot`: it carries a substrate-observed tri-
    state claim and a substrate timestamp, never operator-authored text.
    See `CapturePreconditionBypassSnapshot` for the tri-state contract
    and why this is NOT `Manifest.is_simulated`.

No `conduct_mode` field: this decider hardcodes `ConductMode.WITNESSED`,
symmetric to `StartRun` carrying no `conduct_mode` field for the driven
decider's hardcoded `CONDUCTED`. The mode is a property of which decider
ran, never a caller's choice, on either path.

No `override_parameters`, `campaign_id`, `raid`, `decided_by_decision_id`,
`pinned_calibration_ids`, `input_dataset_ids`, or `compute_resource_code`:
RunWitness has no operator inputs to pass, and every field this command
does not carry is a field an operator cannot reach through it. Effective
parameters are the Plan's own defaults, unmodified.

No `observed_at`: `RunStarted` has no substrate-time field, and adding
one is deferred to the terminal-recording slice that actually needs it.
`occurred_at`, stamped from the Clock port in the handler, is honest
about what it claims: when CORA learned of the genesis, not when the
substrate says the capture began.

Status is implicit at start (`Running`), same as `StartRun`.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.run.aggregates.run.state import CapturePreconditionBypassSnapshot
from cora.shared.identity import MonitorSourceId


@dataclass(frozen=True)
class RecordWitnessedRun:
    """Record that an external tool began a capture: a witnessed Run genesis."""

    name: str
    plan_id: UUID
    capture_code: str
    monitor_source_id: MonitorSourceId
    trigger: str
    subject_id: UUID | None = None
    capture_precondition_bypass_snapshot: CapturePreconditionBypassSnapshot | None = None
